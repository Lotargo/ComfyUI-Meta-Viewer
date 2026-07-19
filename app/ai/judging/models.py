from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class IntentJudgeContractError(ValueError):
    """Raised when an AI judge response does not satisfy the intent rubric contract."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        technical_error: str | None = None,
    ):
        self.code = code
        self.technical_error = technical_error
        super().__init__(message)


class StrictJudgeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IntentJudgeScores(StrictJudgeModel):
    intent_fidelity: int = Field(ge=0, le=20)
    useful_visual_expansion: int = Field(ge=0, le=20)
    atmosphere_translation: int = Field(ge=0, le=15)
    composition_and_camera: int = Field(ge=0, le=10)
    lighting: int = Field(ge=0, le=10)
    environment_and_materials: int = Field(ge=0, le=10)
    coherence_and_model_fit: int = Field(ge=0, le=10)
    restraint_and_consistency: int = Field(ge=0, le=5)

    @property
    def total(self) -> int:
        return sum(
            (
                self.intent_fidelity,
                self.useful_visual_expansion,
                self.atmosphere_translation,
                self.composition_and_camera,
                self.lighting,
                self.environment_and_materials,
                self.coherence_and_model_fit,
                self.restraint_and_consistency,
            )
        )


class IntentJudgeResult(StrictJudgeModel):
    schema_version: Literal["1"] = "1"
    scores: IntentJudgeScores
    strengths: tuple[str, ...] = Field(default_factory=tuple, max_length=5)
    weaknesses: tuple[str, ...] = Field(default_factory=tuple, max_length=5)
    rationale: str = Field(min_length=1, max_length=2_000)

    @field_validator("strengths", "weaknesses")
    @classmethod
    def _clean_items(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(value.strip() for value in values if value.strip())
        if len(cleaned) != len(values):
            raise ValueError("Judge list items must be non-empty strings.")
        return cleaned

    @field_validator("rationale")
    @classmethod
    def _clean_rationale(cls, value: str) -> str:
        return value.strip()

    @property
    def total(self) -> int:
        return self.scores.total

    @property
    def verdict(self) -> Literal["pass", "warn", "fail"]:
        if self.total >= 80:
            return "pass"
        if self.total >= 65:
            return "warn"
        return "fail"


def parse_intent_judge_result(raw: str) -> IntentJudgeResult:
    if not isinstance(raw, str) or not raw.strip():
        raise IntentJudgeContractError(
            "The AI judge returned an empty result.",
            code="empty_judge_result",
        )
    text = raw.strip()
    if text.startswith("```") or text.endswith("```"):
        raise IntentJudgeContractError(
            "The AI judge wrapped its result in Markdown instead of returning strict JSON.",
            code="markdown_wrapped_json",
            technical_error=text[:16_000],
        )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IntentJudgeContractError(
            "The AI judge returned invalid JSON.",
            code="invalid_judge_json",
            technical_error=str(exc),
        ) from exc
    if not isinstance(payload, dict):
        raise IntentJudgeContractError(
            "The AI judge returned a non-object JSON value.",
            code="invalid_judge_shape",
            technical_error=type(payload).__name__,
        )
    try:
        return IntentJudgeResult.model_validate(payload)
    except ValidationError as exc:
        raise IntentJudgeContractError(
            "The AI judge result does not match the intent rubric contract.",
            code="judge_contract_validation_error",
            technical_error=str(exc)[:16_000],
        ) from exc
