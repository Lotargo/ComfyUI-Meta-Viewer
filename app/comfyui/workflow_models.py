from __future__ import annotations

import copy
from enum import Enum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from app.ai.prompting.models import StrictModel
from app.ai.resources import CompatibilityStatus, ModelEcosystem, ResourceType


CURRENT_WORKFLOW_MANIFEST_SCHEMA_VERSION = "2"


class WorkflowCategory(str, Enum):
    SIMPLE = "simple"
    REFERENCE = "reference"
    VIDEO = "video"
    ADVANCED = "advanced"
    INPAINT = "inpaint"
    CONTROLNET = "controlnet"
    UPSCALE = "upscale"

    @classmethod
    def _missing_(cls, value: object) -> "WorkflowCategory":
        normalized = str(value).strip().casefold()
        aliases = {
            "inpaint": cls.INPAINT,
            "inpainting": cls.INPAINT,
            "controlnet": cls.CONTROLNET,
            "pose": cls.CONTROLNET,
            "upscale": cls.UPSCALE,
        }
        return aliases.get(normalized, cls.ADVANCED)


class WorkflowMediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class LoaderFamily(str, Enum):
    CHECKPOINT = "checkpoint"
    SEPARATE_COMPONENTS = "separate_components"
    GGUF = "gguf"
    HYBRID = "hybrid"
    CUSTOM = "custom"


class ComponentMode(str, Enum):
    EMBEDDED = "embedded"
    REQUIRED = "required"
    OPTIONAL = "optional"
    NOT_APPLICABLE = "not_applicable"


class ComponentPolicy(StrictModel):
    clip: ComponentMode
    vae: ComponentMode


class NodeInputBinding(StrictModel):
    node_id: str = Field(min_length=1, max_length=120)
    input: str = Field(min_length=1, max_length=120)


class ResourceBinding(StrictModel):
    kind: Literal["auto", "node_input", "lora_chain"] = "auto"
    node_id: str | None = Field(default=None, max_length=120)
    input: str | None = Field(default=None, max_length=120)
    source_node_id: str | None = Field(default=None, max_length=120)
    model_output: int = Field(default=0, ge=0, le=32)
    clip_output: int = Field(default=1, ge=0, le=32)

    @model_validator(mode="after")
    def validate_binding(self) -> "ResourceBinding":
        if self.kind == "node_input" and (not self.node_id or not self.input):
            raise ValueError("node_input resource binding requires node_id and input")
        if self.kind == "lora_chain" and not self.source_node_id:
            raise ValueError("lora_chain resource binding requires source_node_id")
        return self


class ResourceSlotManifest(StrictModel):
    label: str = Field(min_length=1, max_length=160)
    accepts: list[ResourceType] = Field(min_length=1)
    required: bool = True
    multiple: bool = False
    description: str = Field(default="", max_length=500)
    binding: ResourceBinding = Field(default_factory=ResourceBinding)


class EditorOption(StrictModel):
    value: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=200)


