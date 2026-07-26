from __future__ import annotations

from enum import Enum
import json
import sqlite3
from typing import Any

from pydantic import Field, field_validator, model_validator

from .. import database
from .job_store import (
    AIJob,
    AIJobStore,
    AIJobStoreError,
    PromptDraft,
    PromptDraftSource,
    StoredPromptDraft,
)
from .prompting import PromptFamily, PromptOperation, PromptResult, PromptScenario, PromptTask
from .prompting.models import StrictModel


class RemixError(RuntimeError):
    def __init__(self, message: str, *, code: str):
        self.code = code
        super().__init__(message)


class RemixPromptSource(str, Enum):
    ORIGINAL_METADATA = "original_metadata"
    AI_GENERATED = "ai_generated"
    AI_RECONSTRUCTION = "ai_reconstruction"
    SAVED_SCENE_SPEC = "saved_scene_spec"
    TRANSLATION = "translation"
    FAMILY_ADAPTATION = "family_adaptation"
    USER_EDITED = "user_edited"


class RemixRequest(StrictModel):
    asset_id: int
    prompt_source: RemixPromptSource = RemixPromptSource.ORIGINAL_METADATA
    base_prompt_source: RemixPromptSource | None = None
    prompt_draft_id: int | None = Field(default=None, ge=1)
    workflow_template_id: str | None = None
    target_family: PromptFamily = PromptFamily.SDXL
    checkpoint_profile: str | None = None
    override_positive_prompt: str | None = None
    override_negative_prompt: str | None = None

    @field_validator(
        "workflow_template_id",
        "checkpoint_profile",
        "override_positive_prompt",
        "override_negative_prompt",
    )
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @model_validator(mode="after")
    def validate_source_selection(self) -> "RemixRequest":
        if self.base_prompt_source is RemixPromptSource.USER_EDITED:
            raise ValueError("base_prompt_source cannot be user_edited.")
        if self.prompt_source is RemixPromptSource.USER_EDITED:
            if not self.override_positive_prompt:
                raise ValueError("A manually edited remix requires a positive prompt.")
        elif self.base_prompt_source is not None:
            raise ValueError("base_prompt_source is only valid for a manually edited remix.")
        return self


class RemixPromptOption(StrictModel):
    key: str = Field(min_length=1, max_length=120)
    prompt_source: RemixPromptSource
    label: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=500)
    positive_prompt: str = Field(default="", max_length=40_000)
    negative_prompt: str = Field(default="", max_length=20_000)
    prompt_draft_id: int | None = None
    job_id: int | None = None
    family: PromptFamily | None = None
    base_prompt_source: RemixPromptSource | None = None
    created_at: str | None = None


class RemixDraftOutcome(StrictModel):
    job: AIJob
    draft: StoredPromptDraft
    parent_asset_id: int
    prompt_source: RemixPromptSource


