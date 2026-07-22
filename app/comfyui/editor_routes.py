from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, jsonify, render_template, request
from pydantic import ValidationError

from app import database
from app.ai.job_store import AIJobStore
from app.ai.remix import RemixPromptSource, RemixRequest, RemixService
from app.ai.resources import ModelResourceCatalog
from app.config_store import ConfigStore
from app.media import media_type_for_path
from app.paths import portable_filename

from .client import ComfyUIClientError
from .workflow_compiler import (
    RESOURCE_MODEL_FOLDERS,
    WorkflowCompiler,
    WorkflowCompilerError,
    WorkflowDependencyValidator,
    default_field_values,
)
from .workflow_execution import WorkflowExecutionError, WorkflowExecutionService
from .workflow_inventory import client_from_store, collect_runtime_inventory
from .workflow_models import RuntimeInventory, WorkflowTemplate
from .workflow_registry import (
    MAX_TEMPLATE_BUNDLE_BYTES,
    WorkflowTemplateError,
    WorkflowTemplateRegistry,
)
from .workflow_store import WorkflowStore, WorkflowStoreError


editor_blueprint = Blueprint("workflow_editor", __name__)


def _config_store() -> ConfigStore:
    return current_app.config["CONFIG_STORE"]


def _workflow_store() -> WorkflowStore:
    return WorkflowStore()


def _registry() -> WorkflowTemplateRegistry:
    return WorkflowTemplateRegistry(
        user_root=Path(current_app.config["UPLOAD_FOLDER"]) / "workflow_templates",
    )


def _inventory() -> RuntimeInventory:
    return collect_runtime_inventory(
        _config_store(),
        catalog=ModelResourceCatalog(),
    )


def _template_payload(template: WorkflowTemplate, inventory: RuntimeInventory) -> dict[str, Any]:
    return {
        "manifest": template.manifest.model_dump(mode="json"),
        "source": template.source,
        "defaults": default_field_values(template),
        "resource_options": _resource_options(template, inventory),
    }


def _resource_options(template: WorkflowTemplate, inventory: RuntimeInventory) -> dict[str, list[dict[str, str]]]:
    output: dict[str, list[dict[str, str]]] = {}
    for slot_id, slot in template.manifest.resource_slots.items():
        options: dict[str, dict[str, str]] = {}
        for resource_type in slot.accepts:
            for folder in RESOURCE_MODEL_FOLDERS.get(resource_type, ()):
                for name in inventory.models.get(folder, []):
                    options.setdefault(name, {
                        "name": name,
                        "resource_type": resource_type.value,
                        "folder": folder,
                    })
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


@editor_blueprint.errorhandler(WorkflowTemplateError)
@editor_blueprint.errorhandler(WorkflowCompilerError)
@editor_blueprint.errorhandler(WorkflowStoreError)
@editor_blueprint.errorhandler(WorkflowExecutionError)
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
    return jsonify({"error": str(error), "code": code}), status


@editor_blueprint.errorhandler(ComfyUIClientError)
def workflow_comfy_error(error: ComfyUIClientError):
    return jsonify({
        "error": str(error),
        "code": "comfyui_api_error",
        "details": error.payload,
    }), 503 if error.status is None else 502


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


@editor_blueprint.route("/api/editor/templates/<template_id>", methods=["GET"])
def editor_template(template_id: str):
    inventory = _inventory()
    return jsonify(_template_payload(_registry().get(template_id), inventory))


@editor_blueprint.route("/api/editor/templates/import", methods=["POST"])
def editor_template_import():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        raise WorkflowTemplateError(
            "Choose a JSON template bundle or ZIP archive.",
            code="missing_template_bundle",
        )
    template = _registry().import_bundle(
        uploaded.filename,
        uploaded.stream.read(MAX_TEMPLATE_BUNDLE_BYTES + 1),
    )
    return jsonify(_template_payload(template, _inventory())), 201


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
        values["negative_prompt"] = prompt_draft.negative_prompt
    draft = _workflow_store().create_draft(
        template_id=template.manifest.id,
        template_version=template.manifest.version,
        values=values,
        resource_selections=resources,
        source_asset_id=_optional_positive_int(payload.get("source_asset_id"), "source_asset_id"),
        ai_prompt_draft_id=_optional_positive_int(ai_prompt_draft_id, "ai_prompt_draft_id"),
    )
    return jsonify({"draft": draft.model_dump(mode="json")}), 201


