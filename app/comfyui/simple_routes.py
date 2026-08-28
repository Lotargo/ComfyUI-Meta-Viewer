from __future__ import annotations

import logging
import os
import random
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, jsonify, render_template, request
from pydantic import BaseModel

from app import database as db
from app import library as media_library
from app.ai.enhancement import PromptEnhancementService
from app.ai.profiles import AIProfileStore
from app.ai.prompting import PromptOperation, PromptScenario, PromptTask
from app.ai.reconstruction import SceneAnalysisService
from app.ai.translation import PromptText
from app.config_store import ConfigStore

from .client import ComfyUIClient, ComfyUIClientError
from .detector import detect_comfyui
from .simple_downloader import SimpleModelDownloaderError, SimpleModelDownloaderService
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


def _download_service() -> SimpleModelDownloaderService:
    return SimpleModelDownloaderService(_config_store())


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


_AMBIENT_CACHE: list[dict[str, Any]] = []
_AMBIENT_CACHE_TIME: float = 0.0
_AMBIENT_CACHE_TTL: float = 45.0


def _query_ambient_candidates() -> list[dict[str, Any]]:
    conn = db.get_conn()
    candidates: list[dict[str, Any]] = []
    seen_ids: set[int] = set()

    try:
        # Bucket 1: Favorites & Highly rated images (all-time top quality)
        starred_rows = conn.execute(
            """
            SELECT i.id, i.file_name, i.width, i.height
            FROM images i
            LEFT JOIN folders f ON f.id = i.folder_id
            WHERE i.media_type = 'image'
              AND (f.enabled = 1 OR f.id IS NULL)
              AND (i.original_data IS NOT NULL OR f.source_status NOT IN ('disabled', 'unavailable', 'reconnecting', 'error') OR f.id IS NULL)
              AND (i.is_favorite = 1 OR COALESCE(i.rating, 0) >= 3)
            ORDER BY RANDOM()
            LIMIT 90
            """
        ).fetchall()
        for r in starred_rows:
            aid = int(r["id"])
            if aid not in seen_ids:
                seen_ids.add(aid)
                candidates.append({
                    "id": aid,
                    "file_name": r["file_name"] or "",
                    "original_url": f"/api/original/{aid}",
                    "preview_url": f"/api/preview/{aid}",
                    "thumbnail_url": f"/api/thumbnail/{aid}",
                    "width": int(r["width"] or 0),
                    "height": int(r["height"] or 0),
                })
    except Exception as exc:
        logger.debug("Failed querying starred ambient images: %s", exc)

    try:
        # Bucket 2: Recent artworks (latest generations)
        recent_rows = conn.execute(
            """
            SELECT i.id, i.file_name, i.width, i.height
            FROM images i
            LEFT JOIN folders f ON f.id = i.folder_id
            WHERE i.media_type = 'image'
              AND (f.enabled = 1 OR f.id IS NULL)
              AND (i.original_data IS NOT NULL OR f.source_status NOT IN ('disabled', 'unavailable', 'reconnecting', 'error') OR f.id IS NULL)
            ORDER BY i.indexed_at DESC
            LIMIT 150
            """
        ).fetchall()
        for r in recent_rows:
            aid = int(r["id"])
            if aid not in seen_ids:
                seen_ids.add(aid)
                candidates.append({
                    "id": aid,
                    "file_name": r["file_name"] or "",
                    "original_url": f"/api/original/{aid}",
                    "preview_url": f"/api/preview/{aid}",
                    "thumbnail_url": f"/api/thumbnail/{aid}",
                    "width": int(r["width"] or 0),
                    "height": int(r["height"] or 0),
                })
    except Exception as exc:
        logger.debug("Failed querying recent ambient images: %s", exc)

    try:
        # Bucket 3: Full database random exploration (discover older artworks)
        random_rows = conn.execute(
            """
            SELECT i.id, i.file_name, i.width, i.height
            FROM images i
            LEFT JOIN folders f ON f.id = i.folder_id
            WHERE i.media_type = 'image'
              AND (f.enabled = 1 OR f.id IS NULL)
              AND (i.original_data IS NOT NULL OR f.source_status NOT IN ('disabled', 'unavailable', 'reconnecting', 'error') OR f.id IS NULL)
            ORDER BY RANDOM()
            LIMIT 150
            """
        ).fetchall()
        for r in random_rows:
            aid = int(r["id"])
            if aid not in seen_ids:
                seen_ids.add(aid)
                candidates.append({
                    "id": aid,
                    "file_name": r["file_name"] or "",
                    "original_url": f"/api/original/{aid}",
                    "preview_url": f"/api/preview/{aid}",
                    "thumbnail_url": f"/api/thumbnail/{aid}",
                    "width": int(r["width"] or 0),
                    "height": int(r["height"] or 0),
                })
    except Exception as exc:
        logger.debug("Failed querying random ambient images: %s", exc)

    return candidates


