from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, jsonify, render_template, request
from pydantic import BaseModel

from app import library as media_library
from app.ai.enhancement import PromptEnhancementService
from app.ai.profiles import AIProfileStore
from app.ai.prompting import PromptOperation, PromptScenario, PromptTask
from app.ai.reconstruction import SceneAnalysisService
from app.ai.translation import PromptText
from app.config_store import ConfigStore

from .client import ComfyUIClient, ComfyUIClientError
from .simple_profiles import (
    APPROVED_PROFILES,
    ApprovedProfile,
    QualityPresetLevel,
    check_profile_health,
    compile_simple_workflow,
    serialize_approved_profile,
)
from .workflow_execution import WorkflowExecutionService
from .workflow_inventory import cached_runtime_inventory, client_from_store
from .workflow_store import WorkflowStore

logger = logging.getLogger(__name__)
simple_blueprint = Blueprint("simple_mode", __name__)


def _config_store() -> ConfigStore:
    return current_app.config["CONFIG_STORE"]


def _ai_profile_store() -> AIProfileStore:
    return AIProfileStore(
        Path(current_app.config["CONFIG_FILE"]),
        secret_store=current_app.config.get("AI_SECRET_STORE"),
    )


def _list_ai_profiles() -> list[dict[str, Any]]:
    ai_data = _ai_profile_store().list()
    if isinstance(ai_data, dict):
        return ai_data.get("profiles", [])
    if isinstance(ai_data, list):
        return ai_data
    return []


def _client() -> ComfyUIClient:
    return client_from_store(_config_store())


def _workflow_store() -> WorkflowStore:
    return WorkflowStore()


def _catalog_payload() -> list[dict[str, Any]]:
    return [
        serialize_approved_profile(profile, include_health=False)
        for profile in APPROVED_PROFILES.values()
    ]


def _ai_status_payload() -> dict[str, Any]:
    ai_profiles = _list_ai_profiles()
    has_text = any(
        "text" in profile.get("roles", []) or "translator" in profile.get("roles", [])
        for profile in ai_profiles
    )
    has_vision = any(
        "vision" in profile.get("roles", []) or profile.get("multimodal") is True
        for profile in ai_profiles
    )
    return {
        "available": bool(ai_profiles),
        "has_text": has_text,
        "has_vision": has_vision,
        "profile_count": len(ai_profiles),
    }


def _ambient_payload(limit: int = 36) -> list[dict[str, Any]]:
    """Use the same indexed Library layer as Viewer/Library, never raw Simple Mode SQL."""
    try:
        page = media_library.get_assets(
            collection="images",
            page=1,
            per_page=max(80, min(240, limit * 4)),
            sort_by="added",
            sort_dir="desc",
        )
    except Exception as exc:
        logger.debug("Failed to load ambient library assets: %s", exc)
        return []

    candidates = [
        asset for asset in page.get("assets", [])
        if asset.get("media_type") == "image" and asset.get("available", True)
    ]
    random.shuffle(candidates)
    return [
        {
            "id": int(asset["id"]),
            "file_name": asset.get("file_name") or "",
            "preview_url": f"/api/preview/{int(asset['id'])}",
            "thumbnail_url": asset.get("thumbnail_url") or f"/api/thumbnail/{int(asset['id'])}",
            "width": int(asset.get("width") or 0),
            "height": int(asset.get("height") or 0),
        }
        for asset in candidates[:limit]
    ]


@simple_blueprint.route("/create")
@simple_blueprint.route("/editor")
def simple_mode_page():
    initial_models = _catalog_payload()
    return render_template(
        "create.html",
        initial_models=initial_models,
        default_model_id=initial_models[0]["id"] if initial_models else "",
    )


@simple_blueprint.route("/api/simple/models", methods=["GET"])
def simple_models():
    return jsonify({
        "models": _catalog_payload(),
        "default_model_id": next(iter(APPROVED_PROFILES), None),
    })


