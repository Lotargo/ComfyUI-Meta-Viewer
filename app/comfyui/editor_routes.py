from __future__ import annotations

import hashlib
import json
import time
from io import BytesIO
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, render_template, request, send_file, stream_with_context
from pydantic import ValidationError

from app import database
from app.ai.adaptation import PromptAdaptationStore
from app.ai.job_store import AIJobStore
from app.ai.prompting import PromptFamily
from app.ai.remix import RemixError, RemixPromptSource, RemixRequest, RemixService
from app.ai.resources import ModelResourceCatalog
from app.ai.translation import PromptTranslationStore
from app.config_store import ConfigStore
from app.extractor import make_display_preview_from_bytes
from app.media import media_type_for_path
from app.paths import portable_filename

from .client import ComfyUIClientError
from .civitai_downloader import (
    CIVITAI_FILTER_TYPES,
    CivitaiDownloaderError,
    CivitaiDownloaderService,
    fetch_civitai_image,
)
from .model_inspector import inspect_model_file, register_model_file
from .model_recommendations import (
    CivitaiModelRecommendationService,
    ModelRecommendationError,
)
from .workflow_compiler import (
    WorkflowCompiler,
    WorkflowCompilerError,
    WorkflowDependencyValidator,
    default_field_values,
    evaluate_template_resource,
)
from .resource_taxonomy import (
    RESOURCE_MODEL_FOLDERS,
    get_container_format,
    inventory_resource_matches,
)
from .model_scanner import BackgroundModelScanner, get_model_scanner
from .workflow_execution import WorkflowExecutionError, WorkflowExecutionService
from .workflow_inventory import cached_runtime_inventory, client_from_store
from .workflow_models import RuntimeInventory, WorkflowRun, WorkflowTemplate
from .workflow_registry import (
    MAX_TEMPLATE_BUNDLE_BYTES,
    WorkflowTemplateError,
    WorkflowTemplateRegistry,
)
from .workflow_registry_status import (
    WorkflowRegistryStatusStore,
    validate_registry_template,
)
from .workflow_store import WorkflowStore, WorkflowStoreError
from .workflow_ui_conversion import ui_workflow_needs_object_info, unwrap_ui_workflow


editor_blueprint = Blueprint("workflow_editor", __name__)


def _config_store() -> ConfigStore:
    return current_app.config["CONFIG_STORE"]


def _workflow_store() -> WorkflowStore:
    return WorkflowStore()


def _workflow_draft_payload(draft) -> dict[str, Any]:
    payload: dict[str, Any] = {"draft": draft.model_dump(mode="json")}
    if draft.ai_prompt_draft_id is None:
        return payload
    store = AIJobStore()
    prompt_draft = store.get_draft(draft.ai_prompt_draft_id)
    job = store.get(prompt_draft.job_id).job
    payload.update({
        "ai_prompt_draft": prompt_draft.model_dump(mode="json"),
        "ai_prompt_context": store.draft_context(
            prompt_draft, job
        ).model_dump(mode="json"),
    })
    if job.task.operation.value == "translate":
        payload["ai_prompt_translation"] = PromptTranslationStore().get(
            job.id
        ).model_dump(mode="json")
    elif job.task.operation.value == "adapt":
        payload["ai_prompt_adaptation"] = PromptAdaptationStore().get(
            job.id
        ).model_dump(mode="json")
    elif job.task.operation.value == "reconstruct":
        snapshot = store.get(job.id)
        if snapshot.scene_spec is not None:
            payload["ai_scene_spec"] = snapshot.scene_spec.model_dump(mode="json")
            payload["ai_scene_spec_job_id"] = job.id
    return payload


def _run_payloads(runs: list[WorkflowRun]) -> list[dict[str, Any]]:
    """Serialize runs while exposing only outputs that still exist in Library."""
    live_asset_ids = database.get_existing_asset_ids(
        asset_id
        for run in runs
        for asset_id in run.output_asset_ids
    )
    payloads: list[dict[str, Any]] = []
    for run in runs:
        payload = run.model_dump(mode="json")
        payload["output_asset_ids"] = [
            asset_id for asset_id in run.output_asset_ids if asset_id in live_asset_ids
        ]
        payloads.append(payload)
    return payloads


def _registry() -> WorkflowTemplateRegistry:
    return WorkflowTemplateRegistry(
        user_root=Path(current_app.config["UPLOAD_FOLDER"]) / "workflow_templates",
    )


def _registry_status_store() -> WorkflowRegistryStatusStore:
    return WorkflowRegistryStatusStore(
        Path(current_app.config["UPLOAD_FOLDER"]) / "workflow_templates",
    )


def _inventory() -> RuntimeInventory:
    return cached_runtime_inventory(
        _config_store(),
        catalog=ModelResourceCatalog(),
    )

from .workflow_store import WorkflowStore, WorkflowStoreError
from .workflow_ui_conversion import ui_workflow_needs_object_info, unwrap_ui_workflow


editor_blueprint = Blueprint("workflow_editor", __name__)


def _config_store() -> ConfigStore:
    return current_app.config["CONFIG_STORE"]


def _workflow_store() -> WorkflowStore:
    return WorkflowStore()


