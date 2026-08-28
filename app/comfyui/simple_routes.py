from __future__ import annotations

import base64
import json
import logging
import random
import time
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, render_template, request, stream_with_context
from pydantic import BaseModel, Field

from app import database
from app.ai.enhancement import PromptEnhancementService
from app.ai.job_store import AIJobStore
from app.ai.profiles import AIProfileStore
from app.ai.prompting import PromptFamily, PromptOperation, PromptScenario, PromptTask
from app.ai.reconstruction import SceneAnalysisService
from app.ai.translation import PromptText, PromptTranslationService
from app.config_store import ConfigStore
from app.media import media_type_for_path
from app.paths import portable_filename

from .client import ComfyUIClient, ComfyUIClientError
from .resource_taxonomy import ResourceType
from .simple_profiles import (
    APPROVED_PROFILES,
    ApprovedProfile,
    QualityPresetLevel,
    check_profile_health,
    compile_simple_workflow,
    load_simple_workflow_json,
    serialize_approved_profile,
)

from .workflow_execution import WorkflowExecutionError, WorkflowExecutionService
from .workflow_inventory import cached_runtime_inventory, client_from_store
from .workflow_models import WorkflowDraft
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


def _get_ambient_candidates(limit: int = 36) -> list[dict[str, Any]]:
    """Retrieve aesthetic candidate images from the existing library for ambient glow."""
    conn = database.get_conn()
    try:
        rows = conn.execute(
            """SELECT i.id, i.filename, i.rating, i.favorite, i.width, i.height
            FROM images i
            WHERE i.is_trash = 0 AND (i.media_type = 'image' OR i.media_type IS NULL)
            ORDER BY i.favorite DESC, RANDOM()
            LIMIT ?""",
            (limit,),
        ).fetchall()
        candidates = []
        for row in rows:
            candidates.append({
                "id": row["id"],
                "filename": row["filename"],
                "thumbnail_url": f"/api/thumbnail/{row['id']}",
                "preview_url": f"/api/preview/{row['id']}",
                "width": row["width"],
                "height": row["height"],
            })
        return candidates
    except Exception as exc:
        logger.debug(f"Failed to load ambient candidates: {exc}")
        return []
    finally:
        conn.close()


@simple_blueprint.route("/create")
@simple_blueprint.route("/editor")
def simple_mode_page():
    return render_template("create.html")


def check_comfy_online() -> bool:
    try:
        return bool(_client().check_health().get("online"))
    except Exception:
        return False


@simple_blueprint.route("/api/simple/bootstrap", methods=["GET"])
def simple_bootstrap():
    """Returns approved generation profiles, system health, ambient art candidates, and AI status."""
    try:
        inventory = cached_runtime_inventory(_config_store())
    except Exception:
        inventory = None

    profiles_data = [
        serialize_approved_profile(profile, inventory)
        for profile in APPROVED_PROFILES.values()
    ]

    ai_store = _ai_profile_store()
    ai_data = ai_store.list()
    ai_profiles = ai_data.get("profiles", []) if isinstance(ai_data, dict) else []
    has_text_ai = any("text" in p.get("roles", []) for p in ai_profiles)
    has_vision_ai = any("vision" in p.get("roles", []) or p.get("multimodal") is True for p in ai_profiles)


    ambient_candidates = _get_ambient_candidates()

    return jsonify({
        "profiles": profiles_data,
        "default_profile_id": "realism",
        "ambient_candidates": ambient_candidates,
        "ai_status": {
            "available": bool(ai_profiles),
            "has_text": has_text_ai,
            "has_vision": has_vision_ai,
            "profile_count": len(ai_profiles),
        },
        "comfyui_status": {
            "configured": bool(_config_store().comfyui_settings().get("base_url")),
            "online": check_comfy_online(),
        },

    })