def _ambient_payload(limit: int = 72) -> list[dict[str, Any]]:
    global _AMBIENT_CACHE, _AMBIENT_CACHE_TIME
    now = time.monotonic()
    if not _AMBIENT_CACHE or (now - _AMBIENT_CACHE_TIME) > _AMBIENT_CACHE_TTL:
        try:
            candidates = _query_ambient_candidates()
            if not candidates:
                # Fallback to media_library
                page = media_library.get_assets(
                    collection="images",
                    page=1,
                    per_page=160,
                    sort_by="added",
                    sort_dir="desc",
                )
                candidates = [
                    {
                        "id": int(asset["id"]),
                        "file_name": asset.get("file_name") or "",
                        "original_url": f"/api/original/{int(asset['id'])}",
                        "preview_url": f"/api/preview/{int(asset['id'])}",
                        "thumbnail_url": asset.get("thumbnail_url") or f"/api/thumbnail/{int(asset['id'])}",
                        "width": int(asset.get("width") or 0),
                        "height": int(asset.get("height") or 0),
                    }
                    for asset in page.get("assets", [])
                    if asset.get("media_type") == "image" and asset.get("available", True)
                ]
            if candidates:
                _AMBIENT_CACHE = candidates
                _AMBIENT_CACHE_TIME = now
        except Exception as exc:
            logger.debug("Failed to load ambient library assets: %s", exc)
            if not _AMBIENT_CACHE:
                return []

    pool = list(_AMBIENT_CACHE)
    random.shuffle(pool)
    return pool[:limit]


def _inventory_or_none():
    try:
        return cached_runtime_inventory(_config_store())
    except Exception:
        return None