def _workflow_draft_payload(draft) -> dict[str, Any]:
    payload: dict[str, Any] = {"draft": draft.model_dump(mode="json")}
    if draft.ai_prompt_draft_id is None:
        return payload
    store = AIJobStore()
    prompt_draft = store.get_draft(draft.ai_prompt_draft_id)
    job = store.get(prompt_draft.job_id).job
    payload.update({
        "ai_prompt_draft": prompt_draft.model_dump(mode="json"),
        "ai_prompt_context": store.draft_context(
            prompt_draft, job
        ).model_dump(mode="json"),
    })
    if job.task.operation.value == "translate":
        payload["ai_prompt_translation"] = PromptTranslationStore().get(
            job.id
        ).model_dump(mode="json")
    elif job.task.operation.value == "adapt":
        payload["ai_prompt_adaptation"] = PromptAdaptationStore().get(
            job.id
        ).model_dump(mode="json")
    elif job.task.operation.value == "reconstruct":
        snapshot = store.get(job.id)
        if snapshot.scene_spec is not None:
            payload["ai_scene_spec"] = snapshot.scene_spec.model_dump(mode="json")
            payload["ai_scene_spec_job_id"] = job.id
    return payload


def _run_payloads(runs: list[WorkflowRun]) -> list[dict[str, Any]]:
    """Serialize runs while exposing only outputs that still exist in Library."""
    live_asset_ids = database.get_existing_asset_ids(
        asset_id
        for run in runs
        for asset_id in run.output_asset_ids
    )
    payloads: list[dict[str, Any]] = []
    for run in runs:
        payload = run.model_dump(mode="json")
        payload["output_asset_ids"] = [
            asset_id for asset_id in run.output_asset_ids if asset_id in live_asset_ids
        ]
        payloads.append(payload)
    return payloads


def _registry() -> WorkflowTemplateRegistry:
    return WorkflowTemplateRegistry(
        user_root=Path(current_app.config["UPLOAD_FOLDER"]) / "workflow_templates",
    )


def _registry_status_store() -> WorkflowRegistryStatusStore:
    return WorkflowRegistryStatusStore(
        Path(current_app.config["UPLOAD_FOLDER"]) / "workflow_templates",
    )


def _template_payload(template: WorkflowTemplate, inventory: RuntimeInventory) -> dict[str, Any]:
    return {
        "manifest": template.manifest.model_dump(mode="json"),
        "source": template.source,
        "defaults": default_field_values(template),
        "resource_options": _resource_options(
            template,
            inventory,
            catalog=ModelResourceCatalog(),
        ),
    }


def _remix_template_options(source: dict[str, Any]) -> list[dict[str, Any]]:
    media_type = source.get("media_type") or "image"
    options: list[dict[str, Any]] = []
    for template in _registry().list_templates():
        manifest = template.manifest
        if manifest.media_type.value != media_type:
            continue
        field_ids = {field.id for field in manifest.fields}
        if "positive_prompt" not in field_ids:
            continue
        reference_fields = [
            field.id
            for field in manifest.fields
            if field.kind == "image" and field.required
        ]
        if reference_fields and media_type != "image":
            continue
        options.append({
            "id": manifest.id,
            "name": manifest.name,
            "description": manifest.description,
            "category": manifest.category.value,
            "supported_ecosystems": [
                ecosystem.value for ecosystem in manifest.supported_ecosystems
            ],
            "requires_reference": bool(reference_fields),
            "reference_fields": reference_fields,
            "target_family": _prompt_family_for_template(template).value,
        })
    return options




from .workflow_store import WorkflowStore, WorkflowStoreError
from .workflow_ui_conversion import ui_workflow_needs_object_info, unwrap_ui_workflow


editor_blueprint = Blueprint("workflow_editor", __name__)


def _config_store() -> ConfigStore:
    return current_app.config["CONFIG_STORE"]


def _prompt_family_for_template(template: WorkflowTemplate) -> PromptFamily:
    ecosystems = {
        ecosystem.value for ecosystem in template.manifest.supported_ecosystems
    }
    if "flux_1" in ecosystems and not ecosystems.intersection({"sdxl", "pony", "illustrious"}):
        return PromptFamily.FLUX
    if "pony" in ecosystems and not ecosystems.intersection({"sdxl", "illustrious"}):
        return PromptFamily.PONY
    return PromptFamily.SDXL


def _template_supports_prompt_family(
    template: WorkflowTemplate,
    family: PromptFamily,
) -> bool:
    ecosystems = {
        ecosystem.value for ecosystem in template.manifest.supported_ecosystems
    }
    compatible = {
        PromptFamily.FLUX: {"flux_1"},
        PromptFamily.SDXL: {"sdxl", "illustrious"},
        PromptFamily.PONY: {"pony"},
    }[family]
    return bool(ecosystems.intersection(compatible))


def _resource_options(
    template: WorkflowTemplate,
    inventory: RuntimeInventory,
    *,
    catalog: ModelResourceCatalog | None = None,
) -> dict[str, list[dict[str, Any]]]:
    catalog_resources: dict[tuple[str, str], Any] = {}
    if catalog is not None:
        try:
            catalog_resources = {
                (resource.resource_type.value, resource.file_path): resource
                for resource in catalog.list_resources(only_available=True)
            }
        except Exception:
            catalog_resources = {}
    output: dict[str, list[dict[str, Any]]] = {}
    for slot_id, slot in template.manifest.resource_slots.items():
        options: dict[str, dict[str, Any]] = {}
        for resource_type in slot.accepts:
            for folder in RESOURCE_MODEL_FOLDERS.get(resource_type, ()):
                for name in inventory.models.get(folder, []):
                    if not inventory_resource_matches(folder, name, resource_type):
                        continue
                    lowered_name = name.casefold()
                    is_video_model = any(kw in lowered_name for kw in ("hunyuan", "animate", "wan", "cogvideo", "svd", "mochi", "ltx"))
                    option = options.setdefault(name, {
                        "name": name,
                        "resource_type": resource_type.value,
                        "folder": folder,
                        "format": get_container_format(name),
                        "media_type": "video" if is_video_model else "image",
                    })
                    resource = catalog_resources.get((resource_type.value, name))
                    if resource is not None:
                        issue = evaluate_template_resource(
                            template,
                            slot_id=slot_id,
                            resource=resource,
                        )
                        option.update({
                            "content_hash": resource.content_hash,
                            "display_name": resource.display_name,
                            "architecture": resource.architecture.value,
                            "prompt_family": resource.prompt_family,
                            "metadata_source": resource.metadata_source,
                            "trigger_words": list(resource.trigger_words),
                            "compatibility_status": (
                                issue.status.value
                                if issue is not None
                                else "supported"
                            ),
                            "compatibility_reason": issue.reason if issue is not None else "",
                        })
                        if resource.architecture and "video" in resource.architecture.value.lower():
                            option["media_type"] = "video"
        output[slot_id] = sorted(options.values(), key=lambda item: item["name"].casefold())
    return output