@simple_blueprint.route("/api/simple/ambient", methods=["GET"])
def simple_ambient():
    limit = request.args.get("limit", default=36, type=int) or 36
    return jsonify({"items": _ambient_payload(max(1, min(limit, 72)))})


@simple_blueprint.route("/api/simple/ai-status", methods=["GET"])
def simple_ai_status():
    return jsonify(_ai_status_payload())


@simple_blueprint.route("/api/simple/bootstrap", methods=["GET"])
def simple_bootstrap():
    """Compatibility endpoint. New Create UI hydrates these resources independently."""
    return jsonify({
        "profiles": _catalog_payload(),
        "default_profile_id": next(iter(APPROVED_PROFILES), None),
        "ambient_candidates": _ambient_payload(),
        "ai_status": _ai_status_payload(),
    })


@simple_blueprint.route("/api/simple/models/<profile_id>/status", methods=["GET"])
@simple_blueprint.route("/api/simple/profiles/<profile_id>/status", methods=["GET"])
def simple_profile_status(profile_id: str):
    profile = APPROVED_PROFILES.get(profile_id)
    if not profile:
        return jsonify({"error": "Model not found"}), 404
    try:
        inventory = cached_runtime_inventory(_config_store())
    except Exception:
        inventory = None
    return jsonify({
        "profile_id": profile_id,
        "health": check_profile_health(profile, inventory),
    })


class SimpleGenerateRequest(BaseModel):
    profile_id: str = "model_01"
    prompt: str = ""
    improve_with_ai: bool = True
    aspect_ratio: str = "1:1"
    quality: str = "standard"
    batch_size: int = 1
    seed: int = -1
    reference_image: str | None = None
    negative_prompt: str | None = None


def _quality_level(value: str) -> QualityPresetLevel:
    normalized = (value or "standard").casefold()
    if normalized in {"high", "maximum"}:
        normalized = "detailed"
    try:
        return QualityPresetLevel(normalized)
    except ValueError:
        return QualityPresetLevel.STANDARD


def _first_profile_for_role(role: str) -> dict[str, Any] | None:
    for profile in _list_ai_profiles():
        roles = profile.get("roles", [])
        if role in roles:
            return profile
        if role == "vision" and profile.get("multimodal") is True:
            return profile
        if role == "text" and "translator" in roles:
            return profile
    return None


def _prepare_prompt(profile: ApprovedProfile, req: SimpleGenerateRequest) -> tuple[str, str, bool, str | None]:
    positive_prompt = req.prompt.strip()
    negative_prompt = req.negative_prompt if req.negative_prompt is not None else profile.default_negative_prompt
    ai_improved = False
    explanation = None

    if req.reference_image and req.reference_image.startswith("data:image/"):
        vision_profile = _first_profile_for_role("vision")
        if vision_profile:
            try:
                ai_store = _ai_profile_store()
                scene_service = SceneAnalysisService()
                task = PromptTask(
                    operation=PromptOperation.RECONSTRUCT,
                    family=profile.prompt_family,
                    scenario=PromptScenario.ILLUSTRATION_ART,
                )
                outcome = scene_service.analyze(
                    profile=vision_profile,
                    task=task,
                    image_data_url=req.reference_image,
                    api_key=ai_store.resolve_api_key(vision_profile),
                )
                subjects = ", ".join(
                    subject.kind for subject in outcome.scene_spec.subjects if subject.kind
                )
                background = outcome.scene_spec.composition.background or ""
                reconstructed = f"{subjects}, {background}".strip(", ")
                if reconstructed:
                    positive_prompt = (
                        f"{positive_prompt}, {reconstructed}" if positive_prompt else reconstructed
                    )
                    ai_improved = True
                    explanation = "Reconstructed from reference image"
            except Exception as exc:
                logger.warning("Vision reconstruction fallback: %s", exc)

    elif req.improve_with_ai and positive_prompt:
        text_profile = _first_profile_for_role("text")
        if text_profile:
            try:
                ai_store = _ai_profile_store()
                outcome = PromptEnhancementService().enhance(
                    profile=text_profile,
                    task=PromptTask(
                        operation=PromptOperation.ENHANCE,
                        family=profile.prompt_family,
                        scenario=PromptScenario.ILLUSTRATION_ART,
                    ),
                    source=PromptText(positive_prompt=positive_prompt),
                    api_key=ai_store.resolve_api_key(text_profile),
                )
                enhanced = outcome.enhancement.enhanced
                if enhanced.positive_prompt:
                    positive_prompt = enhanced.positive_prompt
                    if enhanced.negative_prompt:
                        negative_prompt = enhanced.negative_prompt
                    ai_improved = True
                    explanation = "Enhanced with AI prompt compiler"
            except Exception as exc:
                logger.warning("AI prompt improvement fallback: %s", exc)

    if not positive_prompt:
        positive_prompt = "Highly detailed image matching the provided visual direction"
    return positive_prompt, negative_prompt or "", ai_improved, explanation