class EditorFieldManifest(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    label: str = Field(min_length=1, max_length=160)
    kind: Literal["text", "textarea", "number", "seed", "select", "image"]
    section: str = Field(default="General", min_length=1, max_length=80)
    default: Any = None
    required: bool = False
    advanced: bool = False
    hidden: bool = False
    description: str = Field(default="", max_length=500)
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = Field(default=None, gt=0)
    options: list[EditorOption] = Field(default_factory=list)
    bindings: list[NodeInputBinding] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_field(self) -> "EditorFieldManifest":
        if self.kind == "select" and not self.options:
            raise ValueError(f"select field '{self.id}' requires options")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError(f"field '{self.id}' minimum exceeds maximum")
        return self


class WorkflowTemplateManifest(StrictModel):
    schema_version: Literal["2"] = "2"
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,79}$")
    name: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=40)
    category: WorkflowCategory
    media_type: WorkflowMediaType
    supported_ecosystems: list[ModelEcosystem] = Field(min_length=1, max_length=16)
    loader_family: LoaderFamily
    component_policy: ComponentPolicy
    workflow: str = Field(default="workflow.json", min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    preview: str | None = Field(default=None, max_length=200)
    capability_notes: list[str] = Field(default_factory=list, max_length=32)
    limitation_notes: list[str] = Field(default_factory=list, max_length=32)
    required_nodes: list[str] = Field(default_factory=list)
    resource_slots: dict[str, ResourceSlotManifest] = Field(default_factory=dict)
    fields: list[EditorFieldManifest] = Field(default_factory=list)
    output_nodes: list[str] = Field(min_length=1)

    @field_validator("required_nodes", "output_nodes")
    @classmethod
    def unique_node_ids(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return list(dict.fromkeys(cleaned))

    @field_validator("capability_notes", "limitation_notes")
    @classmethod
    def clean_notes(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if any(len(item) > 500 for item in cleaned):
            raise ValueError("workflow template notes cannot exceed 500 characters")
        return list(dict.fromkeys(cleaned))

    @field_validator("supported_ecosystems")
    @classmethod
    def unique_ecosystems(cls, value: list[ModelEcosystem]) -> list[ModelEcosystem]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_unique_fields(self) -> "WorkflowTemplateManifest":
        field_ids = [field.id for field in self.fields]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("workflow template field IDs must be unique")
        slot_types = {
            resource_type
            for slot in self.resource_slots.values()
            for resource_type in slot.accepts
        }
        if self.loader_family is LoaderFamily.CHECKPOINT and ResourceType.CHECKPOINT not in slot_types:
            raise ValueError("checkpoint loader family requires a checkpoint resource slot")
        if self.loader_family is LoaderFamily.SEPARATE_COMPONENTS and ResourceType.DIFFUSION_MODEL not in slot_types:
            raise ValueError("separate_components loader family requires a diffusion_model resource slot")
        if self.loader_family is LoaderFamily.GGUF and not slot_types.intersection({
            ResourceType.DIFFUSION_MODEL_GGUF,
            ResourceType.TEXT_ENCODER_GGUF,
        }):
            raise ValueError("gguf loader family requires a GGUF resource slot")
        self._validate_component_policy("clip", {
            ResourceType.TEXT_ENCODER,
            ResourceType.TEXT_ENCODER_GGUF,
        })
        self._validate_component_policy("vae", {ResourceType.VAE})
        return self

    def _validate_component_policy(self, component: str, accepted: set[ResourceType]) -> None:
        mode = getattr(self.component_policy, component)
        matching = [
            slot
            for slot in self.resource_slots.values()
            if accepted.intersection(slot.accepts)
        ]
        if mode is ComponentMode.REQUIRED and not any(slot.required for slot in matching):
            raise ValueError(f"required {component} policy requires a required resource slot")
        if mode is ComponentMode.OPTIONAL and not matching:
            raise ValueError(f"optional {component} policy requires a resource slot")
        if mode in {ComponentMode.EMBEDDED, ComponentMode.NOT_APPLICABLE} and any(
            slot.required for slot in matching
        ):
            raise ValueError(f"{mode.value} {component} policy conflicts with a required resource slot")


def migrate_workflow_manifest(payload: Any) -> Any:
    """Upgrade supported legacy manifests without weakening schema-v2 validation."""
    if not isinstance(payload, dict):
        return payload
    migrated = copy.deepcopy(payload)
    version = str(migrated.get("schema_version") or "1").strip()
    if version == CURRENT_WORKFLOW_MANIFEST_SCHEMA_VERSION:
        return migrated
    if version != "1":
        return migrated

    slot_types: set[ResourceType] = set()
    slots = migrated.get("resource_slots")
    if isinstance(slots, dict):
        for slot in slots.values():
            if not isinstance(slot, dict):
                continue
            accepts = slot.get("accepts")
            if not isinstance(accepts, list):
                continue
            for value in accepts:
                try:
                    slot_types.add(ResourceType(value))
                except ValueError:
                    continue

    if slot_types.intersection({
        ResourceType.DIFFUSION_MODEL_GGUF,
        ResourceType.TEXT_ENCODER_GGUF,
    }):
        loader_family = LoaderFamily.GGUF
    elif ResourceType.CHECKPOINT in slot_types and ResourceType.DIFFUSION_MODEL in slot_types:
        loader_family = LoaderFamily.HYBRID
    elif ResourceType.CHECKPOINT in slot_types:
        loader_family = LoaderFamily.CHECKPOINT
    elif ResourceType.DIFFUSION_MODEL in slot_types:
        loader_family = LoaderFamily.SEPARATE_COMPONENTS
    else:
        loader_family = LoaderFamily.CUSTOM

    def component_mode(accepted: set[ResourceType]) -> ComponentMode:
        matching: list[dict[str, Any]] = []
        if isinstance(slots, dict):
            for slot in slots.values():
                if not isinstance(slot, dict) or not isinstance(slot.get("accepts"), list):
                    continue
                normalized: set[ResourceType] = set()
                for value in slot["accepts"]:
                    try:
                        normalized.add(ResourceType(value))
                    except ValueError:
                        continue
                if accepted.intersection(normalized):
                    matching.append(slot)
        if not matching:
            return ComponentMode.EMBEDDED
        return (
            ComponentMode.REQUIRED
            if any(bool(slot.get("required", True)) for slot in matching)
            else ComponentMode.OPTIONAL
        )

    migrated.update({
        "schema_version": CURRENT_WORKFLOW_MANIFEST_SCHEMA_VERSION,
        "supported_ecosystems": migrated.get("supported_ecosystems") or [ModelEcosystem.OTHER.value],
        "loader_family": migrated.get("loader_family") or loader_family.value,
        "component_policy": migrated.get("component_policy") or {
            "clip": component_mode({
                ResourceType.TEXT_ENCODER,
                ResourceType.TEXT_ENCODER_GGUF,
            }).value,
            "vae": component_mode({ResourceType.VAE}).value,
        },
        "capability_notes": migrated.get("capability_notes") or [],
        "limitation_notes": migrated.get("limitation_notes") or [
            "Migrated from manifest schema v1; ecosystem compatibility requires review."
        ],
    })
    return migrated


class WorkflowTemplate(StrictModel):
    manifest: WorkflowTemplateManifest
    workflow: dict[str, Any]
    source: Literal["builtin", "user"] = "builtin"


class WorkflowRegistryValidation(StrictModel):
    status: Literal["ready", "warning", "invalid", "expert", "partially_mapped"]
    reason: str = Field(default="", max_length=1000)
    last_validated_at: str | None = None
    inventory_fingerprint: str | None = Field(default=None, max_length=64)
    runtime_source: Literal["api", "filesystem", "none"] = "none"


class ResourceSelection(StrictModel):
    name: str = Field(min_length=1, max_length=1000)
    strength_model: float = Field(default=1.0, ge=-5.0, le=5.0)
    strength_clip: float = Field(default=1.0, ge=-5.0, le=5.0)


class MissingResource(StrictModel):
    slot: str
    label: str
    accepts: list[ResourceType]
    requested: list[str] = Field(default_factory=list)
    reason: str


class CompatibilityIssue(StrictModel):
    slot: str
    resource_name: str
    status: CompatibilityStatus
    reason: str


class DependencyReport(StrictModel):
    runtime_online: bool = False
    runtime_error: str | None = None
    missing_nodes: list[str] = Field(default_factory=list)
    missing_resources: list[MissingResource] = Field(default_factory=list)
    compatibility_issues: list[CompatibilityIssue] = Field(default_factory=list)

    @property
    def ready(self) -> bool:
        incompatible = any(
            issue.status is CompatibilityStatus.INCOMPATIBLE
            for issue in self.compatibility_issues
        )
        return (
            self.runtime_online
            and not self.missing_nodes
            and not self.missing_resources
            and not incompatible
        )

    def api_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["ready"] = self.ready
        return data


class RuntimeInventory(StrictModel):
    online: bool = False
    error: str | None = None
    node_types: list[str] = Field(default_factory=list)
    models: dict[str, list[str]] = Field(default_factory=dict)
    source: Literal["api", "filesystem", "none"] = "none"


class WorkflowDraft(StrictModel):
    id: int
    template_id: str
    template_version: str
    values: dict[str, Any]
    resource_selections: dict[str, Any]
    source_asset_id: int | None = None
    ai_prompt_draft_id: int | None = None
    auto_rate: bool = False
    status: Literal["editing", "queued", "completed", "failed", "cancelled"]
    created_at: str
    updated_at: str


class WorkflowRun(StrictModel):
    id: int
    draft_id: int
    prompt_id: str
    client_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    auto_rate: bool = False
    progress: float | None = None
    queue_position: int | None = None
    current_node: str | None = None
    error: dict[str, Any] | None = None
    output_refs: list[dict[str, Any]] = Field(default_factory=list)
    output_asset_ids: list[int] = Field(default_factory=list)
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None


__all__ = [
    "CURRENT_WORKFLOW_MANIFEST_SCHEMA_VERSION",
    "CompatibilityIssue",
    "ComponentMode",
    "ComponentPolicy",
    "DependencyReport",
    "EditorFieldManifest",
    "EditorOption",
    "LoaderFamily",
    "MissingResource",
    "NodeInputBinding",
    "ResourceBinding",
    "ResourceSelection",
    "ResourceSlotManifest",
    "RuntimeInventory",
    "WorkflowCategory",
    "WorkflowDraft",
    "WorkflowMediaType",
    "WorkflowRun",
    "WorkflowRegistryValidation",
    "WorkflowTemplate",
    "WorkflowTemplateManifest",
    "migrate_workflow_manifest",
]