def _json_object() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise WorkflowCompilerError(
            "A JSON object is required.",
            code="invalid_editor_request",
        )
    return payload


@editor_blueprint.route("/api/editor/models/rescan", methods=["POST"])
def trigger_model_rescan():
    scanner = get_model_scanner(_config_store())
    started = scanner.trigger_rescan()
    return jsonify({
        "status": "started" if started else "already_running",
        "message": "Background model rescan started" if started else "Scan is already in progress",
    })


@editor_blueprint.route("/api/editor/models/scan_status", methods=["GET"])
def get_model_scan_status():
    scanner = get_model_scanner(_config_store())
    return jsonify(scanner.get_status())


@editor_blueprint.route("/api/editor/models/scan_stream", methods=["GET"])
def model_scan_stream():
    """SSE stream for background model scan progress."""
    def generate():
        scanner = get_model_scanner(_config_store())
        last_count = -1
        last_scanning = None
        last_file = None
        while True:
            status = scanner.get_status()
            current_count = status["scanned_count"]
            current_scanning = status["scanning"]
            current_file = status["current_file"]
            if (
                current_count != last_count
                or current_scanning != last_scanning
                or current_file != last_file
            ):
                last_count = current_count
                last_scanning = current_scanning
                last_file = current_file
                yield f"data: {json.dumps(status)}\n\n"
                if not current_scanning and current_count > 0:
                    break
            time.sleep(0.15)
    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@editor_blueprint.errorhandler(WorkflowTemplateError)
@editor_blueprint.errorhandler(WorkflowCompilerError)
@editor_blueprint.errorhandler(WorkflowStoreError)
@editor_blueprint.errorhandler(WorkflowExecutionError)
@editor_blueprint.errorhandler(RemixError)
def workflow_editor_error(error: Exception):
    code = getattr(error, "code", "workflow_editor_error")
    status = 422
    if code in {
        "asset_not_found",
        "template_not_found",
        "workflow_draft_not_found",
        "workflow_run_not_found",
    }:
        status = 404
    elif code == "template_id_conflict":
        status = 409
    payload = {"error": str(error), "code": code}
    details = getattr(error, "details", None)
    if isinstance(details, dict):
        payload.update(details)
    return jsonify(payload), status


@editor_blueprint.errorhandler(ComfyUIClientError)
def workflow_comfy_error(error: ComfyUIClientError):
    return jsonify({
        "error": str(error),
        "code": "comfyui_api_error",
        "details": error.payload,
    }), 503 if error.status is None else 502


@editor_blueprint.errorhandler(ModelRecommendationError)
def workflow_model_recommendation_error(error: ModelRecommendationError):
    return jsonify({"error": str(error), "code": "model_recommendation_error"}), 422


@editor_blueprint.errorhandler(CivitaiDownloaderError)
def workflow_civitai_downloader_error(error: CivitaiDownloaderError):
    return jsonify({"error": str(error), "code": "civitai_downloader_error"}), 422


@editor_blueprint.errorhandler(ValidationError)
def workflow_validation_error(error: ValidationError):
    first = error.errors()[0] if error.errors() else {"msg": str(error)}
    return jsonify({"error": first.get("msg", str(error)), "code": "editor_validation_error"}), 422


@editor_blueprint.route("/editor")
def workflow_editor_page():
    return render_template("workflow_editor.html")


@editor_blueprint.route("/api/editor/bootstrap", methods=["GET"])
def editor_bootstrap():
    inventory = _inventory()
    templates = _registry().list_templates()
    return jsonify({
        "templates": [_template_payload(template, inventory) for template in templates],
        "inventory": inventory.model_dump(mode="json"),
    })


@editor_blueprint.route("/api/editor/templates", methods=["GET"])
def editor_templates():
    inventory = _inventory()
    return jsonify({
        "templates": [
            _template_payload(template, inventory)
            for template in _registry().list_templates()
        ],
        "inventory": inventory.model_dump(mode="json"),
    })


@editor_blueprint.route("/api/editor/templates/<template_id>", methods=["GET", "PATCH", "DELETE"])
def editor_template(template_id: str):
    registry = _registry()
    if request.method == "PATCH":
        payload = _json_object()
        unexpected = set(payload) - {"name", "description"}
        if unexpected:
            raise WorkflowTemplateError(
                "Unsupported workflow metadata fields: " + ", ".join(sorted(unexpected)),
                code="invalid_template_update",
            )
        template = registry.update_user_template(
            template_id,
            name=payload.get("name") if "name" in payload else None,
            description=payload.get("description") if "description" in payload else None,
        )
        return jsonify(_template_payload(template, _inventory()))
    if request.method == "DELETE":
        registry.delete_user_template(template_id)
        _registry_status_store().delete(template_id)
        return jsonify({"deleted": True, "template_id": template_id})
    inventory = _inventory()
    return jsonify(_template_payload(registry.get(template_id), inventory))