@simple_blueprint.route("/api/simple/generate", methods=["POST"])
def simple_generate():
    try:
        req = SimpleGenerateRequest.model_validate(request.get_json(silent=True) or {})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    profile = APPROVED_PROFILES.get(req.profile_id)
    if not profile:
        return jsonify({"error": f"Unknown model '{req.profile_id}'"}), 400

    if not profile.workflow_ready:
        return jsonify({
            "error": "Workflow for this model is still being calibrated.",
            "code": "workflow_pending",
        }), 409

    try:
        inventory = cached_runtime_inventory(_config_store())
        health = check_profile_health(profile, inventory)
        if health["status"] == "not_installed":
            return jsonify({
                "error": "Required model components are missing.",
                "code": "model_not_installed",
                "missing_resources": health["missing_resources"],
            }), 409
    except Exception:
        pass

    positive_prompt, negative_prompt, ai_improved, ai_explanation = _prepare_prompt(profile, req)
    quality_level = _quality_level(req.quality)

    try:
        compiled_workflow = compile_simple_workflow(
            profile,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            aspect_ratio=req.aspect_ratio,
            quality=quality_level,
            batch_size=req.batch_size,
            seed=req.seed,
        )
    except Exception as exc:
        return jsonify({"error": f"Failed to compile workflow: {exc}"}), 500

    wf_store = _workflow_store()
    draft = wf_store.create_draft(
        template_id=f"simple-{profile.id}",
        template_version="2.0.0",
        values={
            "positive_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "aspect_ratio": req.aspect_ratio,
            "quality": quality_level.value,
            "batch_size": req.batch_size,
            "seed": req.seed,
        },
        resource_selections={},
    )

    import uuid
    client_id = str(uuid.uuid4())
    try:
        result = _client().queue_prompt(
            compiled_workflow,
            client_id=client_id,
            extra_data={
                "comfy_meta_viewer": {
                    "simple_mode": True,
                    "profile_id": profile.id,
                    "quality": quality_level.value,
                    "draft_id": draft.id,
                },
                "extra_pnginfo": {
                    "cmv_simple_profile": profile.id,
                    "cmv_prompt": positive_prompt,
                },
            },
        )
        prompt_id = str(result["prompt_id"])
    except ComfyUIClientError as exc:
        return jsonify({
            "error": f"ComfyUI rejected prompt: {exc}",
            "code": "comfyui_rejected",
            "suggestion": "Проверьте, что ComfyUI запущен и компоненты выбранной модели установлены.",
        }), 502
    except Exception as exc:
        return jsonify({
            "error": f"Connection error: {exc}",
            "code": "comfyui_connection_failed",
            "suggestion": "Не удалось связаться с ComfyUI. Проверьте подключение и повторите.",
        }), 503

    run = wf_store.create_run(
        draft_id=draft.id,
        prompt_id=prompt_id,
        client_id=client_id,
    )
    return jsonify({
        "ok": True,
        "run_id": run.id,
        "prompt_id": prompt_id,
        "profile_id": profile.id,
        "positive_prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "ai_improved": ai_improved,
        "ai_explanation": ai_explanation,
    })


