from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .resource_taxonomy import RESOURCE_MODEL_FOLDERS, inventory_resource_matches
from .workflow_models import (
    LoaderFamily,
    RuntimeInventory,
    WorkflowRegistryValidation,
    WorkflowTemplate,
)


class WorkflowRegistryStatusStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.path = self.root / "_registry_status.json"

    def get(self, template_id: str) -> WorkflowRegistryValidation:
        payload = self._read().get(template_id)
        if isinstance(payload, dict):
            try:
                return WorkflowRegistryValidation.model_validate(payload)
            except ValueError:
                pass
        return WorkflowRegistryValidation(
            status="warning",
            reason="Not validated against a ComfyUI inventory yet.",
        )

    def set(
        self,
        template_id: str,
        validation: WorkflowRegistryValidation,
    ) -> WorkflowRegistryValidation:
        payload = self._read()
        payload[template_id] = validation.model_dump(mode="json")
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return validation

    def delete(self, template_id: str) -> None:
        payload = self._read()
        if template_id not in payload:
            return
        del payload[template_id]
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def _read(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}


def inventory_fingerprint(inventory: RuntimeInventory) -> str:
    payload = {
        "online": inventory.online,
        "source": inventory.source,
        "node_types": sorted(inventory.node_types),
        "models": {
            folder: sorted(names)
            for folder, names in sorted(inventory.models.items())
        },
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_registry_template(
    template: WorkflowTemplate,
    inventory: RuntimeInventory,
) -> WorkflowRegistryValidation:
    status = "ready"
    reason = "Required nodes and resource types are available in the current ComfyUI inventory."

    if not inventory.online:
        status = "warning"
        reason = inventory.error or "ComfyUI is offline; node compatibility could not be verified."
    else:
        missing_nodes = sorted(set(template.manifest.required_nodes) - set(inventory.node_types))
        if missing_nodes:
            status = "warning"
            reason = "Missing required node types: " + ", ".join(missing_nodes)
        else:
            missing_slots: list[str] = []
            for slot_id, slot in template.manifest.resource_slots.items():
                if not slot.required:
                    continue
                available = any(
                    inventory_resource_matches(folder, name, resource_type)
                    for resource_type in slot.accepts
                    for folder in RESOURCE_MODEL_FOLDERS.get(resource_type, ())
                    for name in inventory.models.get(folder, [])
                )
                if not available:
                    missing_slots.append(slot_id)
            if missing_slots:
                status = "warning"
                reason = "No compatible resources found for required slots: " + ", ".join(missing_slots)
            elif not template.manifest.fields or not template.manifest.resource_slots:
                status = "partially_mapped"
                reason = "The template has no editor fields or semantic resource slots."
            elif template.manifest.loader_family is LoaderFamily.CUSTOM:
                status = "expert"
                reason = "Custom loader contract is valid but requires expert review after runtime changes."

    return WorkflowRegistryValidation(
        status=status,
        reason=reason,
        last_validated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        inventory_fingerprint=inventory_fingerprint(inventory),
        runtime_source=inventory.source,
    )


__all__ = [
    "WorkflowRegistryStatusStore",
    "inventory_fingerprint",
    "validate_registry_template",
]
