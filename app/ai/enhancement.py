from __future__ import annotations

import json
import re
import sqlite3
from typing import Any, Literal

from .. import database
from .execution.base import PromptExecutionOutcome
from .execution.router import ExecutionRouter
from .prompting import PromptFamily, PromptOperation, PromptResult, PromptTask
from .prompting.models import StrictModel
from .resources import ModelResource
from .translation import PromptText


class PromptEnhancementError(RuntimeError):
    def __init__(self, message: str, *, code: str):
        self.code = code
        super().__init__(message)


class PromptEnhancement(StrictModel):
    schema_version: Literal["1"] = "1"
    job_id: int
    family: PromptFamily
    checkpoint_profile: str | None = None
    wishes: str = ""
    source: PromptText
    enhanced: PromptText
    created_at: str


class PromptEnhancementOutcome(StrictModel):
    execution: PromptExecutionOutcome
    enhancement: PromptEnhancement


class PromptEnhancementStore:
    def save(
        self,
        *,
        job_id: int,
        source: PromptText,
        enhanced: PromptText,
        family: PromptFamily,
        checkpoint_profile: str | None = None,
        wishes: str = "",
    ) -> PromptEnhancement:
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
                or job["operation"] != PromptOperation.ENHANCE.value
                or job["status"] not in {"waiting_for_review", "completed"}
            ):
                raise PromptEnhancementError(
                    "An enhancement can only be attached to a reviewable enhance job.",
                    code="enhancement_job_incomplete",
                )
            if (
                job["positive_prompt"] != enhanced.positive_prompt
                or job["negative_prompt"] != enhanced.negative_prompt
            ):
                raise PromptEnhancementError(
                    "The enhanced prompt does not match the AI job result.",
                    code="enhancement_result_mismatch",
                )
            conn.execute(
                """INSERT INTO ai_prompt_enhancements (
                    job_id, schema_version, family, checkpoint_profile, wishes,
                    source_positive_prompt, source_negative_prompt,
                    enhanced_positive_prompt, enhanced_negative_prompt
                ) VALUES (?, '1', ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    family.value,
                    checkpoint_profile,
                    wishes,
                    source.positive_prompt,
                    source.negative_prompt,
                    enhanced.positive_prompt,
                    enhanced.negative_prompt,
                ),
            )
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise PromptEnhancementError(
                f"Cannot save prompt enhancement: {exc}",
                code="enhancement_persistence_error",
            ) from exc
        finally:
            conn.close()
        return self.get(job_id)

    def get(self, job_id: int) -> PromptEnhancement:
        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM ai_prompt_enhancements WHERE job_id=?", (job_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise PromptEnhancementError(
                f"Prompt enhancement for AI job {job_id} does not exist.",
                code="enhancement_not_found",
            )
        return PromptEnhancement(
            schema_version=row["schema_version"],
            job_id=row["job_id"],
            family=row["family"],
            checkpoint_profile=row["checkpoint_profile"],
            wishes=row["wishes"],
            source=PromptText(
                positive_prompt=row["source_positive_prompt"],
                negative_prompt=row["source_negative_prompt"],
            ),
            enhanced=PromptText(
                positive_prompt=row["enhanced_positive_prompt"],
                negative_prompt=row["enhanced_negative_prompt"],
            ),
            created_at=row["created_at"],
        )


class PromptEnhancementService:
    """Expand and refine a prompt toward the selected model family style, honoring user wishes."""

    def __init__(
        self,
        *,
        router: ExecutionRouter | None = None,
        store: PromptEnhancementStore | None = None,
    ):
        self.router = router or ExecutionRouter()
        self.store = store or PromptEnhancementStore()

    def enhance(
        self,
        *,
        profile: dict[str, Any],
        task: PromptTask,
        source: PromptText,
        wishes: str = "",
        checkpoint_profile: str | None = None,
        checkpoint_resource: ModelResource | None = None,
        api_key: str | None = None,
        asset_id: int | None = None,
    ) -> PromptEnhancementOutcome:
        if task.operation is not PromptOperation.ENHANCE:
            raise PromptEnhancementError(
                "Prompt enhancement requires operation='enhance'.",
                code="invalid_enhancement_operation",
            )

        try:
            family_enum = PromptFamily(task.family)
        except ValueError as exc:
            raise PromptEnhancementError(
                "family must be one of: flux, sdxl, pony.",
                code="invalid_family",
            ) from exc

        enhanced_task = PromptTask.model_validate(
            {
                **task.model_dump(mode="json"),
                "family": family_enum,
                "checkpoint_profile": checkpoint_profile or task.checkpoint_profile,
            }
        )
        protected_triggers = self._protected_triggers(
            source.positive_prompt,
            checkpoint_resource.trigger_words if checkpoint_resource is not None else (),
        )

        resource_lines = ["none"]
        if checkpoint_resource is not None:
            resource_lines = [
                f"name: {checkpoint_resource.display_name or checkpoint_resource.name}",
                f"family: {checkpoint_resource.prompt_family or 'generic'}",
                f"architecture: {checkpoint_resource.architecture.value}",
                f"protected_triggers_in_source: "
                + json.dumps(protected_triggers, ensure_ascii=False),
            ]

        user_input = (
            f"USER WISHES (improvement directive)\n"
            f"{wishes.strip() or 'no explicit wishes - polish the prompt preserving its meaning'}\n\n"
            f"TARGET FAMILY\n{family_enum.value}\n\n"
            f"CHECKPOINT PROFILE\n{enhanced_task.checkpoint_profile or 'default'}\n\n"
            f"CHECKPOINT RESOURCE\n" + "\n".join(resource_lines) + "\n\n"
            "SOURCE PROMPT JSON\n"
            + json.dumps(source.model_dump(mode="json"), ensure_ascii=False)
        )

        execution = self.router.execute(
            profile=profile,
            task=enhanced_task,
            user_input=user_input,
            api_key=api_key,
            asset_id=asset_id,
            result_transformer=lambda result: self._restore_protected_triggers(
                result,
                protected_triggers,
            ),
        )

        enhanced_prompt = PromptText(
            positive_prompt=execution.result.positive_prompt,
            negative_prompt=execution.result.negative_prompt,
        )

        enhancement = self.store.save(
            job_id=execution.job_id,
            source=source,
            enhanced=enhanced_prompt,
            family=family_enum,
            checkpoint_profile=enhanced_task.checkpoint_profile,
            wishes=wishes.strip(),
        )

        return PromptEnhancementOutcome(
            execution=execution,
            enhancement=enhancement,
        )

    @classmethod
    def _protected_triggers(
        cls,
        source_prompt: str,
        trusted_triggers: tuple[str, ...] | list[str],
    ) -> tuple[str, ...]:
        protected: list[str] = []
        seen: set[str] = set()
        for raw_trigger in trusted_triggers:
            trigger = str(raw_trigger).strip()
            if not trigger or trigger.casefold() in seen:
                continue
            match = cls._trigger_pattern(trigger).search(source_prompt)
            if match is not None:
                protected.append(match.group(0))
                seen.add(trigger.casefold())
        return tuple(protected)

    @classmethod
    def _restore_protected_triggers(
        cls,
        result: PromptResult,
        protected_triggers: tuple[str, ...],
    ) -> PromptResult:
        missing = [
            trigger
            for trigger in protected_triggers
            if cls._trigger_pattern(trigger).search(result.positive_prompt) is None
        ]
        if not missing:
            return result
        positive = result.positive_prompt.rstrip(" ,")
        return result.model_copy(update={
            "positive_prompt": ", ".join([positive, *missing]),
        })

    @staticmethod
    def _trigger_pattern(trigger: str) -> re.Pattern[str]:
        prefix = r"(?<!\w)" if trigger[0].isalnum() or trigger[0] == "_" else ""
        suffix = r"(?!\w)" if trigger[-1].isalnum() or trigger[-1] == "_" else ""
        return re.compile(f"{prefix}{re.escape(trigger)}{suffix}", re.IGNORECASE)


__all__ = [
    "PromptEnhancement",
    "PromptEnhancementError",
    "PromptEnhancementOutcome",
    "PromptEnhancementService",
    "PromptEnhancementStore",
]