@simple_blueprint.route("/api/simple/profiles/<profile_id>/status", methods=["GET"])
def simple_profile_status(profile_id: str):
    profile = APPROVED_PROFILES.get(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    try:
        inventory = cached_runtime_inventory(_config_store())
    except Exception:
        inventory = None
    health = check_profile_health(profile, inventory)
    return jsonify({
        "profile_id": profile_id,
        "health": health,
    })


class SimpleGenerateRequest(BaseModel):
    profile_id: str = "realism"
    prompt: str = ""
    improve_with_ai: bool = True
    aspect_ratio: str = "1:1"
    quality: str = "standard"
    batch_size: int = 1
    seed: int = -1
    reference_image: str | None = None
    negative_prompt: str | None = None


@simple_blueprint.route("/api/simple/generate", methods=["POST"])
def simple_generate():
    """
    End-to-end Simple Mode generation:
    1. AI Prompt improvement & translation / Vision reconstruction
    2. Quality preset & aspect ratio mapping
    3. Workflow compilation & execution queueing
    """
    raw_payload = request.get_json(silent=True) or {}
    try:
        req = SimpleGenerateRequest.model_validate(raw_payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    profile = APPROVED_PROFILES.get(req.profile_id)
    if not profile:
        return jsonify({"error": f"Unknown profile '{req.profile_id}'"}), 400

    positive_prompt = req.prompt.strip()
    negative_prompt = req.negative_prompt or profile.default_negative_prompt

    ai_improved = False
    ai_explanation = None

    # Step 1: Reference image vision reconstruction if provided
    if req.reference_image and req.reference_image.startswith("data:image/"):
        ai_profiles = _list_ai_profiles()
        vision_profile = None
        for p in ai_profiles:
            if "vision" in p.get("roles", []) or p.get("multimodal") is True:
                vision_profile = p
                break
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
                # Build reconstructed prompt description
                subjects_desc = ", ".join(s.kind for s in outcome.scene_spec.subjects if s.kind)
                comp_desc = outcome.scene_spec.composition.background or ""
                reconstructed = f"{subjects_desc}, {comp_desc}".strip(", ")
                if reconstructed:
                    positive_prompt = (
                        f"{positive_prompt}, {reconstructed}" if positive_prompt else reconstructed
                    )
                    ai_improved = True
                    ai_explanation = "Reconstructed from reference image"
            except Exception as exc:
                logger.warning(f"Vision reconstruction fallback: {exc}")

    # Step 2: AI prompt improvement if enabled and prompt is present
    elif req.improve_with_ai and positive_prompt:
        ai_profiles = _list_ai_profiles()
        text_profile = None
        for p in ai_profiles:
            if "text" in p.get("roles", []) or "translator" in p.get("roles", []):
                text_profile = p
                break

        if text_profile:
            try:
                ai_store = _ai_profile_store()
                enhance_service = PromptEnhancementService()
                task = PromptTask(
                    operation=PromptOperation.ENHANCE,
                    family=profile.prompt_family,
                    scenario=PromptScenario.ILLUSTRATION_ART,
                )
                # Enhance prompt
                outcome = enhance_service.enhance(
                    profile=text_profile,
                    task=task,
                    source=PromptText(positive_prompt=positive_prompt),
                    api_key=ai_store.resolve_api_key(text_profile),
                )
                if outcome.enhancement.enhanced.positive_prompt:
                    positive_prompt = outcome.enhancement.enhanced.positive_prompt
                    if outcome.enhancement.enhanced.negative_prompt:
                        negative_prompt = outcome.enhancement.enhanced.negative_prompt
                    ai_improved = True
                    ai_explanation = "Enhanced with AI prompt compiler"
            except Exception as exc:
                logger.warning(f"AI Prompt improvement fallback: {exc}")

    if not positive_prompt:
        positive_prompt = "A beautiful aesthetic masterpiece, highly detailed"

    # Step 3: Parse quality preset
    try:
        quality_level = QualityPresetLevel(req.quality.lower())
    except ValueError:
        quality_level = QualityPresetLevel.STANDARD

    # Step 4: Compile workflow
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

    # Step 5: Queue execution in ComfyUI
    client = _client()
    wf_store = _workflow_store()

    # Create synthetic draft record for provenance
    draft = wf_store.create_draft(
        template_id=f"simple-{profile.id}",
        template_version="1.0.0",
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
        res = client.queue_prompt(
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
        prompt_id = str(res["prompt_id"])
    except ComfyUIClientError as exc:
        return jsonify({
            "error": f"ComfyUI rejected prompt: {exc}",
            "code": "comfyui_rejected",
            "suggestion": "Check if ComfyUI is running and required models are loaded.",
        }), 502
    except Exception as exc:
        return jsonify({
            "error": f"Connection error: {exc}",
            "code": "comfyui_connection_failed",
            "suggestion": "Make sure ComfyUI is started at the configured URL.",
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


@simple_blueprint.route("/api/simple/runs/<int:run_id>", methods=["GET"])
def simple_get_run(run_id: int):
    """Check execution status of a Simple Mode generation run."""
    wf_store = _workflow_store()
    try:
        client = _client()
        exec_service = WorkflowExecutionService(store=wf_store, client=client)
        run = exec_service.refresh(run_id)
    except Exception:
        run = wf_store.get_run(run_id)

    # Resolve live output assets
    live_assets = []
    if run.output_asset_ids:
        conn = database.get_conn()
        try:
            for asset_id in run.output_asset_ids:
                row = conn.execute(
                    "SELECT id, filename, width, height FROM images WHERE id = ?",
                    (asset_id,),
                ).fetchone()
                if row:
                    live_assets.append({
                        "id": row["id"],
                        "filename": row["filename"],
                        "preview_url": f"/api/preview/{row['id']}",
                        "thumbnail_url": f"/api/thumbnail/{row['id']}",
                        "width": row["width"],
                        "height": row["height"],
                    })
        finally:
            conn.close()

    return jsonify({
        "run": run.model_dump(mode="json"),
        "status": run.status,
        "outputs": live_assets,
        "is_complete": run.status in {"completed", "failed", "cancelled"},
    })


@simple_blueprint.route("/api/simple/runs/<int:run_id>/cancel", methods=["POST"])
def simple_cancel_run(run_id: int):
    wf_store = _workflow_store()
    try:
        client = _client()
        exec_service = WorkflowExecutionService(store=wf_store, client=client)
        run = exec_service.cancel(run_id)
        return jsonify({"ok": True, "run": run.model_dump(mode="json")})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


# Persistent AI Assistant sessions memory in-process / SQLite
@simple_blueprint.route("/api/simple/assistant/chat", methods=["POST"])
def simple_assistant_chat():
    """Handles conversational prompt refinement in AI assistant modal."""
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    profile_id = str(data.get("profile_id", "realism"))
    history = data.get("history", [])

    if not message:
        return jsonify({"error": "Message is required"}), 400

    profile = APPROVED_PROFILES.get(profile_id, APPROVED_PROFILES["realism"])
    ai_profiles = _list_ai_profiles()
    text_profile = None
    for p in ai_profiles:
        if "text" in p.get("roles", []):
            text_profile = p
            break


    if not text_profile:
        return jsonify({
            "error": "No AI text profile configured. Please add an AI provider in Settings -> Integrations.",
            "code": "no_ai_profile",
        }), 400

    try:
        from app.ai.transport import run_openai_compatible_chat
        system_prompt = (
            f"You are an expert prompt assistant for ComfyUI image generation focusing on the '{profile.name}' model.\n"
            f"Model characteristics: {profile.description}\n"
            f"Target prompt style: {profile.prompt_family.value.upper()}.\n"
            "Help the user brainstorm, refine, or translate their visual ideas into evocative, high-quality image prompts.\n"
            "When suggesting a ready-to-use prompt, format it clearly in a code block or tag so the user can easily copy or apply it."
        )
        messages = [{"role": "system", "content": system_prompt}]
        for h in history[-8:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        messages.append({"role": "user", "content": message})

        ai_store = _ai_profile_store()
        api_key = ai_store.resolve_api_key(text_profile)
        response = run_openai_compatible_chat(
            profile=text_profile,
            messages=messages,
            api_key=api_key,
        )
        reply_content = response.text

        return jsonify({
            "reply": reply_content,
            "profile_id": profile.id,
        })
    except Exception as exc:
        return jsonify({"error": f"AI Assistant error: {exc}"}), 500
