from __future__ import annotations

import json
import sqlite3
from enum import Enum
from typing import Any

from pydantic import Field, ValidationError, field_validator, model_validator

from .. import database
from .prompting import InstructionBundle, PromptResult, PromptTask, SceneSpec
from .prompting.models import StrictModel


class AIJobStoreError(RuntimeError):
    """Raised when an AI job cannot be persisted or changes state illegally."""


class AIJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_REVIEW = "waiting_for_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PromptDraftSource(str, Enum):
    USER_TEXT = "user_text"
    ASSET = "asset"
    SCENE_SPEC = "scene_spec"
    TRANSLATION = "translation"
    ADAPTATION = "adaptation"
    MANUAL = "manual"


class PromptDraft(StrictModel):
    schema_version: str = Field(default="1", min_length=1, max_length=40)
    positive_prompt: str = Field(default="", max_length=40_000)
    negative_prompt: str = Field(default="", max_length=20_000)
    source_kind: PromptDraftSource = PromptDraftSource.USER_TEXT
    source_payload: dict[str, Any] = Field(default_factory=dict)
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
    job_id: int
    parent_draft_id: int | None = None
    draft: PromptDraft
    created_at: str
    updated_at: str


class PromptDraftContext(StrictModel):
    family: str
    checkpoint_profile: str | None = None
    scenario: str
    operation: str
    execution_backend: str
    provider_profile_id: str | None = None
    model_id: str | None = None
    output_contract: str
    technical_status: AIJobStatus


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

    def save_draft(
        self,
        job_id: int,
        draft: PromptDraft,
        *,
        parent_draft_id: int | None = None,
    ) -> StoredPromptDraft:
        job = self._require_job(job_id)
        conn = database.get_conn()
        try:
            if parent_draft_id is not None:
                parent = conn.execute(
                    "SELECT job_id FROM ai_prompt_drafts WHERE id=?",
                    (parent_draft_id,),
                ).fetchone()
                if parent is None:
                    raise AIJobStoreError(
                        f"Prompt draft {parent_draft_id} does not exist."
                    )
                if int(parent["job_id"]) != job_id:
                    raise AIJobStoreError(
                        "A prompt draft revision must belong to the same AI job."
                    )
            cursor = conn.execute(
                """INSERT INTO ai_prompt_drafts (
                    job_id, parent_draft_id, schema_version, positive_prompt,
                    negative_prompt, source_kind, source_payload_json, versions_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    parent_draft_id,
                    draft.schema_version,
                    draft.positive_prompt,
                    draft.negative_prompt,
                    draft.source_kind.value,
                    self._json(draft.source_payload),
                    self._json(draft.versions),
                ),
            )
            draft_id = int(cursor.lastrowid)
            conn.execute(
                "UPDATE ai_jobs SET updated_at=datetime('now') WHERE id=?",
                (job_id,),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_draft(draft_id, job=job)

    def get_draft(
        self,
        draft_id: int,
        *,
        job: AIJob | None = None,
    ) -> StoredPromptDraft:
        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM ai_prompt_drafts WHERE id=?", (draft_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise AIJobStoreError(f"Prompt draft {draft_id} does not exist.")
        resolved_job = job or self._require_job(int(row["job_id"]))
        return self._draft_from_row(row, resolved_job)

    def revise_draft(
        self,
        draft_id: int,
        *,
        positive_prompt: str | None = None,
        negative_prompt: str | None = None,
    ) -> StoredPromptDraft:
        if positive_prompt is None and negative_prompt is None:
            raise AIJobStoreError(
                "A prompt draft revision must change at least one prompt field."
            )
        current = self.get_draft(draft_id)
        try:
            revised = PromptDraft(
                schema_version=current.draft.schema_version,
                positive_prompt=(
                    current.draft.positive_prompt
                    if positive_prompt is None
                    else positive_prompt
                ),
                negative_prompt=(
                    current.draft.negative_prompt
                    if negative_prompt is None
                    else negative_prompt
                ),
                source_kind=PromptDraftSource.MANUAL,
                source_payload={"revised_from_draft_id": draft_id},
                versions=current.draft.versions,
            )
        except ValidationError as exc:
            raise AIJobStoreError(f"Invalid prompt draft revision: {exc}") from exc
        return self.save_draft(
            current.job_id,
            revised,
            parent_draft_id=draft_id,
        )

    def complete(
        self,
        job_id: int,
        *,
        result: PromptResult,
        execution_metadata: dict[str, Any] | None = None,
        bundle: InstructionBundle | None = None,
    ) -> AIJobSnapshot:
        return self._persist_result(
            job_id,
            target=AIJobStatus.COMPLETED,
            allowed={
                AIJobStatus.QUEUED,
                AIJobStatus.RUNNING,
                AIJobStatus.WAITING_FOR_REVIEW,
            },
            result=result,
            execution_metadata=execution_metadata,
            bundle=bundle,
        )

    def wait_for_review(
        self,
        job_id: int,
        *,
        result: PromptResult,
        execution_metadata: dict[str, Any] | None = None,
        bundle: InstructionBundle | None = None,
    ) -> AIJobSnapshot:
        return self._persist_result(
            job_id,
            target=AIJobStatus.WAITING_FOR_REVIEW,
            allowed={AIJobStatus.QUEUED, AIJobStatus.RUNNING},
            result=result,
            execution_metadata=execution_metadata,
            bundle=bundle,
        )

    def accept_draft(
        self,
        job_id: int,
        *,
        draft_id: int | None = None,
    ) -> AIJobSnapshot:
        snapshot = self.get(job_id)
        if snapshot.job.status is not AIJobStatus.WAITING_FOR_REVIEW:
            self._raise_transition(snapshot.job.status, AIJobStatus.COMPLETED)
        if not snapshot.drafts:
            raise AIJobStoreError(f"AI job {job_id} has no prompt draft to accept.")
        if draft_id is None:
            selected = snapshot.drafts[-1]
        else:
            selected = next(
                (draft for draft in snapshot.drafts if draft.id == draft_id),
                None,
            )
            if selected is None:
                raise AIJobStoreError(
                    f"Prompt draft {draft_id} does not belong to AI job {job_id}."
                )
        return self.complete(
            job_id,
            result=PromptResult(
                schema_version=selected.draft.schema_version,
                positive_prompt=selected.draft.positive_prompt,
                negative_prompt=selected.draft.negative_prompt,
            ),
            execution_metadata=snapshot.execution_metadata,
        )

    def _persist_result(
        self,
        job_id: int,
        *,
        target: AIJobStatus,
        allowed: set[AIJobStatus],
        result: PromptResult,
        execution_metadata: dict[str, Any] | None,
        bundle: InstructionBundle | None,
    ) -> AIJobSnapshot:
        current = self._require_job(job_id)
        if current.status not in allowed:
            self._raise_transition(current.status, target)
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
            cursor = conn.execute(
                """UPDATE ai_jobs SET
                    status=?,
                    bundle_metadata_json=COALESCE(?, bundle_metadata_json),
                    technical_error=NULL,
                    started_at=COALESCE(started_at, datetime('now')),
                    completed_at=CASE
                        WHEN ?='completed' THEN datetime('now')
                        ELSE NULL
                    END,
                    updated_at=datetime('now')
                WHERE id=? AND status=?""",
                (
                    target.value,
                    bundle_json,
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
            allowed={
                AIJobStatus.QUEUED,
                AIJobStatus.RUNNING,
                AIJobStatus.WAITING_FOR_REVIEW,
            },
            technical_error=error,
        )

    def cancel(self, job_id: int) -> AIJob:
        return self._transition(
            job_id,
            target=AIJobStatus.CANCELLED,
            allowed={
                AIJobStatus.QUEUED,
                AIJobStatus.RUNNING,
                AIJobStatus.WAITING_FOR_REVIEW,
            },
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
        job = self._job_from_row(job_row)
        drafts = tuple(self._draft_from_row(row, job) for row in draft_rows)
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
            job=job,
            scene_spec=scene_spec,
            drafts=drafts,
            result=result,
            execution_metadata=execution_metadata,
        )

    @staticmethod
    def draft_context(stored: StoredPromptDraft, job: AIJob) -> PromptDraftContext:
        if stored.job_id != job.id:
            raise AIJobStoreError("Prompt draft and AI job do not match.")
        return PromptDraftContext(
            family=job.task.family.value,
            checkpoint_profile=job.task.checkpoint_profile,
            scenario=job.task.scenario.value,
            operation=job.task.operation.value,
            execution_backend=job.execution_backend,
            provider_profile_id=job.provider_profile_id,
            model_id=job.model_id,
            output_contract=job.task.output_contract,
            technical_status=job.status,
        )

    @staticmethod
    def _draft_from_row(row: sqlite3.Row, job: AIJob) -> StoredPromptDraft:
        return StoredPromptDraft(
            id=row["id"],
            job_id=row["job_id"],
            parent_draft_id=row["parent_draft_id"],
            draft=PromptDraft(
                schema_version=row["schema_version"],
                positive_prompt=row["positive_prompt"],
                negative_prompt=row["negative_prompt"],
                source_kind=PromptDraftSource(row["source_kind"]),
                source_payload=AIJobStore._load_json(
                    row["source_payload_json"], expected=dict
                ),
                versions=AIJobStore._load_json(row["versions_json"], expected=dict),
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
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
    "PromptDraftContext",
    "PromptDraftSource",
    "StoredPromptDraft",
]