@simple_blueprint.route("/create")
@simple_blueprint.route("/editor")
def simple_mode_page():
    initial_models = _catalog_payload()
    initial_ambient = _ambient_payload(16)
    return render_template(
        "create.html",
        initial_models=initial_models,
        initial_ambient=initial_ambient,
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
    return jsonify({
        "profile_id": profile_id,
        "health": check_profile_health(profile, _inventory_or_none()),
    })


@simple_blueprint.route("/api/simple/models/<profile_id>/install", methods=["POST"])
def simple_install_profile(profile_id: str):
    profile = APPROVED_PROFILES.get(profile_id)
    if not profile:
        return jsonify({"error": "Model not found"}), 404

    service = _download_service()
    try:
        model_root = service.resolve_model_root()
    except SimpleModelDownloaderError as exc:
        return jsonify({
            "error": str(exc),
            "code": "comfyui_path_required",
            "open_settings": True,
        }), 409

    health = check_profile_health(profile, _inventory_or_none())
    missing_names = {
        str(item.get("filename") or "").casefold()
        for item in health.get("missing_resources", [])
    }
    queued: list[dict[str, Any]] = []
    unavailable: list[str] = []
    for dependency in profile.required_resources:
        if dependency.filename.casefold() not in missing_names:
            continue
        if not dependency.download_url:
            unavailable.append(dependency.display_name)
            continue
        try:
            queued.append(service.queue(
                profile_id=profile.id,
                display_name=dependency.display_name,
                folder=dependency.folder,
                filename=dependency.filename,
                source_url=dependency.download_url,
            ))
        except SimpleModelDownloaderError as exc:
            unavailable.append(f"{dependency.display_name}: {exc}")

    return jsonify({
        "ok": not unavailable,
        "profile_id": profile.id,
        "model_root": str(model_root),
        "downloads": queued,
        "unavailable": unavailable,
    }), 202 if queued else 200


@simple_blueprint.route("/api/simple/downloads", methods=["GET"])
def simple_downloads():
    profile_id = str(request.args.get("profile_id") or "").strip() or None
    return jsonify({"items": _download_service().list(profile_id=profile_id)})


@simple_blueprint.route("/api/simple/downloads/<int:download_id>/pause", methods=["POST"])
def simple_pause_download(download_id: int):
    try:
        return jsonify({"item": _download_service().pause(download_id)})
    except SimpleModelDownloaderError as exc:
        return jsonify({"error": str(exc)}), 404


@simple_blueprint.route("/api/simple/downloads/<int:download_id>/resume", methods=["POST"])
@simple_blueprint.route("/api/simple/downloads/<int:download_id>/retry", methods=["POST"])
def simple_resume_download(download_id: int):
    try:
        return jsonify({"item": _download_service().resume(download_id)})
    except SimpleModelDownloaderError as exc:
        return jsonify({"error": str(exc)}), 404


@simple_blueprint.route("/api/simple/downloads/<int:download_id>/cancel", methods=["POST"])
def simple_cancel_download(download_id: int):
    try:
        return jsonify({"item": _download_service().cancel(download_id)})
    except SimpleModelDownloaderError as exc:
        return jsonify({"error": str(exc)}), 404


def _pick_windows_directory(initial_path: str) -> str | None:
    powershell = shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        raise RuntimeError("PowerShell не найден, поэтому системный выбор папки недоступен.")
    script = r"""
Add-Type -AssemblyName System.Windows.Forms
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Выберите папку ComfyUI'
$dialog.ShowNewFolderButton = $false
$initial = $env:CMV_INITIAL_DIRECTORY
if ($initial -and (Test-Path -LiteralPath $initial)) { $dialog.SelectedPath = $initial }
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dialog.SelectedPath
}
"""
    env = os.environ.copy()
    env["CMV_INITIAL_DIRECTORY"] = initial_path
    result = subprocess.run(
        [powershell, "-NoProfile", "-STA", "-WindowStyle", "Hidden", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "Не удалось открыть выбор папки.").strip()
        raise RuntimeError(message)
    selected = (result.stdout or "").strip().splitlines()
    return selected[-1].strip() if selected else None


def _pick_tk_directory(initial_path: str) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # pragma: no cover - platform dependency
        raise RuntimeError("Системный выбор папки недоступен в этой сборке Python.") from exc
    root = tk.Tk()
    try:
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        selected = filedialog.askdirectory(
            title="Выберите папку ComfyUI",
            initialdir=initial_path or None,
            mustexist=True,
        )
        return str(selected).strip() or None
    finally:
        root.destroy()


@simple_blueprint.route("/api/simple/pick-comfyui-directory", methods=["POST"])
def simple_pick_comfyui_directory():
    remote = str(request.remote_addr or "")
    if remote not in {"127.0.0.1", "::1", "localhost"}:
        return jsonify({
            "error": "Выбор локальной папки доступен только при открытии приложения на этом компьютере."
        }), 403
    payload = request.get_json(silent=True) or {}
    initial_path = str(payload.get("initial_path") or "").strip()
    try:
        selected = (
            _pick_windows_directory(initial_path)
            if os.name == "nt"
            else _pick_tk_directory(initial_path)
        )
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        return jsonify({"error": str(exc), "code": "directory_picker_unavailable"}), 503
    if not selected:
        return jsonify({"cancelled": True})
    detection = detect_comfyui(selected)
    return jsonify({
        "cancelled": False,
        "path": selected,
        "detection": detection.to_dict(),
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


def _prepare_prompt(
    profile: ApprovedProfile,
    req: SimpleGenerateRequest,
) -> tuple[str, str, bool, str | None]:
    positive_prompt = req.prompt.strip()
    negative_prompt = (
        req.negative_prompt
        if req.negative_prompt is not None
        else profile.default_negative_prompt
    )
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
                        f"{positive_prompt}, {reconstructed}"
                        if positive_prompt
                        else reconstructed
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

    health = check_profile_health(profile, _inventory_or_none())
    if health["status"] == "not_installed":
        return jsonify({
            "error": "Required model components are missing.",
            "code": "model_not_installed",
            "missing_resources": health["missing_resources"],
        }), 409

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
