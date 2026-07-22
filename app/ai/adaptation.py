from __future__ import annotations

import json
import sqlite3
from typing import Any

from pydantic import Field, field_validator

from .. import database
from .execution.base import PromptExecutionOutcome
from .execution.router import ExecutionRouter
from .prompting import PromptFamily, PromptOperation, PromptTask
from .prompting.models import StrictModel
from .translation import PromptText, PromptTranslationStore


class PromptAdaptationError(RuntimeError):
    def __init__(self, message: str, *, code: str):
        self.code = code
        super().__init__(message)


class PromptAdaptationOutcome(StrictModel):
    execution: PromptExecutionOutcome
    source_prompt: PromptText
    adapted_prompt: PromptText
    target_family: PromptFamily
    checkpoint_profile: str | None = None


class PromptAdaptationService:
    """Transform prompt structure specifically for chosen model family profiles (Flux, SDXL, Pony)."""

    def __init__(
        self,
        *,
        router: ExecutionRouter | None = None,
        translation_store: PromptTranslationStore | None = None,
    ):
        self.router = router or ExecutionRouter()
        self.translation_store = translation_store or PromptTranslationStore()

    def adapt(
        self,
        *,
        profile: dict[str, Any],
        task: PromptTask,
        source: PromptText,
        target_family: PromptFamily | str,
        checkpoint_profile: str | None = None,
        api_key: str | None = None,
        asset_id: int | None = None,
    ) -> PromptAdaptationOutcome:
        if task.operation is not PromptOperation.ADAPT:
            raise PromptAdaptationError(
                "Family adaptation requires operation='adapt'; language translation is a separate task.",
                code="invalid_adaptation_operation",
            )

        family_enum = (
            PromptFamily(target_family)
            if isinstance(target_family, str) and target_family in PromptFamily._value2member_map_
            else task.family
        )

        adapted_task = task.model_copy(
            update={
                "family": family_enum,
                "checkpoint_profile": checkpoint_profile or task.checkpoint_profile,
            }
        )

        user_input = (
            f"TARGET FAMILY PROFILE\n{family_enum.value}\n\n"
            f"CHECKPOINT PROFILE\n{checkpoint_profile or 'default'}\n\n"
            f"SOURCE PROMPT JSON\n"
            + json.dumps(source.model_dump(mode="json"), ensure_ascii=False)
        )

        execution = self.router.execute(
            profile=profile,
            task=adapted_task,
            user_input=user_input,
            api_key=api_key,
            asset_id=asset_id,
        )

        adapted_prompt = PromptText(
            positive_prompt=execution.result.positive_prompt,
            negative_prompt=execution.result.negative_prompt,
        )

        # Optionally save adaptation payload to translations / drafts table if desired
        try:
            self.translation_store.save(
                job_id=execution.job_id,
                source=source,
                translated=adapted_prompt,
                target_language=f"adapt:{family_enum.value}",
                source_language="auto",
            )
        except Exception:
            # If translation save fails due to custom language label validation, continue cleanly
            pass

        return PromptAdaptationOutcome(
            execution=execution,
            source_prompt=source,
            adapted_prompt=adapted_prompt,
            target_family=family_enum,
            checkpoint_profile=checkpoint_profile,
        )


__all__ = [
    "PromptAdaptationError",
    "PromptAdaptationOutcome",
    "PromptAdaptationService",
]
