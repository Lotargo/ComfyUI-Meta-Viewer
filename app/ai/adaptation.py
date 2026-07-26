from __future__ import annotations

import json
import sqlite3
from typing import Any, Literal

from .. import database
from .execution.base import PromptExecutionOutcome
from .execution.router import ExecutionRouter
from .prompting import PromptFamily, PromptOperation, PromptTask
from .prompting.models import StrictModel
from .translation import PromptText


class PromptAdaptationError(RuntimeError):
    def __init__(self, message: str, *, code: str):
        self.code = code
        super().__init__(message)


class PromptAdaptation(StrictModel):
    schema_version: Literal["1"] = "1"
    job_id: int
    target_family: PromptFamily
    checkpoint_profile: str | None = None
    source: PromptText
    adapted: PromptText
    created_at: str


class PromptAdaptationOutcome(StrictModel):
    execution: PromptExecutionOutcome
    adaptation: PromptAdaptation


class PromptAdaptationStore:
    def save(
        self,
        *,
        job_id: int,
        source: PromptText,
        adapted: PromptText,
        target_family: PromptFamily,
        checkpoint_profile: str | None = None,
    ) -> PromptAdaptation:
        conn = database.get_conn()
        try:
            job = conn.execute(
                """SELECT j.status, j.operation, r.positive_prompt, r.negative_prompt
                FROM ai_jobs j
                LEFT JOIN ai_results r ON r.job_id=j.id
                WHERE j.id=?""",
                (job_id,),
            ).fetchone()
            if (
                job is None
                or job["operation"] != PromptOperation.ADAPT.value
                or job["status"] not in {"waiting_for_review", "completed"}
            ):
                raise PromptAdaptationError(
                    "An adaptation can only be attached to a reviewable adapt job.",
                    code="adaptation_job_incomplete",
                )
            if (
                job["positive_prompt"] != adapted.positive_prompt
                or job["negative_prompt"] != adapted.negative_prompt
            ):
                raise PromptAdaptationError(
                    "The adapted prompt does not match the AI job result.",
                    code="adaptation_result_mismatch",
                )
            conn.execute(
                """INSERT INTO ai_prompt_adaptations (
                    job_id, schema_version, target_family, checkpoint_profile,
                    source_positive_prompt, source_negative_prompt,
                    adapted_positive_prompt, adapted_negative_prompt
                ) VALUES (?, '1', ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    target_family.value,
                    checkpoint_profile,
                    source.positive_prompt,
                    source.negative_prompt,
                    adapted.positive_prompt,
                    adapted.negative_prompt,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise PromptAdaptationError(
                f"Cannot save prompt adaptation: {exc}",
                code="adaptation_persistence_error",
            ) from exc
        finally:
            conn.close()
        return self.get(job_id)

    def get(self, job_id: int) -> PromptAdaptation:
        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM ai_prompt_adaptations WHERE job_id=?", (job_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise PromptAdaptationError(
                f"Prompt adaptation for AI job {job_id} does not exist.",
                code="adaptation_not_found",
            )
        return PromptAdaptation(
            schema_version=row["schema_version"],
            job_id=row["job_id"],
            target_family=row["target_family"],
            checkpoint_profile=row["checkpoint_profile"],
            source=PromptText(
                positive_prompt=row["source_positive_prompt"],
                negative_prompt=row["source_negative_prompt"],
            ),
            adapted=PromptText(
                positive_prompt=row["adapted_positive_prompt"],
                negative_prompt=row["adapted_negative_prompt"],
            ),
            created_at=row["created_at"],
        )


class PromptAdaptationService:
    """Transform prompt structure specifically for chosen model family profiles (Flux, SDXL, Pony)."""

    def __init__(
        self,
        *,
        router: ExecutionRouter | None = None,
        store: PromptAdaptationStore | None = None,
    ):
        self.router = router or ExecutionRouter()
        self.store = store or PromptAdaptationStore()

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

        try:
            family_enum = PromptFamily(target_family)
        except ValueError as exc:
            raise PromptAdaptationError(
                "target_family must be one of: flux, sdxl, pony.",
                code="invalid_target_family",
            ) from exc

        adapted_task = PromptTask.model_validate(
            {
                **task.model_dump(mode="json"),
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

        adaptation = self.store.save(
            job_id=execution.job_id,
            source=source,
            adapted=adapted_prompt,
            target_family=family_enum,
            checkpoint_profile=adapted_task.checkpoint_profile,
        )

        return PromptAdaptationOutcome(
            execution=execution,
            adaptation=adaptation,
        )


__all__ = [
    "PromptAdaptation",
    "PromptAdaptationError",
    "PromptAdaptationOutcome",
    "PromptAdaptationService",
    "PromptAdaptationStore",
]
