from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import ValidationError

from .workflow_models import WorkflowTemplate, WorkflowTemplateManifest


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
                template = self._load_from_manifest(manifest_path, source=source)
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

    def get(self, template_id: str) -> WorkflowTemplate:
        clean_id = str(template_id).strip()
        for template in self.list_templates():
            if template.manifest.id == clean_id:
                return template
        raise WorkflowTemplateError(
            f"Workflow template '{clean_id}' was not found.",
            code="template_not_found",
        )

    def import_bundle(self, filename: str, data: bytes) -> WorkflowTemplate:
        if self.user_root is None:
            raise WorkflowTemplateError(
                "User workflow template storage is not configured.",
                code="template_storage_unavailable",
            )
        if not data:
            raise WorkflowTemplateError("Template bundle is empty.", code="empty_template_bundle")
        if len(data) > MAX_TEMPLATE_BUNDLE_BYTES:
            raise WorkflowTemplateError(
                "Template bundle exceeds the 20 MB limit.",
                code="template_bundle_too_large",
            )

        suffix = Path(filename or "template.json").suffix.lower()
        if suffix == ".zip":
            manifest_data, workflow_data, preview = self._read_zip_bundle(data)
        elif suffix == ".json":
            manifest_data, workflow_data, preview = self._read_json_bundle(data)
        else:
            raise WorkflowTemplateError(
                "Import a JSON template bundle or ZIP archive.",
                code="unsupported_template_bundle",
            )

        manifest = self._validate_manifest(manifest_data)
        self._validate_workflow(workflow_data)
        if any(item.manifest.id == manifest.id and item.source == "builtin" for item in self.list_templates()):
            raise WorkflowTemplateError(
                f"Template ID '{manifest.id}' is reserved by a built-in template.",
                code="template_id_conflict",
            )

        template_dir = self.user_root / manifest.id
        template_dir.mkdir(parents=True, exist_ok=True)
        workflow_name = Path(manifest.workflow).name
        if workflow_name != manifest.workflow:
            manifest = manifest.model_copy(update={"workflow": workflow_name})

        self._write_json(template_dir / "manifest.json", manifest.model_dump(mode="json"))
        self._write_json(template_dir / workflow_name, workflow_data)
        if preview is not None and manifest.preview:
            preview_name = Path(manifest.preview).name
            if preview_name == manifest.preview:
                (template_dir / preview_name).write_bytes(preview)
        return self._load_from_manifest(template_dir / "manifest.json", source="user")

    def _load_from_manifest(self, path: Path, *, source: str) -> WorkflowTemplate:
        try:
            manifest_payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowTemplateError(
                f"Cannot read workflow manifest {path}: {exc}",
                code="invalid_template_manifest",
            ) from exc
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
            return WorkflowTemplateManifest.model_validate(payload)
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
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkflowTemplateError(
                f"Template JSON is invalid: {exc}",
                code="invalid_template_bundle",
            ) from exc
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
                manifest_model = WorkflowTemplateManifest.model_validate(manifest)
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
