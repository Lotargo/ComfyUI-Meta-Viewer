from __future__ import annotations

import json
import sqlite3
from typing import Any, Literal

from pydantic import Field, field_validator

from .. import database
from .execution import ExecutionRouter, PromptExecutionOutcome
from .prompting import PromptOperation, PromptTask
from .prompting.models import StrictModel


class PromptTranslationError(RuntimeError):
    def __init__(self, message: str, *, code: str):
        self.code = code
        super().__init__(message)


class PromptText(StrictModel):
    positive_prompt: str = Field(min_length=1, max_length=40_000)
    negative_prompt: str = Field(default="", max_length=20_000)

    @field_validator("positive_prompt")
    @classmethod
    def strip_positive_prompt(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("positive_prompt cannot be empty.")
        return cleaned

    @field_validator("negative_prompt")
    @classmethod
    def strip_negative_prompt(cls, value: str) -> str:
        return value.strip()


class PromptTranslation(StrictModel):
    schema_version: Literal["1"] = "1"
    job_id: int
    source_language: str | None = None
    target_language: str
    source: PromptText
    translated: PromptText
    created_at: str


class PromptTranslationOutcome(StrictModel):
    execution: PromptExecutionOutcome
    translation: PromptTranslation


class PromptTranslationStore:
    def save(
        self,
        *,
        job_id: int,
        source: PromptText,
        translated: PromptText,
        target_language: str,
        source_language: str | None = None,
    ) -> PromptTranslation:
        target = self._language(target_language, required=True)
        source_lang = self._language(source_language, required=False)
        conn = database.get_conn()
        try:
            job = conn.execute(
                """SELECT j.status, r.positive_prompt, r.negative_prompt
                FROM ai_jobs j
                LEFT JOIN ai_results r ON r.job_id=j.id
                WHERE j.id=?""",
                (job_id,),
            ).fetchone()
            if job is None or job["status"] != "completed":
                raise PromptTranslationError(
                    "A translation can only be attached to a completed AI job.",
                    code="translation_job_incomplete",
                )
            if (
                job["positive_prompt"] != translated.positive_prompt
                or job["negative_prompt"] != translated.negative_prompt
            ):
                raise PromptTranslationError(
                    "The translated prompt does not match the completed AI result.",
                    code="translation_result_mismatch",
                )
            conn.execute(
                """INSERT INTO ai_prompt_translations (
                    job_id, schema_version, source_language, target_language,
                    source_positive_prompt, source_negative_prompt,
                    translated_positive_prompt, translated_negative_prompt
                ) VALUES (?, '1', ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    source_lang,
                    target,
                    source.positive_prompt,
                    source.negative_prompt,
                    translated.positive_prompt,
                    translated.negative_prompt,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise PromptTranslationError(
                f"Cannot save prompt translation: {exc}",
                code="translation_persistence_error",
            ) from exc
        finally:
            conn.close()
        return self.get(job_id)

    def get(self, job_id: int) -> PromptTranslation:
        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM ai_prompt_translations WHERE job_id=?", (job_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise PromptTranslationError(
                f"Prompt translation for AI job {job_id} does not exist.",
                code="translation_not_found",
            )
        return PromptTranslation(
            schema_version=row["schema_version"],
            job_id=row["job_id"],
            source_language=row["source_language"],
            target_language=row["target_language"],
            source=PromptText(
                positive_prompt=row["source_positive_prompt"],
                negative_prompt=row["source_negative_prompt"],
            ),
            translated=PromptText(
                positive_prompt=row["translated_positive_prompt"],
                negative_prompt=row["translated_negative_prompt"],
            ),
            created_at=row["created_at"],
        )

    @staticmethod
    def _language(value: Any, *, required: bool) -> str | None:
        if value is None and not required:
            return None
        if not isinstance(value, str) or not value.strip():
            label = "target_language" if required else "source_language"
            raise PromptTranslationError(
                f"{label} must be non-empty text.", code="invalid_language"
            )
        cleaned = value.strip()
        if len(cleaned) > 80:
            raise PromptTranslationError(
                "Language identifier exceeds 80 characters.", code="invalid_language"
            )
        return cleaned


class PromptTranslationService:
    def __init__(
        self,
        *,
        router: ExecutionRouter | None = None,
        store: PromptTranslationStore | None = None,
    ):
        self.router = router or ExecutionRouter()
        self.store = store or PromptTranslationStore()

    def translate(
        self,
        *,
        profile: dict[str, Any],
        task: PromptTask,
        source: PromptText,
        target_language: str,
        source_language: str | None = None,
        api_key: str | None = None,
        asset_id: int | None = None,
    ) -> PromptTranslationOutcome:
        if task.operation is not PromptOperation.TRANSLATE:
            raise PromptTranslationError(
                "Prompt translation requires operation='translate'; family adaptation is a separate task.",
                code="invalid_translation_operation",
            )
        target = self.store._language(target_language, required=True)
        source_lang = self.store._language(source_language, required=False)
        user_input = self._render_input(
            source=source,
            target_language=target,
            source_language=source_lang,
        )
        execution = self.router.execute(
            profile=profile,
            task=task,
            user_input=user_input,
            api_key=api_key,
            asset_id=asset_id,
        )
        translation = self.store.save(
            job_id=execution.job_id,
            source=source,
            translated=PromptText(
                positive_prompt=execution.result.positive_prompt,
                negative_prompt=execution.result.negative_prompt,
            ),
            target_language=target,
            source_language=source_lang,
        )
        return PromptTranslationOutcome(
            execution=execution,
            translation=translation,
        )

    @staticmethod
    def _render_input(
        *,
        source: PromptText,
        target_language: str,
        source_language: str | None,
    ) -> str:
        payload = json.dumps(source.model_dump(mode="json"), ensure_ascii=False)
        source_label = source_language or "auto-detect"
        return (
            f"TARGET LANGUAGE\n{target_language}\n\n"
            f"SOURCE LANGUAGE\n{source_label}\n\n"
            "SOURCE PROMPT JSON\n"
            f"{payload}"
        )


__all__ = [
    "PromptText",
    "PromptTranslation",
    "PromptTranslationError",
    "PromptTranslationOutcome",
    "PromptTranslationService",
    "PromptTranslationStore",
]
