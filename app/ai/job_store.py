from __future__ import annotations

import json
import sqlite3
from enum import Enum
from typing import Any

from pydantic import Field, field_validator, model_validator

from .. import database
from .prompting import InstructionBundle, PromptResult, PromptTask, SceneSpec
from .prompting.models import StrictModel


class AIJobStoreError(RuntimeError):
    """Raised when an AI job cannot be persisted or changes state illegally."""


class AIJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PromptDraft(StrictModel):
    schema_version: str = Field(default="1", min_length=1, max_length=40)
    positive_prompt: str = Field(default="", max_length=40_000)
    negative_prompt: str = Field(default="", max_length=20_000)
    versions: dict[str, str] = Field(default_factory=dict)

    @field_validator("schema_version", "positive_prompt", "negative_prompt")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def require_content(self) -> "PromptDraft":
        if not self.positive_prompt and not self.negative_prompt:
            raise ValueError("A prompt draft must contain positive or negative prompt text.")
        return self


class AIJob(StrictModel):
    id: int
    asset_id: int | None = None
    task: PromptTask
    execution_backend: str
    provider_profile_id: str | None = None
    model_id: str | None = None
    user_input: str = ""
    status: AIJobStatus
    bundle_metadata: dict[str, Any] | None = None
    technical_error: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None


class StoredPromptDraft(StrictModel):
    id: int
    draft: PromptDraft
    created_at: str


class AIJobSnapshot(StrictModel):
    job: AIJob
    scene_spec: SceneSpec | None = None
    drafts: tuple[StoredPromptDraft, ...] = ()
    result: PromptResult | None = None
    execution_metadata: dict[str, Any] = Field(default_factory=dict)