@editor_blueprint.route("/api/editor/templates/<template_id>/duplicate", methods=["POST"])
def editor_template_duplicate(template_id: str):
    payload = _json_object()
    unexpected = set(payload) - {"id", "name"}
    if unexpected:
        raise WorkflowTemplateError(
            "Unsupported workflow duplicate fields: " + ", ".join(sorted(unexpected)),
            code="invalid_template_duplicate",
        )
    template = _registry().duplicate_template(
        template_id,
        duplicate_id=payload.get("id"),
        name=payload.get("name"),
    )
    return jsonify(_template_payload(template, _inventory())), 201


@editor_blueprint.route("/api/editor/templates/<template_id>/export", methods=["GET"])
def editor_template_export(template_id: str):
    registry = _registry()
    template = registry.get(template_id)
    return send_file(
        BytesIO(registry.export_bundle(template_id)),
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{template.manifest.id}.zip",
    )


@editor_blueprint.route("/api/editor/workflows", methods=["GET"])
def editor_workflow_registry():
    return jsonify({
        "workflows": _registry().list_management_entries(_registry_status_store()),
    })


@editor_blueprint.route("/api/editor/workflows/revalidate", methods=["POST"])
def editor_workflow_revalidate_all():
    registry = _registry()
    inventory = _inventory()
    status_store = _registry_status_store()
    for template in registry.list_templates():
        status_store.set(
            template.manifest.id,
            validate_registry_template(template, inventory),
        )
    return jsonify({
        "workflows": registry.list_management_entries(status_store),
        "inventory": inventory.model_dump(mode="json"),
    })


@editor_blueprint.route("/api/editor/workflows/<template_id>/revalidate", methods=["POST"])
def editor_workflow_revalidate(template_id: str):
    registry = _registry()
    inventory = _inventory()
    validation = _registry_status_store().set(
        template_id,
        validate_registry_template(registry.get(template_id), inventory),
    )
    return jsonify({
        "template_id": template_id,
        "validation": validation.model_dump(mode="json"),
        "inventory": inventory.model_dump(mode="json"),
    })


@editor_blueprint.route(
    "/api/editor/workflows/<template_id>/mapping",
    methods=["GET", "POST", "PUT"],
)
def editor_workflow_mapping(template_id: str):
    registry = _registry()
    mapping = None if request.method == "GET" else _json_mapping()
    if request.method == "PUT":
        template = registry.remap_user_template(
            template_id,
            mapping_overrides=mapping or {},
        )
        _registry_status_store().delete(template_id)
        return jsonify(_template_payload(template, _inventory()))
    plan, resolved_mapping = registry.analyze_registered_mapping(
        template_id,
        mapping_overrides=mapping,
    )
    return jsonify({
        "plan": plan.api_dict(),
        "mapping": resolved_mapping,
    })


@editor_blueprint.route("/api/editor/templates/import", methods=["POST"])
def editor_template_import():
    uploaded, data = _uploaded_template_data()
    template = _registry().import_bundle(
        uploaded.filename,
        data,
        manifest_overrides={
            key: request.form[key]
            for key in ("id", "name", "description")
            if key in request.form
        },
        mapping_overrides=_mapping_overrides(),
        object_info=_ui_workflow_object_info(uploaded.filename, data),
    )
    return jsonify(_template_payload(template, _inventory())), 201


@editor_blueprint.route("/api/editor/templates/import/analyze", methods=["POST"])
def editor_template_import_analyze():
    uploaded, data = _uploaded_template_data()
    return jsonify(_registry().analyze_import(
        uploaded.filename,
        data,
        mapping_overrides=_mapping_overrides(),
        object_info=_ui_workflow_object_info(uploaded.filename, data),
    ).api_dict())


def _uploaded_template_data():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        raise WorkflowTemplateError(
            "Choose a ComfyUI API workflow, JSON template bundle, or ZIP archive.",
            code="missing_template_bundle",
        )
    return uploaded, uploaded.stream.read(MAX_TEMPLATE_BUNDLE_BYTES + 1)


def _ui_workflow_object_info(filename: str, data: bytes) -> dict[str, Any] | None:
    if Path(filename or "").suffix.lower() != ".json":
        return None
    try:
        payload = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    ui_workflow = unwrap_ui_workflow(payload)
    if ui_workflow is None or not ui_workflow_needs_object_info(ui_workflow):
        return None
    try:
        return client_from_store(_config_store()).get_object_info()
    except ComfyUIClientError:
        return None


def _mapping_overrides() -> dict[str, Any] | None:
    raw = request.form.get("mapping")
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WorkflowTemplateError(
            "Workflow mapping must be valid JSON.",
            code="invalid_workflow_mapping",
        ) from exc
    if not isinstance(payload, dict):
        raise WorkflowTemplateError(
            "Workflow mapping must be a JSON object.",
            code="invalid_workflow_mapping",
        )
    return payload


def _json_mapping() -> dict[str, Any]:
    payload = _json_object()
    unexpected = set(payload) - {"mapping"}
    if unexpected:
        raise WorkflowTemplateError(
            "Unsupported workflow mapping fields: " + ", ".join(sorted(unexpected)),
            code="invalid_workflow_mapping",
        )
    mapping = payload.get("mapping")
    if not isinstance(mapping, dict):
        raise WorkflowTemplateError(
            "Workflow mapping must be a JSON object.",
            code="invalid_workflow_mapping",
        )
    return mapping


