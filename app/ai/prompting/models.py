from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PromptFamily(str, Enum):
    FLUX = "flux"
    SDXL = "sdxl"
    PONY = "pony"


class PromptOperation(str, Enum):
    GENERATE = "generate"
    RECONSTRUCT = "reconstruct"
    ADAPT = "adapt"
    TRANSLATE = "translate"


class PromptScenario(str, Enum):
    PORTRAIT = "portrait"
    SINGLE_CHARACTER = "single_character"
    PRODUCT_OBJECT = "product_object"
    ARCHITECTURE_INTERIOR = "architecture_interior"
    LANDSCAPE_ENVIRONMENT = "landscape_environment"
    ILLUSTRATION_ART = "illustration_art"
    GRAPHIC_DESIGN_TEXT = "graphic_design_text"
    MULTI_CHARACTER = "multi_character"


class PromptModifier(str, Enum):
    SAFE = "safe"
    ADULT_ONLY = "adult_only"


class CapabilityStatus(str, Enum):
    SUPPORTED = "supported"
    LIMITED = "limited"
    EXPERIMENTAL = "experimental"
    UNSUPPORTED = "unsupported"
    CHECKPOINT_ONLY = "checkpoint_only"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PromptTask(StrictModel):
    family: PromptFamily
    operation: PromptOperation
    scenario: PromptScenario
    modifiers: tuple[PromptModifier, ...] = ()
    checkpoint_profile: str | None = Field(default=None, max_length=120)
    output_contract: str = Field(default="prompt_result", min_length=1, max_length=80)

    @field_validator("checkpoint_profile")
    @classmethod
    def clean_checkpoint_profile(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("output_contract")
    @classmethod
    def clean_output_contract(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("output_contract cannot be empty.")
        return cleaned

    @model_validator(mode="after")
    def validate_modifiers(self) -> "PromptTask":
        if len(set(self.modifiers)) != len(self.modifiers):
            raise ValueError("Prompt modifiers cannot be duplicated.")
        if {
            PromptModifier.SAFE,
            PromptModifier.ADULT_ONLY,
        }.issubset(self.modifiers):
            raise ValueError("safe and adult_only modifiers are mutually exclusive.")
        return self


class SceneSubject(StrictModel):
    kind: str = Field(min_length=1, max_length=120)
    position: str | None = Field(default=None, max_length=240)
    attributes: dict[str, str] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("kind")
    @classmethod
    def clean_kind(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Scene subject kind cannot be empty.")
        return cleaned


class SceneComposition(StrictModel):
    shot: str | None = Field(default=None, max_length=240)
    camera_angle: str | None = Field(default=None, max_length=240)
    background: str | None = Field(default=None, max_length=1000)


class VisibleText(StrictModel):
    text: str = Field(min_length=1, max_length=2000)
    placement: str | None = Field(default=None, max_length=500)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Visible text cannot be empty.")
        return cleaned


class SceneSpec(StrictModel):
    schema_version: Literal["1"] = "1"
    recommended_scenario: PromptScenario | None = None
    subjects: tuple[SceneSubject, ...] = ()
    composition: SceneComposition = Field(default_factory=SceneComposition)
    visible_text: tuple[VisibleText, ...] = ()
    uncertain_details: tuple[str, ...] = ()

    @field_validator("uncertain_details")
    @classmethod
    def clean_uncertain_details(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(item.strip() for item in value if item.strip())


class PromptResult(StrictModel):
    schema_version: Literal["1"] = "1"
    positive_prompt: str = Field(min_length=1, max_length=40_000)
    negative_prompt: str = Field(default="", max_length=20_000)

    @field_validator("positive_prompt")
    @classmethod
    def clean_positive_prompt(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("positive_prompt cannot be empty.")
        return cleaned

    @field_validator("negative_prompt")
    @classmethod
    def clean_negative_prompt(cls, value: str) -> str:
        return value.strip()


class InstructionSection(StrictModel):
    section_id: str = Field(min_length=1, max_length=120)
    kind: str = Field(min_length=1, max_length=80)
    version: str = Field(min_length=1, max_length=80)
    source: str = Field(min_length=1, max_length=500)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content: str = Field(min_length=1)

    @field_validator("section_id", "kind", "version", "source", "content")
    @classmethod
    def clean_required_string(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Instruction section fields cannot be empty.")
        return cleaned


class InstructionBundle(StrictModel):
    task: PromptTask
    capability_status: CapabilityStatus
    sections: tuple[InstructionSection, ...]
    versions: dict[str, str]
    warnings: tuple[str, ...] = ()

    def render(self) -> str:
        modifier_text = ", ".join(item.value for item in self.task.modifiers) or "none"
        task_block = (
            "COMPILED TASK\n"
            f"family: {self.task.family.value}\n"
            f"operation: {self.task.operation.value}\n"
            f"scenario: {self.task.scenario.value}\n"
            f"checkpoint_profile: {self.task.checkpoint_profile or 'none'}\n"
            f"modifiers: {modifier_text}\n"
            f"capability_status: {self.capability_status.value}\n"
            f"output_contract: {self.task.output_contract}"
        )
        blocks = [
            task_block,
            "INSTRUCTION PRECEDENCE\n"
            "1. Output contract and hard content boundaries.\n"
            "2. Verified checkpoint-specific overrides.\n"
            "3. Selected scenario manifest.\n"
            "4. Selected operation manifest.\n"
            "5. Family base defaults.",
        ]
        warnings_added = False
        for section in self.sections:
            if section.kind == "output_contract" and self.warnings:
                blocks.append("COMPILER WARNINGS\n" + "\n".join(self.warnings))
                warnings_added = True
            blocks.append(
                f"SECTION {section.kind.upper()}: {section.section_id} "
                f"(version {section.version})\n{section.content}"
            )
        if self.warnings and not warnings_added:
            blocks.append("COMPILER WARNINGS\n" + "\n".join(self.warnings))
        return "\n\n".join(blocks).strip() + "\n"

    def metadata(self) -> dict[str, Any]:
        return {
            "family": self.task.family.value,
            "operation": self.task.operation.value,
            "scenario": self.task.scenario.value,
            "checkpoint_profile": self.task.checkpoint_profile,
            "capability_status": self.capability_status.value,
            "versions": dict(self.versions),
            "sections": [
                {
                    "section_id": section.section_id,
                    "kind": section.kind,
                    "version": section.version,
                    "source": section.source,
                    "content_sha256": section.content_sha256,
                }
                for section in self.sections
            ],
        }
