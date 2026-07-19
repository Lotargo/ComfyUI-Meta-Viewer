from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from .models import PromptResult, SceneSpec


ModelT = TypeVar("ModelT", bound=BaseModel)


class PromptContractError(ValueError):
    """Raised when an AI result does not satisfy a prompt-domain contract."""

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


def _parse_json_model(raw: str, model: type[ModelT], contract_name: str) -> ModelT:
    if not isinstance(raw, str) or not raw.strip():
        raise PromptContractError(
            f"The AI returned an empty {contract_name} result.",
            code="empty_result",
        )

    text = raw.strip()
    if text.startswith("```") or text.endswith("```"):
        raise PromptContractError(
            f"The AI wrapped {contract_name} in Markdown instead of returning strict JSON.",
            code="markdown_wrapped_json",
            technical_error=text[:16_000],
        )

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PromptContractError(
            f"The AI returned invalid JSON for {contract_name}.",
            code="invalid_json",
            technical_error=str(exc),
        ) from exc

    if not isinstance(payload, dict):
        raise PromptContractError(
            f"The AI returned a non-object JSON value for {contract_name}.",
            code="invalid_contract_shape",
            technical_error=type(payload).__name__,
        )

    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise PromptContractError(
            f"The AI result does not match the {contract_name} contract.",
            code="contract_validation_error",
            technical_error=str(exc)[:16_000],
        ) from exc


def parse_prompt_result(raw: str) -> PromptResult:
    return _parse_json_model(raw, PromptResult, "PromptResult")


def parse_scene_spec(raw: str) -> SceneSpec:
    return _parse_json_model(raw, SceneSpec, "SceneSpec")