@editor_blueprint.route("/api/editor/drafts", methods=["POST"])
def editor_create_draft():
    payload = _json_object()
    template = _registry().get(payload.get("template_id") or "core-image")
    values = _validated_values(template, payload.get("values"))
    resources = _validated_resources(template, payload.get("resource_selections"))
    ai_prompt_draft_id = payload.get("ai_prompt_draft_id")
    if ai_prompt_draft_id is not None:
        prompt_draft = AIJobStore().get_draft(int(ai_prompt_draft_id)).draft
        values["positive_prompt"] = prompt_draft.positive_prompt
        if (
            prompt_draft.negative_prompt
            and any(field.id == "negative_prompt" for field in template.manifest.fields)
        ):
            values["negative_prompt"] = prompt_draft.negative_prompt
    draft = _workflow_store().create_draft(
        template_id=template.manifest.id,
        template_version=template.manifest.version,
        values=values,
        resource_selections=resources,
        source_asset_id=_optional_positive_int(payload.get("source_asset_id"), "source_asset_id"),
        ai_prompt_draft_id=_optional_positive_int(ai_prompt_draft_id, "ai_prompt_draft_id"),
        auto_rate=bool(payload.get("auto_rate")) if "auto_rate" in payload else False,
    )
    return jsonify(_workflow_draft_payload(draft)), 201


@editor_blueprint.route("/api/editor/drafts/<int:draft_id>", methods=["GET", "PATCH"])
def editor_draft(draft_id: int):
    store = _workflow_store()
    draft = store.get_draft(draft_id)
    template = _registry().get(draft.template_id)
    if request.method == "PATCH":
        payload = _json_object()
        unexpected = set(payload) - {"values", "resource_selections", "auto_rate"}
        if unexpected:
            raise WorkflowCompilerError(
                "Unsupported draft fields: " + ", ".join(sorted(unexpected)),
                code="invalid_editor_request",
            )
        draft = store.update_draft(
            draft.id,
            values=_validated_values(template, payload.get("values"), current=draft.values)
            if "values" in payload else None,
            resource_selections=_validated_resources(
                template,
                payload.get("resource_selections"),
                current=draft.resource_selections,
            ) if "resource_selections" in payload else None,
            auto_rate=bool(payload["auto_rate"]) if "auto_rate" in payload else None,
        )
    response_payload = _workflow_draft_payload(draft)
    response_payload["template"] = _template_payload(template, _inventory())
    return jsonify(response_payload)


@editor_blueprint.route("/api/editor/drafts/<int:draft_id>/preview", methods=["POST"])
def editor_preview(draft_id: int):
    draft = _workflow_store().get_draft(draft_id)
    template = _registry().get(draft.template_id)
    workflow = WorkflowCompiler().compile(
        template,
        values=draft.values,
        resource_selections=draft.resource_selections,
    )
    inventory = _inventory()
    report = WorkflowDependencyValidator(catalog=ModelResourceCatalog()).validate(
        template,
        resource_selections=draft.resource_selections,
        inventory=inventory,
    )
    return jsonify({
        "workflow": workflow,
        "dependencies": report.api_dict(),
        "inventory": inventory.model_dump(mode="json"),
    })


@editor_blueprint.route("/api/editor/drafts/<int:draft_id>/run", methods=["POST"])
def editor_run(draft_id: int):
    payload = request.get_json(silent=True) or {}
    store = _workflow_store()
    draft = store.get_draft(draft_id)
    template = _registry().get(draft.template_id)
    workflow = WorkflowCompiler().compile(
        template,
        values=draft.values,
        resource_selections=draft.resource_selections,
    )
    inventory = _inventory()
    report = WorkflowDependencyValidator(catalog=ModelResourceCatalog()).validate(
        template,
        resource_selections=draft.resource_selections,
        inventory=inventory,
    )
    if not report.ready:
        return jsonify({
            "error": "Workflow dependencies are not ready.",
            "code": "workflow_dependencies_missing",
            "dependencies": report.api_dict(),
        }), 409
    service = WorkflowExecutionService(
        store=store,
        client=client_from_store(_config_store(), timeout=10.0),
        registry=_registry(),
    )
    auto_rate = bool(payload.get("auto_rate")) if "auto_rate" in payload else draft.auto_rate
    run = service.queue(draft=draft, template=template, workflow=workflow, auto_rate=auto_rate)
    return jsonify({
        "run": run.model_dump(mode="json"),
        "dependencies": report.api_dict(),
    }), 202


@editor_blueprint.route("/api/editor/runs", methods=["GET"])
def editor_runs():
    try:
        limit = int(request.args.get("limit", 30))
    except (TypeError, ValueError) as exc:
        raise WorkflowCompilerError(
            "limit must be an integer.",
            code="invalid_editor_request",
        ) from exc
    runs = _workflow_store().list_runs(limit=limit)
    return jsonify({"runs": _run_payloads(runs)})


@editor_blueprint.route("/api/editor/runs/<int:run_id>", methods=["GET"])
def editor_run_status(run_id: int):
    service = WorkflowExecutionService(
        store=_workflow_store(),
        client=client_from_store(_config_store(), timeout=10.0),
        registry=_registry(),
    )
    run = service.refresh(run_id)
    return jsonify({"run": _run_payloads([run])[0]})


@editor_blueprint.route("/api/editor/runs/<int:run_id>/cancel", methods=["POST"])
def editor_cancel_run(run_id: int):
    service = WorkflowExecutionService(
        store=_workflow_store(),
        client=client_from_store(_config_store(), timeout=10.0),
        registry=_registry(),
    )
    run = service.cancel(run_id)
    return jsonify({"run": _run_payloads([run])[0]})