def _output_asset_payload(asset_id: int) -> dict[str, Any] | None:
    try:
        result = media_library.get_assets(
            collection="all",
            asset_id=int(asset_id),
            page=1,
            per_page=1,
        )
    except Exception:
        return None
    assets = result.get("assets", [])
    if not assets:
        return None
    asset = assets[0]
    return {
        "id": int(asset["id"]),
        "filename": asset.get("file_name") or "",
        "preview_url": f"/api/preview/{int(asset['id'])}",
        "thumbnail_url": asset.get("thumbnail_url") or f"/api/thumbnail/{int(asset['id'])}",
        "width": int(asset.get("width") or 0),
        "height": int(asset.get("height") or 0),
    }


@simple_blueprint.route("/api/simple/runs/<int:run_id>", methods=["GET"])
def simple_get_run(run_id: int):
    wf_store = _workflow_store()
    try:
        run = WorkflowExecutionService(store=wf_store, client=_client()).refresh(run_id)
    except Exception:
        run = wf_store.get_run(run_id)

    outputs = [
        payload
        for asset_id in run.output_asset_ids
        if (payload := _output_asset_payload(int(asset_id))) is not None
    ]
    return jsonify({
        "run": run.model_dump(mode="json"),
        "status": run.status,
        "outputs": outputs,
        "is_complete": run.status in {"completed", "failed", "cancelled"},
    })


@simple_blueprint.route("/api/simple/runs/<int:run_id>/cancel", methods=["POST"])
def simple_cancel_run(run_id: int):
    wf_store = _workflow_store()
    try:
        run = WorkflowExecutionService(store=wf_store, client=_client()).cancel(run_id)
        return jsonify({"ok": True, "run": run.model_dump(mode="json")})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@simple_blueprint.route("/api/simple/assistant/chat", methods=["POST"])
def simple_assistant_chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    profile_id = str(data.get("profile_id", "model_01"))
    history = data.get("history", [])
    current_prompt = str(data.get("current_prompt", "")).strip()
    if not message:
        return jsonify({"error": "Message is required"}), 400

    profile = APPROVED_PROFILES.get(profile_id) or next(iter(APPROVED_PROFILES.values()), None)
    if profile is None:
        return jsonify({"error": "No Simple Mode models configured"}), 500

    text_profile = _first_profile_for_role("text")
    if not text_profile:
        return jsonify({
            "error": "No AI text profile configured. Add an AI provider in Integrations.",
            "code": "no_ai_profile",
        }), 400

    try:
        from app.ai.transport import run_openai_compatible_chat

        system_prompt = (
            "You are a concise prompt assistant for ComfyUI image generation.\n"
            f"Selected user model: {profile.name} ({profile.technical_name}).\n"
            f"Prompt family: {profile.prompt_family.value}.\n"
            "Help refine composition, lighting, subject details and clarity. "
            "Do not add generic quality buzzwords unless they are technically required by the model."
        )
        messages = [{"role": "system", "content": system_prompt}]
        if current_prompt:
            messages.append({"role": "system", "content": f"Current prompt: {current_prompt}"})
        for item in history[-8:]:
            messages.append({
                "role": item.get("role", "user"),
                "content": item.get("content", ""),
            })
        messages.append({"role": "user", "content": message})

        ai_store = _ai_profile_store()
        response = run_openai_compatible_chat(
            profile=text_profile,
            messages=messages,
            api_key=ai_store.resolve_api_key(text_profile),
        )
        return jsonify({"reply": response.text, "profile_id": profile.id})
    except Exception as exc:
        return jsonify({"error": f"AI Assistant error: {exc}"}), 500
