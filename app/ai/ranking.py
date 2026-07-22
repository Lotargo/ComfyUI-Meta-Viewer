from __future__ import annotations

import json
import sqlite3
from enum import Enum
from typing import Any

from pydantic import Field, field_validator

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
    rank: AIRank = AIRank.C
    technical_quality: float = Field(default=7.0, ge=0.0, le=10.0)
    composition: float = Field(default=7.0, ge=0.0, le=10.0)
    prompt_adherence: float = Field(default=7.0, ge=0.0, le=10.0)
    defects: list[str] = Field(default_factory=list)
    explanation: str = Field(default="", max_length=5000)

    @field_validator("explanation")
    @classmethod
    def strip_explanation(cls, value: str) -> str:
        return value.strip()


class AIRating(StrictModel):
    id: int | None = None
    image_id: int
    job_id: int | None = None
    rank: AIRank
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
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def effective_rank(self) -> AIRank:
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
    ) -> AIRating:
        conn = database.get_conn()
        try:
            conn.execute(
                """INSERT INTO ai_ratings (
                    image_id, job_id, rank, status, technical_quality,
                    composition, prompt_adherence, defects_json, explanation,
                    execution_backend, provider_profile_id, model_id, evaluation_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    updated_at=datetime('now')""",
                (
                    image_id,
                    job_id,
                    result.rank.value,
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
            override_val = rank_override.value if isinstance(rank_override, AIRank) else str(rank_override)

        conn = database.get_conn()
        try:
            cursor = conn.execute(
                "UPDATE ai_ratings SET rank_override=?, updated_at=datetime('now') WHERE image_id=?",
                (override_val, image_id),
            )
            if cursor.rowcount == 0:
                # If rating doesn't exist yet, insert a default not_rated rating with override
                rank_str = override_val or AIRank.C.value
                conn.execute(
                    """INSERT INTO ai_ratings (
                        image_id, rank, rank_override, status, explanation
                    ) VALUES (?, ?, ?, 'not_rated', 'Manual rank override')""",
                    (image_id, rank_str, override_val),
                )
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise AIRankingError(f"Failed to override rank for image {image_id}: {exc}") from exc
        finally:
            conn.close()
        return self.get_by_image_id(image_id)

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
            rank=AIRank(row["rank"]),
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
            # Rating feature disabled
            result = AIRatingResult(
                status=AIRatingStatus.NOT_RATED,
                rank=AIRank.C,
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
            f"Evaluate image composition, technical quality, prompt adherence, and defects. "
            f"Return rank (F, E, D, C, B, A, S, SS, SSS, SSS+)."
        )

        try:
            outcome = self.router.execute(
                profile=profile,
                task=task,
                user_input=user_input,
                api_key=api_key,
                asset_id=image_id,
            )
            # Parse result from outcome or fallback to structured result
            rating_result = self._parse_evaluation_result(outcome)
            return self.store.save(
                image_id=image_id,
                result=rating_result,
                job_id=outcome.job_id,
                execution_backend=outcome.execution_backend,
                provider_profile_id=outcome.provider_profile_id,
                model_id=outcome.model_id,
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
                rank=AIRank.F if status == AIRatingStatus.GENERATION_ERROR else AIRank.D,
                explanation=explanation,
            )
            return self.store.save(
                image_id=image_id,
                result=result,
                execution_backend=profile.get("kind", "unknown"),
            )

    @staticmethod
    def _parse_evaluation_result(outcome: PromptExecutionOutcome) -> AIRatingResult:
        # Default structured result check
        res = outcome.result
        positive = res.positive_prompt or ""

        # Try parsing JSON if model returned JSON string in positive_prompt
        try:
            data = json.loads(positive)
            if isinstance(data, dict) and "rank" in data:
                rank_val = data.get("rank", "B")
                if rank_val in AIRank._value2member_map_:
                    rank_enum = AIRank(rank_val)
                else:
                    rank_enum = AIRank.B
                return AIRatingResult(
                    status=AIRatingStatus.RATED,
                    rank=rank_enum,
                    technical_quality=float(data.get("technical_quality", 8.0)),
                    composition=float(data.get("composition", 8.0)),
                    prompt_adherence=float(data.get("prompt_adherence", 8.0)),
                    defects=list(data.get("defects", [])),
                    explanation=str(data.get("explanation", positive)),
                )
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        # Fallback heuristic: check if rank keywords appear in text
        for r_str, r_enum in [
            ("SSS+", AIRank.SSS_PLUS),
            ("SSS", AIRank.SSS),
            ("SS", AIRank.SS),
            ("S", AIRank.S),
            ("A", AIRank.A),
            ("B", AIRank.B),
            ("C", AIRank.C),
            ("D", AIRank.D),
            ("E", AIRank.E),
            ("F", AIRank.F),
        ]:
            if f"Rank: {r_str}" in positive or f"Rank {r_str}" in positive or f"rank: {r_str}" in positive.lower():
                return AIRatingResult(
                    status=AIRatingStatus.RATED,
                    rank=r_enum,
                    explanation=positive,
                )

        return AIRatingResult(
            status=AIRatingStatus.RATED,
            rank=AIRank.B,
            explanation=positive or "Image evaluated successfully.",
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