class AIJobStore:
    """Persist backend-neutral AI execution state in the application database."""

    def create(
        self,
        *,
        task: PromptTask,
        execution_backend: str,
        provider_profile_id: str | None = None,
        model_id: str | None = None,
        asset_id: int | None = None,
        user_input: str = "",
    ) -> AIJob:
        backend = self._required_text(execution_backend, "execution_backend", 120)
        profile_id = self._optional_text(provider_profile_id, "provider_profile_id", 200)
        normalized_model = self._optional_text(model_id, "model_id", 500)
        if not isinstance(user_input, str):
            raise AIJobStoreError("user_input must be text.")
        if len(user_input) > 100_000:
            raise AIJobStoreError("user_input exceeds 100000 characters.")

        conn = database.get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO ai_jobs (
                    asset_id, family, operation, scenario, modifiers_json,
                    checkpoint_profile, output_contract, execution_backend,
                    provider_profile_id, model_id, user_input
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    asset_id,
                    task.family.value,
                    task.operation.value,
                    task.scenario.value,
                    self._json([modifier.value for modifier in task.modifiers]),
                    task.checkpoint_profile,
                    task.output_contract,
                    backend,
                    profile_id,
                    normalized_model,
                    user_input,
                ),
            )
            job_id = int(cursor.lastrowid)
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise AIJobStoreError(f"Cannot create AI job: {exc}") from exc
        finally:
            conn.close()
        return self.get(job_id).job

    def mark_running(self, job_id: int, bundle: InstructionBundle) -> AIJob:
        return self._transition(
            job_id,
            target=AIJobStatus.RUNNING,
            allowed={AIJobStatus.QUEUED},
            bundle_metadata=bundle.metadata(),
        )

    def save_scene_spec(self, job_id: int, scene_spec: SceneSpec) -> SceneSpec:
        self._require_job(job_id)
        payload = self._json(scene_spec.model_dump(mode="json"))
        conn = database.get_conn()
        try:
            conn.execute(
                """INSERT INTO ai_scene_specs (job_id, schema_version, scene_spec_json)
                VALUES (?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    schema_version=excluded.schema_version,
                    scene_spec_json=excluded.scene_spec_json,
                    updated_at=datetime('now')""",
                (job_id, scene_spec.schema_version, payload),
            )
            conn.execute(
                "UPDATE ai_jobs SET updated_at=datetime('now') WHERE id=?",
                (job_id,),
            )
            conn.commit()
        finally:
            conn.close()
        return scene_spec

    def save_draft(self, job_id: int, draft: PromptDraft) -> StoredPromptDraft:
        self._require_job(job_id)
        conn = database.get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO ai_prompt_drafts (
                    job_id, schema_version, positive_prompt, negative_prompt, versions_json
                ) VALUES (?, ?, ?, ?, ?)""",
                (
                    job_id,
                    draft.schema_version,
                    draft.positive_prompt,
                    draft.negative_prompt,
                    self._json(draft.versions),
                ),
            )
            draft_id = int(cursor.lastrowid)
            conn.execute(
                "UPDATE ai_jobs SET updated_at=datetime('now') WHERE id=?",
                (job_id,),
            )
            row = conn.execute(
                "SELECT created_at FROM ai_prompt_drafts WHERE id=?", (draft_id,)
            ).fetchone()
            conn.commit()
        finally:
            conn.close()
        return StoredPromptDraft(id=draft_id, draft=draft, created_at=row["created_at"])

    def complete(
        self,
        job_id: int,
        *,
        result: PromptResult,
        execution_metadata: dict[str, Any] | None = None,
        bundle: InstructionBundle | None = None,
    ) -> AIJobSnapshot:
        current = self._require_job(job_id)
        if current.status not in {AIJobStatus.QUEUED, AIJobStatus.RUNNING}:
            self._raise_transition(current.status, AIJobStatus.COMPLETED)
        metadata_json = self._json(execution_metadata or {})
        bundle_json = self._json(bundle.metadata()) if bundle is not None else None

        conn = database.get_conn()
        try:
            conn.execute("BEGIN")
            conn.execute(
                """INSERT INTO ai_results (
                    job_id, schema_version, positive_prompt, negative_prompt,
                    execution_metadata_json
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    schema_version=excluded.schema_version,
                    positive_prompt=excluded.positive_prompt,
                    negative_prompt=excluded.negative_prompt,
                    execution_metadata_json=excluded.execution_metadata_json,
                    created_at=datetime('now')""",
                (
                    job_id,
                    result.schema_version,
                    result.positive_prompt,
                    result.negative_prompt,
                    metadata_json,
                ),
            )
            conn.execute(
                """UPDATE ai_jobs SET
                    status='completed',
                    bundle_metadata_json=COALESCE(?, bundle_metadata_json),
                    technical_error=NULL,
                    started_at=COALESCE(started_at, datetime('now')),
                    completed_at=datetime('now'),
                    updated_at=datetime('now')
                WHERE id=?""",
                (bundle_json, job_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get(job_id)

    def fail(self, job_id: int, technical_error: str) -> AIJob:
        error = self._required_text(technical_error, "technical_error", 16_000)
        return self._transition(
            job_id,
            target=AIJobStatus.FAILED,
            allowed={AIJobStatus.QUEUED, AIJobStatus.RUNNING},
            technical_error=error,
        )

    def cancel(self, job_id: int) -> AIJob:
        return self._transition(
            job_id,
            target=AIJobStatus.CANCELLED,
            allowed={AIJobStatus.QUEUED, AIJobStatus.RUNNING},
        )

    def get(self, job_id: int) -> AIJobSnapshot:
        conn = database.get_conn()
        try:
            job_row = conn.execute("SELECT * FROM ai_jobs WHERE id=?", (job_id,)).fetchone()
            if job_row is None:
                raise AIJobStoreError(f"AI job {job_id} does not exist.")
            scene_row = conn.execute(
                "SELECT scene_spec_json FROM ai_scene_specs WHERE job_id=?", (job_id,)
            ).fetchone()
            draft_rows = conn.execute(
                "SELECT * FROM ai_prompt_drafts WHERE job_id=? ORDER BY id", (job_id,)
            ).fetchall()
            result_row = conn.execute(
                "SELECT * FROM ai_results WHERE job_id=?", (job_id,)
            ).fetchone()
        finally:
            conn.close()

        scene_spec = (
            SceneSpec.model_validate_json(scene_row["scene_spec_json"])
            if scene_row is not None
            else None
        )
        drafts = tuple(
            StoredPromptDraft(
                id=row["id"],
                draft=PromptDraft(
                    schema_version=row["schema_version"],
                    positive_prompt=row["positive_prompt"],
                    negative_prompt=row["negative_prompt"],
                    versions=self._load_json(row["versions_json"], expected=dict),
                ),
                created_at=row["created_at"],
            )
            for row in draft_rows
        )
        result = None
        execution_metadata: dict[str, Any] = {}
        if result_row is not None:
            result = PromptResult(
                schema_version=result_row["schema_version"],
                positive_prompt=result_row["positive_prompt"],
                negative_prompt=result_row["negative_prompt"],
            )
            execution_metadata = self._load_json(
                result_row["execution_metadata_json"], expected=dict
            )
        return AIJobSnapshot(
            job=self._job_from_row(job_row),
            scene_spec=scene_spec,
            drafts=drafts,
            result=result,
            execution_metadata=execution_metadata,
        )

    def _require_job(self, job_id: int) -> AIJob:
        return self.get(job_id).job

    def _transition(
        self,
        job_id: int,
        *,
        target: AIJobStatus,
        allowed: set[AIJobStatus],
        bundle_metadata: dict[str, Any] | None = None,
        technical_error: str | None = None,
    ) -> AIJob:
        current = self._require_job(job_id)
        if current.status not in allowed:
            self._raise_transition(current.status, target)
        bundle_json = self._json(bundle_metadata) if bundle_metadata is not None else None
        conn = database.get_conn()
        try:
            cursor = conn.execute(
                """UPDATE ai_jobs SET
                    status=?,
                    bundle_metadata_json=COALESCE(?, bundle_metadata_json),
                    technical_error=?,
                    started_at=CASE
                        WHEN ?='running' THEN COALESCE(started_at, datetime('now'))
                        ELSE started_at
                    END,
                    completed_at=CASE
                        WHEN ? IN ('failed', 'cancelled') THEN datetime('now')
                        ELSE completed_at
                    END,
                    updated_at=datetime('now')
                WHERE id=? AND status=?""",
                (
                    target.value,
                    bundle_json,
                    technical_error,
                    target.value,
                    target.value,
                    job_id,
                    current.status.value,
                ),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                raise AIJobStoreError(
                    f"AI job {job_id} changed concurrently; reload it before retrying."
                )
            conn.commit()
        finally:
            conn.close()
        return self.get(job_id).job

    @staticmethod
    def _job_from_row(row: sqlite3.Row) -> AIJob:
        from .prompting import PromptFamily, PromptModifier, PromptOperation, PromptScenario

        modifiers = AIJobStore._load_json(row["modifiers_json"], expected=list)
        bundle_metadata = (
            AIJobStore._load_json(row["bundle_metadata_json"], expected=dict)
            if row["bundle_metadata_json"] is not None
            else None
        )
        return AIJob(
            id=row["id"],
            asset_id=row["asset_id"],
            task=PromptTask(
                family=PromptFamily(row["family"]),
                operation=PromptOperation(row["operation"]),
                scenario=PromptScenario(row["scenario"]),
                modifiers=tuple(PromptModifier(value) for value in modifiers),
                checkpoint_profile=row["checkpoint_profile"],
                output_contract=row["output_contract"],
            ),
            execution_backend=row["execution_backend"],
            provider_profile_id=row["provider_profile_id"],
            model_id=row["model_id"],
            user_input=row["user_input"],
            status=AIJobStatus(row["status"]),
            bundle_metadata=bundle_metadata,
            technical_error=row["technical_error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    @staticmethod
    def _json(value: Any) -> str:
        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise AIJobStoreError(f"AI job metadata is not JSON serializable: {exc}") from exc

    @staticmethod
    def _load_json(value: str, *, expected: type) -> Any:
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise AIJobStoreError(f"Stored AI job JSON is invalid: {exc}") from exc
        if not isinstance(parsed, expected):
            raise AIJobStoreError(
                f"Stored AI job JSON must contain {expected.__name__}."
            )
        return parsed

    @staticmethod
    def _required_text(value: Any, field: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip():
            raise AIJobStoreError(f"{field} must be non-empty text.")
        cleaned = value.strip()
        if len(cleaned) > maximum:
            raise AIJobStoreError(f"{field} exceeds {maximum} characters.")
        return cleaned

    @staticmethod
    def _optional_text(value: Any, field: str, maximum: int) -> str | None:
        if value is None:
            return None
        return AIJobStore._required_text(value, field, maximum)

    @staticmethod
    def _raise_transition(current: AIJobStatus, target: AIJobStatus) -> None:
        raise AIJobStoreError(
            f"Cannot change an AI job from '{current.value}' to '{target.value}'."
        )


__all__ = [
    "AIJob",
    "AIJobSnapshot",
    "AIJobStatus",
    "AIJobStore",
    "AIJobStoreError",
    "PromptDraft",
    "StoredPromptDraft",
]