@editor_blueprint.route("/api/editor/inputs", methods=["POST"])
def editor_upload_input():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        raise WorkflowCompilerError(
            "Choose an image to upload.",
            code="missing_reference_image",
        )
    filename = portable_filename(uploaded.filename)
    if media_type_for_path(filename) != "image":
        raise WorkflowCompilerError(
            "Reference inputs must use a supported image format.",
            code="unsupported_reference_image",
        )
    response = client_from_store(_config_store(), timeout=15.0).upload_image(
        filename,
        uploaded.read(),
        subfolder="cmv",
    )
    subfolder = str(response.get("subfolder") or "")
    value = f"{subfolder}/{response['name']}" if subfolder else str(response["name"])
    return jsonify({"input": response, "value": value}), 201


@editor_blueprint.route("/api/editor/remix", methods=["GET", "POST"])
def editor_remix():
    payload = _json_object() if request.method == "POST" else request.args
    asset_id = _optional_positive_int(payload.get("asset_id"), "asset_id")
    if asset_id is None:
        raise WorkflowCompilerError("asset_id is required.", code="invalid_editor_request")
    source = database.get_asset_source_info(asset_id)
    if source is None:
        raise WorkflowStoreError(
            f"Asset {asset_id} was not found.",
            code="asset_not_found",
        )
    service = RemixService()
    template_options = _remix_template_options(source)
    if request.method == "GET":
        default_template_id = next(
            (
                option["id"] for option in template_options
                if option["id"] == (
                    "core-reference"
                    if source.get("media_type") == "image"
                    else "core-video"
                )
            ),
            template_options[0]["id"] if template_options else None,
        )
        prompt_sources = service.list_prompt_sources(asset_id)
        default_prompt_source = next(
            (item.key for item in prompt_sources if item.prompt_source is not RemixPromptSource.USER_EDITED),
            prompt_sources[0].key if prompt_sources else None,
        )
        return jsonify({
            "asset": {
                "id": asset_id,
                "file_name": source.get("file_name"),
                "media_type": source.get("media_type"),
                "preview_url": f"/api/preview/{asset_id}",
            },
            "prompt_sources": [item.model_dump(mode="json") for item in prompt_sources],
            "templates": template_options,
            "defaults": {
                "prompt_source_key": default_prompt_source,
                "template_id": default_template_id,
            },
        })

    if not template_options:
        raise WorkflowCompilerError(
            "No compatible workflow template is registered for this asset.",
            code="remix_template_unavailable",
        )
    compatible_ids = {option["id"] for option in template_options}
    template_id = payload.get("template_id") or next(
        (
            option["id"] for option in template_options
            if option["id"] == (
                "core-reference"
                if source.get("media_type") == "image"
                else "core-video"
            )
        ),
        template_options[0]["id"],
    )
    if template_id not in compatible_ids:
        raise WorkflowCompilerError(
            "The selected workflow template is not compatible with this asset.",
            code="remix_template_incompatible",
        )
    template = _registry().get(template_id)
    try:
        prompt_source = RemixPromptSource(
            payload.get("prompt_source") or RemixPromptSource.ORIGINAL_METADATA.value
        )
        base_prompt_source = (
            RemixPromptSource(payload["base_prompt_source"])
            if payload.get("base_prompt_source")
            else None
        )
    except ValueError as exc:
        raise WorkflowCompilerError(
            "prompt_source is not supported.",
            code="invalid_editor_request",
        ) from exc
    prompt_draft_id = _optional_positive_int(
        payload.get("prompt_draft_id"),
        "prompt_draft_id",
    )
    source_family = None
    if prompt_draft_id is not None:
        selected_source = base_prompt_source or prompt_source
        source_family = next(
            (
                option.family
                for option in service.list_prompt_sources(asset_id)
                if option.prompt_draft_id == prompt_draft_id
                and option.prompt_source is selected_source
            ),
            None,
        )
    if source_family is not None and not _template_supports_prompt_family(
        template,
        source_family,
    ):
        raise WorkflowCompilerError(
            "The selected workflow template does not support this prompt family.",
            code="remix_template_incompatible",
        )
    outcome = service.create_remix_draft(
        request=RemixRequest(
            asset_id=asset_id,
            prompt_source=prompt_source,
            base_prompt_source=base_prompt_source,
            prompt_draft_id=prompt_draft_id,
            workflow_template_id=template.manifest.id,
            target_family=source_family or _prompt_family_for_template(template),
            override_positive_prompt=payload.get("positive_prompt"),
            override_negative_prompt=payload.get("negative_prompt"),
        ),
    )
    values = default_field_values(template)
    values["positive_prompt"] = outcome.draft.draft.positive_prompt
    if (
        outcome.draft.draft.negative_prompt
        and any(field.id == "negative_prompt" for field in template.manifest.fields)
    ):
        values["negative_prompt"] = outcome.draft.draft.negative_prompt
    reference_fields = [
        field.id
        for field in template.manifest.fields
        if field.kind == "image" and field.required
    ]
    reference_input = {
        "required": bool(reference_fields),
        "prepared": False,
        "field_ids": reference_fields,
        "error": None,
    }
    if reference_fields and source.get("media_type") == "image":
        try:
            data = _asset_bytes(source)
            uploaded = client_from_store(_config_store(), timeout=15.0).upload_image(
                source["file_name"],
                data,
                subfolder="cmv/remix",
            )
            subfolder = str(uploaded.get("subfolder") or "")
            reference_value = (
                f"{subfolder}/{uploaded['name']}" if subfolder else str(uploaded["name"])
            )
            for field_id in reference_fields:
                values[field_id] = reference_value
            reference_input["prepared"] = True
        except (ComfyUIClientError, OSError) as exc:
            # The remix remains a manual draft when the runtime is offline.
            reference_input["error"] = str(exc)
    draft = _workflow_store().create_draft(
        template_id=template.manifest.id,
        template_version=template.manifest.version,
        values=values,
        resource_selections={},
        source_asset_id=asset_id,
        ai_prompt_draft_id=outcome.draft.id,
    )
    return jsonify({
        "draft": draft.model_dump(mode="json"),
        "job": outcome.job.model_dump(mode="json"),
        "prompt_draft": outcome.draft.model_dump(mode="json"),
        "prompt_source": outcome.prompt_source.value,
        "reference_input": reference_input,
        "lineage": {"parent_asset_id": asset_id},
        "editor_url": f"/editor?draft_id={draft.id}",
    }), 201