class RemixService:
    """Prepare a pre-filled editor draft from an asset for manual generation without auto-running."""

    def __init__(self, *, job_store: AIJobStore | None = None):
        self.job_store = job_store or AIJobStore()

    def list_prompt_sources(self, asset_id: int) -> list[RemixPromptOption]:
        conn = database.get_conn()
        try:
            image_row = conn.execute(
                "SELECT id, metadata_json, ai_annotations_json FROM images WHERE id=?",
                (asset_id,),
            ).fetchone()
            if image_row is None:
                raise RemixError(
                    f"Asset with ID {asset_id} not found.",
                    code="asset_not_found",
                )

            workflow_row = conn.execute(
                """SELECT wd.id, wd.values_json, wd.ai_prompt_draft_id, wr.created_at
                FROM workflow_runs wr
                JOIN workflow_drafts wd ON wd.id=wr.draft_id
                JOIN json_each(wr.output_asset_ids_json) output
                WHERE CAST(output.value AS INTEGER)=?
                ORDER BY wr.id DESC LIMIT 1""",
                (asset_id,),
            ).fetchone()
            draft_rows = conn.execute(
                """SELECT d.*, j.family, j.operation, j.execution_backend,
                    j.created_at AS job_created_at,
                    CASE WHEN s.job_id IS NULL THEN 0 ELSE 1 END AS has_scene_spec
                FROM ai_prompt_drafts d
                JOIN ai_jobs j ON j.id=d.job_id
                LEFT JOIN ai_scene_specs s ON s.job_id=j.id
                WHERE j.execution_backend!='remix' AND d.id IN (
                    SELECT MAX(direct_draft.id)
                    FROM ai_prompt_drafts direct_draft
                    JOIN ai_jobs direct_job ON direct_job.id=direct_draft.job_id
                    WHERE direct_job.asset_id=?
                    GROUP BY direct_draft.job_id
                    UNION
                    SELECT wd.ai_prompt_draft_id
                    FROM workflow_runs wr
                    JOIN workflow_drafts wd ON wd.id=wr.draft_id
                    JOIN json_each(wr.output_asset_ids_json) output
                    WHERE CAST(output.value AS INTEGER)=?
                        AND wd.ai_prompt_draft_id IS NOT NULL
                )
                ORDER BY d.id DESC""",
                (asset_id, asset_id),
            ).fetchall()
        finally:
            conn.close()

        options: list[RemixPromptOption] = []
        positive, negative = self._metadata_prompts(image_row["metadata_json"])
        if positive:
            options.append(RemixPromptOption(
                key="embedded",
                prompt_source=RemixPromptSource.ORIGINAL_METADATA,
                label="Embedded generation prompt",
                description="Prompt extracted from the asset metadata.",
                positive_prompt=positive,
                negative_prompt=negative,
            ))

        annotation_positive, annotation_negative = self._annotation_prompts(
            image_row["ai_annotations_json"]
        )
        if annotation_positive:
            options.append(RemixPromptOption(
                key="ai-annotation",
                prompt_source=RemixPromptSource.AI_RECONSTRUCTION,
                label="Saved AI reconstruction",
                description="Prompt stored with the asset AI annotations.",
                positive_prompt=annotation_positive,
                negative_prompt=annotation_negative,
            ))

        for row in draft_rows:
            source = self._source_for_job_row(row)
            if source is None:
                continue
            label, description = self._source_copy(source)
            options.append(RemixPromptOption(
                key=f"draft-{row['id']}",
                prompt_source=source,
                label=label,
                description=description,
                positive_prompt=row["positive_prompt"],
                negative_prompt=row["negative_prompt"],
                prompt_draft_id=int(row["id"]),
                job_id=int(row["job_id"]),
                family=PromptFamily(row["family"]),
                created_at=row["updated_at"] or row["created_at"],
            ))

        if workflow_row is not None:
            values = self._json_object(workflow_row["values_json"])
            workflow_positive = str(values.get("positive_prompt") or "").strip()
            workflow_negative = str(values.get("negative_prompt") or "").strip()
            ai_draft = next(
                (
                    row for row in draft_rows
                    if workflow_row["ai_prompt_draft_id"] is not None
                    and int(row["id"]) == int(workflow_row["ai_prompt_draft_id"])
                ),
                None,
            )
            was_edited = ai_draft is None or (
                workflow_positive != ai_draft["positive_prompt"]
                or workflow_negative != ai_draft["negative_prompt"]
            )
            if workflow_positive and was_edited:
                options.append(RemixPromptOption(
                    key=f"editor-{workflow_row['id']}",
                    prompt_source=RemixPromptSource.USER_EDITED,
                    label="Prompt used by the editor",
                    description="Manual prompt values used to generate this asset.",
                    positive_prompt=workflow_positive,
                    negative_prompt=workflow_negative,
                    created_at=workflow_row["created_at"],
                ))

        base = options[0] if options else None
        options.append(RemixPromptOption(
            key="manual",
            prompt_source=RemixPromptSource.USER_EDITED,
            base_prompt_source=base.prompt_source if base is not None else None,
            label="Manual prompt",
            description="Start from the selected asset and edit the prompt before opening Create.",
            positive_prompt=base.positive_prompt if base is not None else "",
            negative_prompt=base.negative_prompt if base is not None else "",
            prompt_draft_id=base.prompt_draft_id if base is not None else None,
            job_id=base.job_id if base is not None else None,
            family=base.family if base is not None else None,
        ))
        return options

    def create_remix_draft(
        self,
        *,
        request: RemixRequest,
        execution_backend: str = "remix",
        provider_profile_id: str | None = None,
        model_id: str | None = None,
    ) -> RemixDraftOutcome:
        conn = database.get_conn()
        try:
            image_row = conn.execute(
                "SELECT id, metadata_json, ai_annotations_json FROM images WHERE id=?",
                (request.asset_id,),
            ).fetchone()
        finally:
            conn.close()

        if image_row is None:
            raise RemixError(f"Asset with ID {request.asset_id} not found.", code="asset_not_found")

        # Determine initial prompt text from chosen prompt source
        positive_prompt, negative_prompt, source_job = self._extract_prompts(
            image_row=image_row,
            request=request,
        )

        if not positive_prompt:
            raise RemixError(
                "The selected remix source does not contain a positive prompt.",
                code="remix_prompt_missing",
            )

        task = PromptTask(
            family=(
                source_job.task.family
                if source_job is not None
                else request.target_family
            ),
            operation=PromptOperation.GENERATE,
            scenario=(
                source_job.task.scenario
                if source_job is not None
                else PromptScenario.SINGLE_CHARACTER
            ),
            checkpoint_profile=request.checkpoint_profile,
        )

        # Create job in waiting_for_review status so generation is NOT started automatically
        job = self.job_store.create(
            task=task,
            execution_backend=execution_backend,
            provider_profile_id=provider_profile_id,
            model_id=model_id,
            asset_id=request.asset_id,
            user_input=f"REMIX from asset #{request.asset_id} via {request.prompt_source.value}",
        )

        draft_content = PromptDraft(
            schema_version="1",
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            source_kind=(
                PromptDraftSource.MANUAL
                if request.prompt_source is RemixPromptSource.USER_EDITED
                else PromptDraftSource.ASSET
            ),
            source_payload={
                "parent_asset_id": request.asset_id,
                "prompt_source": request.prompt_source.value,
                "base_prompt_source": (
                    request.base_prompt_source.value
                    if request.base_prompt_source is not None
                    else None
                ),
                "source_prompt_draft_id": request.prompt_draft_id,
                "source_ai_job_id": source_job.id if source_job is not None else None,
                "workflow_template_id": request.workflow_template_id,
            },
        )

        # Save initial draft in job store
        stored_draft = self.job_store.add_draft(job.id, draft_content)

        # Update job status to WAITING_FOR_REVIEW
        prompt_result = PromptResult(
            positive_prompt=draft_content.positive_prompt,
            negative_prompt=draft_content.negative_prompt,
        )
        self.job_store.wait_for_review(job.id, result=prompt_result)

        updated_job = self.job_store.get(job.id).job

        return RemixDraftOutcome(
            job=updated_job,
            draft=stored_draft,
            parent_asset_id=request.asset_id,
            prompt_source=request.prompt_source,
        )

    def link_derived_asset(self, *, child_asset_id: int, parent_asset_id: int) -> None:
        """Record asset lineage when a remix generation produces a new media item."""
        conn = database.get_conn()
        try:
            conn.execute(
                "UPDATE images SET derived_from_asset_id=? WHERE id=?",
                (parent_asset_id, child_asset_id),
            )
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise RemixError(f"Failed to link asset lineage: {exc}", code="lineage_error") from exc
        finally:
            conn.close()

    def _extract_prompts(
        self,
        *,
        image_row: sqlite3.Row,
        request: RemixRequest,
    ) -> tuple[str, str, AIJob | None]:
        base_source = request.base_prompt_source or request.prompt_source
        source_job: AIJob | None = None

        if request.prompt_draft_id is not None:
            try:
                stored = self.job_store.get_draft(request.prompt_draft_id)
                source_job = self.job_store.get(stored.job_id).job
            except AIJobStoreError as exc:
                raise RemixError(
                    "The selected saved prompt draft does not exist.",
                    code="remix_prompt_source_missing",
                ) from exc
            self._validate_prompt_draft_source(
                asset_id=request.asset_id,
                source=base_source,
                stored=stored,
                job=source_job,
            )
            pos_prompt = stored.draft.positive_prompt
            neg_prompt = stored.draft.negative_prompt
        elif base_source is RemixPromptSource.ORIGINAL_METADATA:
            pos_prompt, neg_prompt = self._metadata_prompts(image_row["metadata_json"])
        elif base_source is RemixPromptSource.AI_RECONSTRUCTION:
            pos_prompt, neg_prompt = self._annotation_prompts(
                image_row["ai_annotations_json"]
            )
        elif request.prompt_source is RemixPromptSource.USER_EDITED:
            pos_prompt = ""
            neg_prompt = ""
        else:
            raise RemixError(
                "The selected remix source requires a saved prompt draft.",
                code="remix_prompt_source_missing",
            )

        if request.override_positive_prompt is not None:
            return (
                request.override_positive_prompt,
                request.override_negative_prompt or "",
                source_job,
            )
        return (pos_prompt, neg_prompt, source_job)

    def _validate_prompt_draft_source(
        self,
        *,
        asset_id: int,
        source: RemixPromptSource,
        stored: StoredPromptDraft,
        job: AIJob,
    ) -> None:
        expected = {
            PromptOperation.GENERATE: RemixPromptSource.AI_GENERATED,
            PromptOperation.TRANSLATE: RemixPromptSource.TRANSLATION,
            PromptOperation.ADAPT: RemixPromptSource.FAMILY_ADAPTATION,
        }.get(job.task.operation)
        if job.task.operation is PromptOperation.RECONSTRUCT:
            snapshot = self.job_store.get(job.id)
            expected = (
                RemixPromptSource.SAVED_SCENE_SPEC
                if snapshot.scene_spec is not None
                else RemixPromptSource.AI_RECONSTRUCTION
            )
        if source is not expected:
            raise RemixError(
                "The saved prompt draft does not match the selected remix source.",
                code="remix_prompt_source_mismatch",
            )
        if job.asset_id == asset_id:
            return
        conn = database.get_conn()
        try:
            related = conn.execute(
                """SELECT 1
                FROM workflow_drafts wd
                JOIN workflow_runs wr ON wr.draft_id=wd.id
                JOIN json_each(wr.output_asset_ids_json) output
                WHERE wd.ai_prompt_draft_id=?
                    AND CAST(output.value AS INTEGER)=?
                LIMIT 1""",
                (stored.id, asset_id),
            ).fetchone()
        finally:
            conn.close()
        if related is None:
            raise RemixError(
                "The saved prompt draft is not related to the selected asset.",
                code="remix_prompt_asset_mismatch",
            )

    @staticmethod
    def _source_for_job_row(row: sqlite3.Row) -> RemixPromptSource | None:
        operation = PromptOperation(row["operation"])
        if operation is PromptOperation.GENERATE:
            return RemixPromptSource.AI_GENERATED
        if operation is PromptOperation.TRANSLATE:
            return RemixPromptSource.TRANSLATION
        if operation is PromptOperation.ADAPT:
            return RemixPromptSource.FAMILY_ADAPTATION
        if operation is PromptOperation.RECONSTRUCT and row["has_scene_spec"]:
            return RemixPromptSource.SAVED_SCENE_SPEC
        return None

    @staticmethod
    def _source_copy(source: RemixPromptSource) -> tuple[str, str]:
        return {
            RemixPromptSource.AI_GENERATED: (
                "Original AI-generated prompt",
                "Persisted prompt draft used by the generation flow.",
            ),
            RemixPromptSource.SAVED_SCENE_SPEC: (
                "Prompt reconstructed from SceneSpec",
                "Persisted reconstruction rendered from an editable SceneSpec.",
            ),
            RemixPromptSource.TRANSLATION: (
                "Translated prompt",
                "Persisted translation associated with this asset.",
            ),
            RemixPromptSource.FAMILY_ADAPTATION: (
                "Family-adapted prompt",
                "Persisted prompt adaptation associated with this asset.",
            ),
        }[source]

    @classmethod
    def _metadata_prompts(cls, value: str | None) -> tuple[str, str]:
        data = cls._json_object(value)
        prompt_parameters = data.get("prompt_parameters")
        if not isinstance(prompt_parameters, dict):
            prompt_parameters = {}
        positive = (
            prompt_parameters.get("positive_prompt")
            or prompt_parameters.get("prompt")
            or prompt_parameters.get("positive")
            or data.get("prompt")
            or data.get("positive_prompt")
            or data.get("positive")
            or ""
        )
        negative = (
            prompt_parameters.get("negative_prompt")
            or prompt_parameters.get("negative")
            or data.get("negative_prompt")
            or data.get("negative")
            or ""
        )
        return str(positive).strip(), str(negative).strip()

    @classmethod
    def _annotation_prompts(cls, value: str | None) -> tuple[str, str]:
        data = cls._json_object(value)
        positive = data.get("positive_prompt") or data.get("prompt") or ""
        negative = data.get("negative_prompt") or ""
        return str(positive).strip(), str(negative).strip()

    @staticmethod
    def _json_object(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            data = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}


__all__ = [
    "RemixDraftOutcome",
    "RemixError",
    "RemixPromptSource",
    "RemixPromptOption",
    "RemixRequest",
    "RemixService",
]
