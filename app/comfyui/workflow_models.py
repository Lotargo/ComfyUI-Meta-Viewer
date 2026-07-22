from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from app.ai.prompting.models import StrictModel
from app.ai.resources import CompatibilityStatus, ResourceType


class WorkflowCategory(str, Enum):
    SIMPLE = "simple"
    REFERENCE = "reference"
    VIDEO = "video"
    ADVANCED = "advanced"


class WorkflowMediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


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
    schema_version: Literal["1"] = "1"
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,79}$")
    name: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=40)
    category: WorkflowCategory
    media_type: WorkflowMediaType
    workflow: str = Field(default="workflow.json", min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    preview: str | None = Field(default=None, max_length=200)
    required_nodes: list[str] = Field(default_factory=list)
    resource_slots: dict[str, ResourceSlotManifest] = Field(default_factory=dict)
    fields: list[EditorFieldManifest] = Field(default_factory=list)
    output_nodes: list[str] = Field(min_length=1)

    @field_validator("required_nodes", "output_nodes")
    @classmethod
    def unique_node_ids(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return list(dict.fromkeys(cleaned))

    @model_validator(mode="after")
    def validate_unique_fields(self) -> "WorkflowTemplateManifest":
        field_ids = [field.id for field in self.fields]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("workflow template field IDs must be unique")
        return self


class WorkflowTemplate(StrictModel):
    manifest: WorkflowTemplateManifest
    workflow: dict[str, Any]
    source: Literal["builtin", "user"] = "builtin"


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
    status: Literal["editing", "queued", "completed", "failed", "cancelled"]
    created_at: str
    updated_at: str


class WorkflowRun(StrictModel):
    id: int
    draft_id: int
    prompt_id: str
    client_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
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
    "CompatibilityIssue",
    "DependencyReport",
    "EditorFieldManifest",
    "EditorOption",
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
    "WorkflowTemplate",
    "WorkflowTemplateManifest",
]
