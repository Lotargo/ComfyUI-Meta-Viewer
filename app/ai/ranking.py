from __future__ import annotations

import json
import sqlite3
from enum import Enum
from typing import Any

from pydantic import Field, field_validator, model_validator

from .. import database
from .execution.base import PromptExecutionOutcome
from .execution.router import ExecutionRouter
from .prompting import PromptFamily, PromptOperation, PromptScenario, PromptTask
from .prompting.models import StrictModel


class AIRankingError(RuntimeError):
    """Raised when AI ranking evaluation or storage fails."""


class AIRank(str, Enum):
    F = "F"
    E = "E"
    D = "D"
    C = "C"
    B = "B"
    A = "A"
    S = "S"
    SS = "SS"
    SSS = "SSS"
    SSS_PLUS = "SSS+"


class AIRatingStatus(str, Enum):
    RATED = "rated"
    GENERATION_ERROR = "generation_error"
    UNREADABLE = "unreadable"
    AI_REJECTED = "ai_rejected"
    NOT_RATED = "not_rated"


class AIRatingResult(StrictModel):
    status: AIRatingStatus = AIRatingStatus.RATED
    rank: AIRank | None = None
    technical_quality: float | None = Field(default=None, ge=0.0, le=10.0)
    composition: float | None = Field(default=None, ge=0.0, le=10.0)
    prompt_adherence: float | None = Field(default=None, ge=0.0, le=10.0)
    defects: list[str] = Field(default_factory=list)
    explanation: str = Field(default="", max_length=5000)

    @field_validator("explanation")
    @classmethod
    def strip_explanation(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_rated_result(self) -> "AIRatingResult":
        if self.status == AIRatingStatus.RATED:
            missing = [
                name
                for name in ("rank", "technical_quality", "composition", "prompt_adherence")
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(
                    "A rated result requires: " + ", ".join(missing)
                )
        elif any(
            value is not None
            for value in (
                self.rank,
                self.technical_quality,
                self.composition,
                self.prompt_adherence,
            )
        ):
            raise ValueError(
                "Technical AI rating states cannot contain artistic ranks or scores."
            )
        return self


class AIRating(StrictModel):
    id: int | None = None
    image_id: int
    job_id: int | None = None
    rank: AIRank | None = None
    rank_override: AIRank | None = None
    status: AIRatingStatus = AIRatingStatus.RATED
    technical_quality: float | None = None
    composition: float | None = None
    prompt_adherence: float | None = None
    defects: list[str] = Field(default_factory=list)
    explanation: str = ""
    execution_backend: str = ""
    provider_profile_id: str | None = None
    model_id: str | None = None
    evaluation_version: str = "1"
    output_schema_version: str = "1"
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def effective_rank(self) -> AIRank | None:
        return self.rank_override if self.rank_override is not None else self.rank


class AIRatingStore:
    """Database persistence for AI ratings and rank overrides."""

    def save(
        self,
        *,
        image_id: int,
        result: AIRatingResult,
        job_id: int | None = None,
        execution_backend: str = "",
        provider_profile_id: str | None = None,
        model_id: str | None = None,
        evaluation_version: str = "1",
        output_schema_version: str = "1",
    ) -> AIRating:
        conn = database.get_conn()
        try:
            conn.execute(
                """INSERT INTO ai_ratings (
                    image_id, job_id, rank, status, technical_quality,
                    composition, prompt_adherence, defects_json, explanation,
                    execution_backend, provider_profile_id, model_id, evaluation_version,
                    schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(image_id) DO UPDATE SET
                    job_id=excluded.job_id,
                    rank=excluded.rank,
                    status=excluded.status,
                    technical_quality=excluded.technical_quality,
                    composition=excluded.composition,
                    prompt_adherence=excluded.prompt_adherence,
                    defects_json=excluded.defects_json,
                    explanation=excluded.explanation,
                    execution_backend=excluded.execution_backend,
                    provider_profile_id=excluded.provider_profile_id,
                    model_id=excluded.model_id,
                    evaluation_version=excluded.evaluation_version,
                    schema_version=excluded.schema_version,
                    updated_at=datetime('now')""",
                (
                    image_id,
                    job_id,
                    result.rank.value if result.rank is not None else None,
                    result.status.value,
                    result.technical_quality,
                    result.composition,
                    result.prompt_adherence,
                    json.dumps(result.defects, ensure_ascii=False),
                    result.explanation,
                    execution_backend,
                    provider_profile_id,
                    model_id,
                    evaluation_version,
                    output_schema_version,
                ),
            )
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise AIRankingError(f"Failed to save AI rating: {exc}") from exc
        finally:
            conn.close()
        return self.get_by_image_id(image_id)

    def set_manual_override(self, image_id: int, rank_override: AIRank | str | None) -> AIRating:
        override_val = None
        if rank_override is not None:
            try:
                override_val = (
                    rank_override.value
                    if isinstance(rank_override, AIRank)
                    else AIRank(str(rank_override)).value
                )
            except ValueError as exc:
                raise AIRankingError("Unknown AI rank override.") from exc

        conn = database.get_conn()
        try:
            cursor = conn.execute(
                "UPDATE ai_ratings SET rank_override=?, updated_at=datetime('now') WHERE image_id=?",
                (override_val, image_id),
            )
            if cursor.rowcount == 0:
                # If rating doesn't exist yet, insert a default not_rated rating with override
                conn.execute(
                    """INSERT INTO ai_ratings (
                        image_id, rank, rank_override, status, explanation
                    ) VALUES (?, ?, ?, 'not_rated', 'Manual rank override')""",
                    (image_id, None, override_val),
                )
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise AIRankingError(f"Failed to override rank for image {image_id}: {exc}") from exc
        finally:
            conn.close()
        return self.get_by_image_id(image_id)

    def delete(self, image_id: int) -> bool:
        conn = database.get_conn()
        try:
            cursor = conn.execute("DELETE FROM ai_ratings WHERE image_id=?", (image_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as exc:
            conn.rollback()
            raise AIRankingError(f"Failed to delete AI rating for image {image_id}: {exc}") from exc
        finally:
            conn.close()

    def get_by_image_id(self, image_id: int) -> AIRating:
        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM ai_ratings WHERE image_id=?", (image_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise AIRankingError(f"AI rating for image {image_id} not found.")
        return self._row_to_model(row)

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> AIRating:
        defects = []
        if row["defects_json"]:
            try:
                defects = json.loads(row["defects_json"])
            except (json.JSONDecodeError, TypeError):
                defects = []

        return AIRating(
            id=row["id"],
            image_id=row["image_id"],
            job_id=row["job_id"],
            rank=AIRank(row["rank"]) if row["rank"] else None,
            rank_override=AIRank(row["rank_override"]) if row["rank_override"] else None,
            status=AIRatingStatus(row["status"]),
            technical_quality=row["technical_quality"],
            composition=row["composition"],
            prompt_adherence=row["prompt_adherence"],
            defects=defects,
            explanation=row["explanation"] or "",
            execution_backend=row["execution_backend"] or "",
            provider_profile_id=row["provider_profile_id"],
            model_id=row["model_id"],
            evaluation_version=row["evaluation_version"] or "1",
            output_schema_version=row["schema_version"] or "1",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class AIRankingService:
    """Multimodal image rating service evaluating prompt adherence and visual quality."""

    def __init__(
        self,
        *,
        router: ExecutionRouter | None = None,
        store: AIRatingStore | None = None,
    ):
        self.router = router or ExecutionRouter()
        self.store = store or AIRatingStore()

    def evaluate_asset(
        self,
        *,
        profile: dict[str, Any],
        image_id: int,
        prompt_text: str = "",
        api_key: str | None = None,
        enabled: bool = True,
    ) -> AIRating:
        if not enabled:
            result = AIRatingResult(
                status=AIRatingStatus.NOT_RATED,
                explanation="AI rating evaluation is disabled.",
            )
            return self.store.save(
                image_id=image_id,
                result=result,
                execution_backend=profile.get("kind", "disabled"),
            )

        task = PromptTask(
            family=PromptFamily.FLUX,
            operation=PromptOperation.RECONSTRUCT,
            scenario=PromptScenario.SINGLE_CHARACTER,
            output_contract="prompt_result",
        )

        user_input = (
            f"IMAGE EVALUATION TASK\n"
            f"Image ID: {image_id}\n"
            f"Original Prompt: {prompt_text}\n"
            "Evaluate image composition, technical quality, prompt adherence, and defects. "
            "Return a PromptResult whose positive_prompt contains only a JSON object with "
            'the keys "rank", "technical_quality", "composition", "prompt_adherence", '
            '"defects", and "explanation". Scores are numbers from 0 to 10, defects is a '
            "JSON string array, and rank is one of F, E, D, C, B, A, S, SS, SSS, SSS+. "
            "Do not use Markdown and leave negative_prompt empty."
        )

        try:
            outcome = self.router.execute(
                profile=profile,
                task=task,
                user_input=user_input,
                api_key=api_key,
                asset_id=image_id,
            )
        except Exception as exc:
            err_msg = str(exc).lower()
            if "policy" in err_msg or "reject" in err_msg or "content_policy" in err_msg:
                status = AIRatingStatus.AI_REJECTED
                explanation = f"AI content policy rejection: {exc}"
            else:
                status = AIRatingStatus.GENERATION_ERROR
                explanation = f"Evaluation execution failed: {exc}"

            result = AIRatingResult(
                status=status,
                explanation=explanation,
            )
            return self.store.save(
                image_id=image_id,
                result=result,
                execution_backend=profile.get("kind", "unknown"),
                provider_profile_id=profile.get("id"),
                model_id=profile.get("model"),
            )

        rating_result = self._parse_evaluation_result(outcome)
        return self.store.save(
            image_id=image_id,
            result=rating_result,
            job_id=outcome.job_id,
            execution_backend=outcome.adapter_id,
            provider_profile_id=profile.get("id"),
            model_id=profile.get("model"),
        )

    @staticmethod
    def _parse_evaluation_result(outcome: PromptExecutionOutcome) -> AIRatingResult:
        res = outcome.result
        positive = res.positive_prompt or ""

        # Try parsing JSON if model returned JSON string in positive_prompt
        try:
            data = json.loads(positive)
            if isinstance(data, dict) and "rank" in data:
                return AIRatingResult.model_validate({
                    **data,
                    "status": AIRatingStatus.RATED,
                })
        except (json.JSONDecodeError, TypeError, ValueError):
            return AIRatingResult(
                status=AIRatingStatus.UNREADABLE,
                explanation=(
                    "The selected AI profile returned a response that does not match "
                    "the rating schema. The asset was preserved and no artistic rank was assigned."
                ),
            )

        return AIRatingResult(
            status=AIRatingStatus.UNREADABLE,
            explanation=(
                "The selected AI profile did not return a structured rating. "
                "The asset was preserved and no artistic rank was assigned."
            ),
        )


AIRatingService = AIRankingService


__all__ = [
    "AIRank",
    "AIRating",
    "AIRatingResult",
    "AIRankingError",
    "AIRankingService",
    "AIRatingService",
    "AIRatingStatus",
    "AIRatingStore",
]
