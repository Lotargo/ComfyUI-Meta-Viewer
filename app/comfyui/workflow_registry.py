from __future__ import annotations

import io
import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import ValidationError

from .sampling_options import apply_builtin_sampling_options
from .workflow_import import WorkflowImportPlan, analyze_api_workflow, unwrap_api_workflow
from .workflow_models import (
    WorkflowTemplate,
    WorkflowTemplateManifest,
    migrate_workflow_manifest,
)
from .workflow_registry_status import WorkflowRegistryStatusStore
from .workflow_ui_conversion import (
    UIWorkflowConversionError,
    convert_ui_workflow,
    unwrap_ui_workflow,
)


BUILTIN_TEMPLATE_ROOT = Path(__file__).resolve().parent / "workflow_templates"
MAX_TEMPLATE_BUNDLE_BYTES = 20 * 1024 * 1024
MAX_TEMPLATE_FILE_BYTES = 10 * 1024 * 1024


class WorkflowTemplateError(RuntimeError):
    def __init__(self, message: str, *, code: str = "workflow_template_error"):
        self.code = code
        super().__init__(message)


class WorkflowTemplateRegistry:
    def __init__(
        self,
        *,
        builtin_root: str | Path = BUILTIN_TEMPLATE_ROOT,
        user_root: str | Path | None = None,
    ):
        self.builtin_root = Path(builtin_root)
        self.user_root = Path(user_root) if user_root is not None else None

    def list_templates(self) -> list[WorkflowTemplate]:
        templates: dict[str, WorkflowTemplate] = {}
        for source, root in (("builtin", self.builtin_root), ("user", self.user_root)):
            if root is None or not root.is_dir():
                continue
            for manifest_path in sorted(root.glob("*/manifest.json")):
                try:
                    template = self._load_from_manifest(manifest_path, source=source)
                except WorkflowTemplateError:
                    if source == "user":
                        continue
                    raise
                existing = templates.get(template.manifest.id)
                if existing and source == "user":
                    raise WorkflowTemplateError(
                        f"User template '{template.manifest.id}' conflicts with a built-in template.",
                        code="template_id_conflict",
                    )
                templates[template.manifest.id] = template
        return sorted(
            templates.values(),
            key=lambda item: (item.manifest.category.value, item.manifest.name.casefold()),
        )

    def list_management_entries(
        self,
        status_store: WorkflowRegistryStatusStore,
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        known_ids: set[str] = set()
        for source, root in (("builtin", self.builtin_root), ("user", self.user_root)):
            if root is None or not root.is_dir():
                continue
            for manifest_path in sorted(root.glob("*/manifest.json")):
                try:
                    template = self._load_from_manifest(manifest_path, source=source)
                    if template.manifest.id in known_ids:
                        raise WorkflowTemplateError(
                            f"Template ID '{template.manifest.id}' is already registered.",
                            code="template_id_conflict",
                        )
                    known_ids.add(template.manifest.id)
                    validation = status_store.get(template.manifest.id)
                    entries.append({
                        "id": template.manifest.id,
                        "name": template.manifest.name,
                        "description": template.manifest.description,
                        "category": template.manifest.category.value,
                        "media_type": template.manifest.media_type.value,
                        "ecosystems": [item.value for item in template.manifest.supported_ecosystems],
                        "loader_family": template.manifest.loader_family.value,
                        "source": template.source,
                        "manifest_version": template.manifest.schema_version,
                        "template_version": template.manifest.version,
                        "validation": validation.model_dump(mode="json"),
                    })
                except WorkflowTemplateError as exc:
                    fallback = self._invalid_entry_payload(manifest_path, source=source)
                    fallback["validation"] = {
                        "status": "invalid",
                        "reason": str(exc),
                        "last_validated_at": None,
                        "inventory_fingerprint": None,
                        "runtime_source": "none",
                    }
                    entries.append(fallback)
        return sorted(entries, key=lambda item: (item["source"], item["name"].casefold()))

    def update_user_template(
        self,
        template_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> WorkflowTemplate:
        template = self.get(template_id)
        if template.source != "user":
            raise WorkflowTemplateError(
                "Built-in workflow metadata cannot be edited.",
                code="builtin_template_read_only",
            )
        updates: dict[str, str] = {}
        if name is not None:
            updates["name"] = str(name).strip()
        if description is not None:
            updates["description"] = str(description).strip()
        manifest = self._validate_manifest({
            **template.manifest.model_dump(mode="json"),
            **updates,
        })
        template_dir = self._user_template_dir(template_id)
        self._write_json(template_dir / "manifest.json", manifest.model_dump(mode="json"))
        return self._load_from_manifest(template_dir / "manifest.json", source="user")

    def delete_user_template(self, template_id: str) -> None:
        if any(
            template.manifest.id == template_id
            for template in WorkflowTemplateRegistry(
                builtin_root=self.builtin_root,
                user_root=None,
            ).list_templates()
        ):
            raise WorkflowTemplateError(
                "Built-in workflows cannot be deleted.",
                code="builtin_template_read_only",
            )
        template_dir = self._user_template_dir(template_id)
        if not template_dir.is_dir():
            raise WorkflowTemplateError(
                f"Workflow template '{template_id}' was not found.",
                code="template_not_found",
            )
        try:
            shutil.rmtree(template_dir)
        except OSError as exc:
            raise WorkflowTemplateError(
                f"Cannot delete workflow template: {exc}",
                code="template_storage_error",
            ) from exc

    def _user_template_dir(self, template_id: str) -> Path:
        if self.user_root is None:
            raise WorkflowTemplateError(
                "User workflow template storage is not configured.",
                code="template_storage_unavailable",
            )
        root = self.user_root.resolve()
        candidate = (root / str(template_id)).resolve()
        if candidate.parent != root:
            raise WorkflowTemplateError(
                "Workflow template path is invalid.",
                code="invalid_template_id",
            )
        return candidate

    @staticmethod
    def _invalid_entry_payload(path: Path, *, source: str) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        template_id = path.parent.name
        return {
            "id": template_id,
            "name": str(payload.get("name") or template_id),
            "description": str(payload.get("description") or ""),
            "category": str(payload.get("category") or "unknown"),
            "media_type": str(payload.get("media_type") or "unknown"),
            "ecosystems": payload.get("supported_ecosystems") or [],
            "loader_family": str(payload.get("loader_family") or "unknown"),
            "source": "user" if source == "user" else "builtin",
            "manifest_version": str(payload.get("schema_version") or "unknown"),
            "template_version": str(payload.get("version") or "unknown"),
        }

    def get(self, template_id: str) -> WorkflowTemplate:
        clean_id = str(template_id).strip()
        for template in self.list_templates():
            if template.manifest.id == clean_id:
                return template
        raise WorkflowTemplateError(
            f"Workflow template '{clean_id}' was not found.",
            code="template_not_found",
        )

    def analyze_import(
        self,
        filename: str,
        data: bytes,
        *,
        mapping_overrides: dict[str, Any] | None = None,
        object_info: dict[str, Any] | None = None,
    ) -> WorkflowImportPlan:
        self._validate_import_data(data)
        suffix = Path(filename or "template.json").suffix.lower()
        if suffix == ".zip":
            manifest_data, workflow_data, _preview = self._read_zip_bundle(data)
            return self._bundle_plan(manifest_data, workflow_data, source_format="template_bundle")
        if suffix != ".json":
            raise WorkflowTemplateError(
                "Import a ComfyUI API workflow, JSON template bundle, or ZIP archive.",
                code="unsupported_template_bundle",
            )

        payload = self._decode_json(data)
        if isinstance(payload, dict) and payload.get("manifest") is not None:
            manifest_data, workflow_data, _preview = self._read_json_bundle(data)
            return self._bundle_plan(manifest_data, workflow_data, source_format="template_bundle")
        workflow_data = unwrap_api_workflow(payload)
        if workflow_data is None:
            ui_workflow = unwrap_ui_workflow(payload)
            if ui_workflow is not None:
                try:
                    conversion = convert_ui_workflow(ui_workflow, object_info=object_info)
                    plan = analyze_api_workflow(
                        filename,
                        conversion.workflow,
                        mapping_overrides=mapping_overrides,
                        source_format="ui_workflow",
                    )
                except UIWorkflowConversionError as exc:
                    raise WorkflowTemplateError(str(exc), code=exc.code) from exc
                return WorkflowImportPlan(
                    source_format=plan.source_format,
                    manifest=plan.manifest,
                    workflow=plan.workflow,
                    mappings=plan.mappings,
                    candidates=plan.candidates,
                    warnings=[*conversion.warnings, *plan.warnings],
                    ready=plan.ready,
                )
            if isinstance(payload, dict) and isinstance(payload.get("nodes"), list):
                raise WorkflowTemplateError(
                    "This looks like a ComfyUI UI workflow, but its links array is missing.",
                    code="invalid_ui_workflow",
                )
            raise WorkflowTemplateError(
                "JSON does not contain a ComfyUI API graph or a template bundle.",
                code="invalid_template_bundle",
            )
        self._validate_workflow(workflow_data)
        try:
            return analyze_api_workflow(
                filename,
                workflow_data,
                mapping_overrides=mapping_overrides,
            )
        except ValueError as exc:
            raise WorkflowTemplateError(
                f"Invalid workflow mapping: {exc}",
                code="invalid_workflow_mapping",
            ) from exc

    def import_bundle(
        self,
        filename: str,
        data: bytes,
        *,
        manifest_overrides: dict[str, str] | None = None,
        mapping_overrides: dict[str, Any] | None = None,
        object_info: dict[str, Any] | None = None,
    ) -> WorkflowTemplate:
        if self.user_root is None:
            raise WorkflowTemplateError(
                "User workflow template storage is not configured.",
                code="template_storage_unavailable",
            )
        plan = self.analyze_import(
            filename,
            data,
            mapping_overrides=mapping_overrides,
            object_info=object_info,
        )
        if not plan.ready:
            raise WorkflowTemplateError(
                "This workflow needs manual mapping before it can be registered: "
                + " ".join(plan.warnings),
                code="workflow_mapping_required",
            )
        manifest = plan.manifest
        if manifest_overrides:
            allowed = {
                key: str(value).strip()
                for key, value in manifest_overrides.items()
                if key in {"id", "name", "description"} and str(value).strip()
            }
            if allowed:
                manifest = self._validate_manifest({
                    **manifest.model_dump(mode="json"),
                    **allowed,
                })
        workflow_data = plan.workflow
        existing = next(
            (item for item in self.list_templates() if item.manifest.id == manifest.id),
            None,
        )
        if existing is not None:
            raise WorkflowTemplateError(
                f"Template ID '{manifest.id}' is already registered.",
                code="template_id_conflict",
            )

        template_dir = self.user_root / manifest.id
        template_dir.mkdir(parents=True, exist_ok=True)
        workflow_name = Path(manifest.workflow).name
        if workflow_name != manifest.workflow:
            manifest = manifest.model_copy(update={"workflow": workflow_name})

        self._write_json(template_dir / "manifest.json", manifest.model_dump(mode="json"))
        self._write_json(template_dir / workflow_name, workflow_data)
        preview = None
        if Path(filename or "").suffix.lower() == ".zip":
            _manifest_data, _workflow_data, preview = self._read_zip_bundle(data)
        if preview is not None and manifest.preview:
            preview_name = Path(manifest.preview).name
            if preview_name == manifest.preview:
                (template_dir / preview_name).write_bytes(preview)
        return self._load_from_manifest(template_dir / "manifest.json", source="user")

    @staticmethod
    def _validate_import_data(data: bytes) -> None:
        if not data:
            raise WorkflowTemplateError("Template bundle is empty.", code="empty_template_bundle")
        if len(data) > MAX_TEMPLATE_BUNDLE_BYTES:
            raise WorkflowTemplateError(
                "Template bundle exceeds the 20 MB limit.",
                code="template_bundle_too_large",
            )

    @classmethod
    def _bundle_plan(
        cls,
        manifest_data: Any,
        workflow_data: dict[str, Any],
        *,
        source_format: str,
    ) -> WorkflowImportPlan:
        manifest = cls._validate_manifest(manifest_data)
        cls._validate_workflow(workflow_data)
        mappings = [
            {
                "kind": "resource",
                "semantic_id": slot_id,
                "node_id": slot.binding.node_id or slot.binding.source_node_id or "auto",
                "input": slot.binding.input or slot.binding.kind,
                "confidence": "declared",
            }
            for slot_id, slot in manifest.resource_slots.items()
        ]
        mappings.extend(
            {
                "kind": "field",
                "semantic_id": field.id,
                "node_id": binding.node_id,
                "input": binding.input,
                "confidence": "declared",
            }
            for field in manifest.fields
            for binding in field.bindings
        )
        return WorkflowImportPlan(
            source_format=source_format,
            manifest=manifest,
            workflow=workflow_data,
            mappings=mappings,
            candidates={
                "samplers": [],
                "prompt_inputs": [],
                "outputs": [],
                "model_inputs": [],
            },
            warnings=[],
            ready=True,
        )

    def _load_from_manifest(self, path: Path, *, source: str) -> WorkflowTemplate:
        try:
            manifest_payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowTemplateError(
                f"Cannot read workflow manifest {path}: {exc}",
                code="invalid_template_manifest",
            ) from exc
        if source == "builtin":
            manifest_payload = apply_builtin_sampling_options(manifest_payload)
        manifest = self._validate_manifest(manifest_payload)
        workflow_path = path.parent / manifest.workflow
        try:
            workflow_payload = json.loads(workflow_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowTemplateError(
                f"Cannot read workflow graph for '{manifest.id}': {exc}",
                code="invalid_template_workflow",
            ) from exc
        self._validate_workflow(workflow_payload)
        return WorkflowTemplate(
            manifest=manifest,
            workflow=workflow_payload,
            source="user" if source == "user" else "builtin",
        )

    @staticmethod
    def _validate_manifest(payload: Any) -> WorkflowTemplateManifest:
        try:
            return WorkflowTemplateManifest.model_validate(migrate_workflow_manifest(payload))
        except ValidationError as exc:
            message = exc.errors()[0].get("msg", str(exc))
            raise WorkflowTemplateError(
                f"Invalid workflow manifest: {message}",
                code="invalid_template_manifest",
            ) from exc

    @staticmethod
    def _validate_workflow(payload: Any) -> None:
        if not isinstance(payload, dict) or not payload:
            raise WorkflowTemplateError(
                "Workflow graph must be a non-empty JSON object.",
                code="invalid_template_workflow",
            )
        for node_id, node in payload.items():
            if not isinstance(node_id, str) or not isinstance(node, dict):
                raise WorkflowTemplateError(
                    "Workflow graph must use string node IDs and object nodes.",
                    code="invalid_template_workflow",
                )
            if not isinstance(node.get("class_type"), str) or not isinstance(node.get("inputs"), dict):
                raise WorkflowTemplateError(
                    f"Workflow node '{node_id}' requires class_type and inputs.",
                    code="invalid_template_workflow",
                )

    @staticmethod
    def _read_json_bundle(data: bytes) -> tuple[Any, dict[str, Any], bytes | None]:
        payload = WorkflowTemplateRegistry._decode_json(data)
        if not isinstance(payload, dict):
            raise WorkflowTemplateError(
                "Template JSON bundle must be an object.",
                code="invalid_template_bundle",
            )
        manifest = payload.get("manifest")
        workflow = payload.get("workflow") or payload.get("workflow_data")
        if manifest is None or workflow is None:
            raise WorkflowTemplateError(
                "JSON bundle requires manifest and workflow objects.",
                code="invalid_template_bundle",
            )
        return manifest, workflow, None

    @staticmethod
    def _decode_json(data: bytes) -> Any:
        try:
            return json.loads(data.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkflowTemplateError(
                f"Template JSON is invalid: {exc}",
                code="invalid_template_bundle",
            ) from exc

    @staticmethod
    def _read_zip_bundle(data: bytes) -> tuple[Any, dict[str, Any], bytes | None]:
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise WorkflowTemplateError(
                "Template ZIP archive is invalid.",
                code="invalid_template_bundle",
            ) from exc
        with archive:
            files = [info for info in archive.infolist() if not info.is_dir()]
            for info in files:
                path = PurePosixPath(info.filename.replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts:
                    raise WorkflowTemplateError(
                        "Template archive contains an unsafe path.",
                        code="unsafe_template_bundle",
                    )
                if info.file_size > MAX_TEMPLATE_FILE_BYTES:
                    raise WorkflowTemplateError(
                        f"Template file '{info.filename}' exceeds the 10 MB limit.",
                        code="template_file_too_large",
                    )

            manifest_info = next(
                (item for item in files if PurePosixPath(item.filename).name == "manifest.json"),
                None,
            )
            if manifest_info is None:
                raise WorkflowTemplateError(
                    "Template ZIP requires manifest.json.",
                    code="invalid_template_bundle",
                )
            try:
                manifest = json.loads(archive.read(manifest_info).decode("utf-8"))
                manifest_model = WorkflowTemplateRegistry._validate_manifest(manifest)
                workflow_name = PurePosixPath(manifest_model.workflow).name
                workflow_info = next(
                    (item for item in files if PurePosixPath(item.filename).name == workflow_name),
                    None,
                )
                if workflow_info is None:
                    raise WorkflowTemplateError(
                        f"Template ZIP is missing '{workflow_name}'.",
                        code="invalid_template_bundle",
                    )
                workflow = json.loads(archive.read(workflow_info).decode("utf-8"))
            except WorkflowTemplateError:
                raise
            except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
                raise WorkflowTemplateError(
                    f"Template ZIP contains invalid JSON: {exc}",
                    code="invalid_template_bundle",
                ) from exc

            preview = None
            if manifest_model.preview:
                preview_name = PurePosixPath(manifest_model.preview).name
                preview_info = next(
                    (item for item in files if PurePosixPath(item.filename).name == preview_name),
                    None,
                )
                if preview_info is not None:
                    preview = archive.read(preview_info)
            return manifest, workflow, preview

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise WorkflowTemplateError(
                f"Cannot save workflow template: {exc}",
                code="template_storage_error",
            ) from exc


__all__ = [
    "BUILTIN_TEMPLATE_ROOT",
    "WorkflowTemplateError",
    "WorkflowTemplateRegistry",
]