@editor_blueprint.route("/api/editor/drafts/<int:draft_id>", methods=["GET", "PATCH"])
def editor_draft(draft_id: int):
    store = _workflow_store()
    draft = store.get_draft(draft_id)
    template = _registry().get(draft.template_id)
    if request.method == "PATCH":
        payload = _json_object()
        unexpected = set(payload) - {"values", "resource_selections"}
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
        )
    return jsonify({
        "draft": draft.model_dump(mode="json"),
        "template": _template_payload(template, _inventory()),
    })


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
    )
    run = service.queue(draft=draft, template=template, workflow=workflow)
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
    return jsonify({"runs": [run.model_dump(mode="json") for run in runs]})


@editor_blueprint.route("/api/editor/runs/<int:run_id>", methods=["GET"])
def editor_run_status(run_id: int):
    service = WorkflowExecutionService(
        store=_workflow_store(),
        client=client_from_store(_config_store(), timeout=10.0),
    )
    run = service.refresh(run_id)
    return jsonify({"run": run.model_dump(mode="json")})


@editor_blueprint.route("/api/editor/runs/<int:run_id>/cancel", methods=["POST"])
def editor_cancel_run(run_id: int):
    service = WorkflowExecutionService(
        store=_workflow_store(),
        client=client_from_store(_config_store(), timeout=10.0),
    )
    run = service.cancel(run_id)
    return jsonify({"run": run.model_dump(mode="json")})


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


@editor_blueprint.route("/api/editor/remix", methods=["POST"])
def editor_remix():
    payload = _json_object()
    asset_id = _optional_positive_int(payload.get("asset_id"), "asset_id")
    if asset_id is None:
        raise WorkflowCompilerError("asset_id is required.", code="invalid_editor_request")
    source = database.get_asset_source_info(asset_id)
    if source is None:
        raise WorkflowStoreError(
            f"Asset {asset_id} was not found.",
            code="asset_not_found",
        )
    template_id = payload.get("template_id") or (
        "core-reference" if source.get("media_type") == "image" else "core-image"
    )
    template = _registry().get(template_id)
    try:
        prompt_source = RemixPromptSource(
            payload.get("prompt_source") or RemixPromptSource.ORIGINAL_METADATA.value
        )
    except ValueError as exc:
        raise WorkflowCompilerError(
            "prompt_source is not supported.",
            code="invalid_editor_request",
        ) from exc
    outcome = RemixService().create_remix_draft(
        request=RemixRequest(
            asset_id=asset_id,
            prompt_source=prompt_source,
            workflow_template_id=template.manifest.id,
        ),
    )
    values = default_field_values(template)
    values["positive_prompt"] = outcome.draft.draft.positive_prompt
    values["negative_prompt"] = outcome.draft.draft.negative_prompt
    if template.manifest.id == "core-reference" and source.get("media_type") == "image":
        try:
            data = _asset_bytes(source)
            uploaded = client_from_store(_config_store(), timeout=15.0).upload_image(
                source["file_name"],
                data,
                subfolder="cmv/remix",
            )
            subfolder = str(uploaded.get("subfolder") or "")
            values["reference_image"] = (
                f"{subfolder}/{uploaded['name']}" if subfolder else str(uploaded["name"])
            )
        except (ComfyUIClientError, OSError):
            # The remix remains a manual draft when the runtime is offline.
            pass
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
        "prompt_draft": outcome.draft.model_dump(mode="json"),
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


__all__ = ["editor_blueprint"]