@editor_blueprint.route("/api/editor/assets/<int:asset_id>/workflow", methods=["GET"])
def editor_analyze_asset_workflow(asset_id: int):
    detail = database.get_asset_detail(asset_id)
    if detail is None:
        raise WorkflowStoreError(
            f"Asset {asset_id} was not found.",
            code="asset_not_found",
        )
    workflow = detail.workflow or detail.workflow_ui_json
    if not isinstance(workflow, dict):
        return jsonify({
            "workflow": None,
            "format": None,
            "missing_nodes": [],
            "message": "The asset does not contain a ComfyUI workflow.",
        })
    node_types, workflow_format = _workflow_node_types(workflow)
    inventory = _inventory()
    missing_nodes = sorted(node_types - set(inventory.node_types)) if inventory.online else sorted(node_types)
    return jsonify({
        "workflow": workflow,
        "format": workflow_format,
        "node_types": sorted(node_types),
        "missing_nodes": missing_nodes,
        "runtime_online": inventory.online,
        "suggested_template_id": "core-reference" if detail.media_type == "image" else "core-video",
    })


def _validated_values(
    template: WorkflowTemplate,
    raw: Any,
    *,
    current: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if raw is None:
        return dict(current or default_field_values(template))
    if not isinstance(raw, dict):
        raise WorkflowCompilerError("values must be an object.", code="invalid_editor_request")
    allowed = {field.id for field in template.manifest.fields}
    unexpected = set(raw) - allowed
    if unexpected:
        raise WorkflowCompilerError(
            "Unknown workflow fields: " + ", ".join(sorted(unexpected)),
            code="invalid_editor_request",
        )
    values = dict(current or default_field_values(template))
    values.update(raw)
    return values


def _validated_resources(
    template: WorkflowTemplate,
    raw: Any,
    *,
    current: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if raw is None:
        return dict(current or {})
    if not isinstance(raw, dict):
        raise WorkflowCompilerError(
            "resource_selections must be an object.",
            code="invalid_editor_request",
        )
    allowed = set(template.manifest.resource_slots)
    unexpected = set(raw) - allowed
    if unexpected:
        raise WorkflowCompilerError(
            "Unknown resource slots: " + ", ".join(sorted(unexpected)),
            code="invalid_editor_request",
        )
    resources = dict(current or {})
    resources.update(raw)
    return resources


def _optional_positive_int(value: Any, field: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise WorkflowCompilerError(f"{field} must be an integer.", code="invalid_editor_request")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise WorkflowCompilerError(f"{field} must be an integer.", code="invalid_editor_request") from exc
    if parsed < 1:
        raise WorkflowCompilerError(f"{field} must be positive.", code="invalid_editor_request")
    return parsed


def _asset_bytes(source: dict[str, Any]) -> bytes:
    if source.get("has_original_data"):
        data = database.get_asset_original_data(int(source["id"]))
        if data is None:
            raise OSError("Stored asset data is unavailable")
        return data
    path = source.get("path")
    if not path:
        raise OSError("Asset source path is unavailable")
    return Path(path).read_bytes()


def _workflow_node_types(workflow: dict[str, Any]) -> tuple[set[str], str]:
    if isinstance(workflow.get("nodes"), list):
        types = {
            str(node.get("type"))
            for node in workflow["nodes"]
            if isinstance(node, dict) and node.get("type")
        }
        return types, "ui"
    types = {
        str(node.get("class_type"))
        for node in workflow.values()
        if isinstance(node, dict) and node.get("class_type")
    }
    return types, "api"


@editor_blueprint.post("/api/comfyui/models/inspect")
def inspect_model_route():
    body = request.get_json(silent=True) or {}
    file_path = str(body.get("file_path") or "").strip()
    if not file_path:
        return jsonify({"error": "file_path is required."}), 400
    try:
        result = inspect_model_file(file_path, store=_config_store())
        return jsonify({
            "file_path": result.file_path,
            "file_name": result.file_name,
            "file_size_bytes": result.file_size_bytes,
            "container_format": result.container_format,
            "detected_resource_type": result.detected_resource_type.value,
            "detected_architecture": result.detected_architecture.value,
            "confidence": result.confidence,
            "recommended_folder": result.recommended_folder,
            "recommended_target_path": result.recommended_target_path,
            "metadata": result.metadata,
            "sample_tensor_keys": result.sample_tensor_keys,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@editor_blueprint.post("/api/comfyui/models/register")
def register_model_route():
    body = request.get_json(silent=True) or {}
    source_path = str(body.get("source_path") or "").strip()
    target_folder = str(body.get("target_folder") or "").strip()
    action = str(body.get("action") or "copy").strip()
    if not source_path or not target_folder:
        return jsonify({"error": "source_path and target_folder are required."}), 400
    if action not in ("copy", "link"):
        return jsonify({"error": "action must be 'copy' or 'link'."}), 400
    try:
        catalog = ModelResourceCatalog()
        res = register_model_file(
            source_path_str=source_path,
            target_folder=target_folder,
            action=action,
            store=_config_store(),
            catalog=catalog,
        )
        return jsonify(res)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@editor_blueprint.post("/api/editor/models/recommendations")
def model_recommendations_route():
    body = _json_object()
    unexpected = set(body) - {"folder", "name"}
    if unexpected:
        raise WorkflowCompilerError(
            "Unsupported recommendation fields: " + ", ".join(sorted(unexpected)),
            code="invalid_editor_request",
        )
    folder = str(body.get("folder") or "").strip()
    name = str(body.get("name") or "").strip()
    if not folder or not name:
        raise WorkflowCompilerError(
            "folder and name are required.", code="invalid_editor_request"
        )
    return jsonify(CivitaiModelRecommendationService(_config_store()).recommend(
        folder=folder,
        name=name,
    ))


# --------------------------------------------------------------------------
# Civitai model download manager
# --------------------------------------------------------------------------


def _civitai_downloader() -> CivitaiDownloaderService:
    return CivitaiDownloaderService(_config_store())


@editor_blueprint.get("/api/editor/models/civitai/filters")
def civitai_downloader_filters():
    service = _civitai_downloader()
    return jsonify({
        "model_types": list(CIVITAI_FILTER_TYPES),
        "sort_options": [
            "Most Downloaded",
            "Most Liked",
            "Newest",
            "Highest Rated",
        ],
        "folders": service.available_folders(),
        "folder_for_type": {mt: service.folder_for_type(mt) for mt in CIVITAI_FILTER_TYPES},
    })


@editor_blueprint.post("/api/editor/models/civitai/search")
def civitai_search_route():
    body = _json_object()
    allowed = {"query", "types", "page", "limit", "sort", "nsfw", "cursor"}
    unexpected = set(body) - allowed
    if unexpected:
        raise WorkflowCompilerError(
            "Unsupported search fields: " + ", ".join(sorted(unexpected)),
            code="invalid_editor_request",
        )
    page = max(1, int(body.get("page") or 1))
    limit = min(100, max(1, int(body.get("limit") or 20)))
    return jsonify(_civitai_downloader().search(
        query=str(body.get("query") or ""),
        types=str(body.get("types") or ""),
        page=page,
        limit=limit,
        sort=str(body.get("sort") or "Most Downloaded"),
        nsfw=bool(body.get("nsfw", True)),
        cursor=str(body.get("cursor") or ""),
    ))


@editor_blueprint.get("/api/editor/models/civitai/details/<int:model_id>")
def civitai_details_route(model_id: int):
    return jsonify(_civitai_downloader().details(model_id))


@editor_blueprint.get("/api/editor/models/civitai/image")
def civitai_image_proxy_route():
    url = str(request.args.get("url") or "")
    if not url.startswith("https://image.civitai.com/"):
        raise WorkflowCompilerError(
            "Only Civitai image URLs are allowed.",
            code="invalid_editor_request",
        )
    thumbnail_dir = Path(current_app.config["THUMBNAIL_FOLDER"])
    cache_dir = thumbnail_dir / "civitai"
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    cached = next(iter(cache_dir.glob(f"{digest}.*")), None)
    if cached is not None and cached.is_file() and cached.stat().st_size > 0:
        return send_file(cached)
    try:
        data = fetch_civitai_image(url)
    except CivitaiDownloaderError as exc:
        raise WorkflowCompilerError(str(exc), code="civitai_image_error") from exc
    preview = make_display_preview_from_bytes(data, max_size=640)
    if preview is None:
        raise WorkflowCompilerError(
            "Civitai returned an image that could not be decoded.",
            code="civitai_image_error",
        )
    payload, extension = preview
    cached = cache_dir / f"{digest}.{extension}"
    cached.write_bytes(payload)
    return send_file(cached)


@editor_blueprint.post("/api/editor/models/civitai/download")
def civitai_download_route():
    body = _json_object()
    allowed = {
        "model_id", "model_name", "version_id", "version_name",
        "folder", "filename", "file_type", "file_size_bytes",
    }
    unexpected = set(body) - allowed
    if unexpected:
        raise WorkflowCompilerError(
            "Unsupported download fields: " + ", ".join(sorted(unexpected)),
            code="invalid_editor_request",
        )
    required = {"model_id", "version_id", "folder", "filename"}
    missing = sorted(required - set(body))
    if missing:
        raise WorkflowCompilerError(
            "Missing download fields: " + ", ".join(missing),
            code="invalid_editor_request",
        )
    return jsonify(_civitai_downloader().start_download(
        model_id=int(body["model_id"]),
        model_name=str(body.get("model_name") or ""),
        version_id=int(body["version_id"]),
        version_name=str(body.get("version_name") or ""),
        folder=str(body["folder"]),
        filename=str(body["filename"]),
        file_type=str(body.get("file_type") or ""),
        file_size_bytes=int(body.get("file_size_bytes") or 0),
    ))


@editor_blueprint.get("/api/editor/models/civitai/downloads")
def civitai_downloads_route():
    return jsonify({"items": _civitai_downloader().list_downloads()})


@editor_blueprint.post("/api/editor/models/civitai/downloads/<int:download_id>/cancel")
def civitai_cancel_route(download_id: int):
    if not _civitai_downloader().cancel_download(download_id):
        raise CivitaiDownloaderError("Download already finished or not found.")
    return jsonify({"ok": True})


@editor_blueprint.delete("/api/editor/models/civitai/downloads/<int:download_id>")
def civitai_delete_route(download_id: int):
    if not _civitai_downloader().delete_download(download_id):
        raise CivitaiDownloaderError("Download record not found.")
    return jsonify({"ok": True})


__all__ = ["editor_blueprint"]

