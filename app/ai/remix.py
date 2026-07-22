from __future__ import annotations

from enum import Enum
import json
import sqlite3
from typing import Any, Literal

from pydantic import Field

from .. import database
from .job_store import AIJob, AIJobStatus, AIJobStore, PromptDraft, PromptDraftSource, StoredPromptDraft
from .prompting import PromptFamily, PromptOperation, PromptResult, PromptScenario, PromptTask
from .prompting.models import StrictModel


class RemixError(RuntimeError):
    def __init__(self, message: str, *, code: str):
        self.code = code
        super().__init__(message)


class RemixPromptSource(str, Enum):
    ORIGINAL_METADATA = "original_metadata"
    AI_RECONSTRUCTION = "ai_reconstruction"
    SAVED_SCENE_SPEC = "saved_scene_spec"
    TRANSLATION = "translation"
    FAMILY_ADAPTATION = "family_adaptation"
    USER_EDITED = "user_edited"


class RemixRequest(StrictModel):
    asset_id: int
    prompt_source: RemixPromptSource = RemixPromptSource.ORIGINAL_METADATA
    workflow_template_id: str | None = None
    target_family: PromptFamily = PromptFamily.FLUX
    checkpoint_profile: str | None = None
    override_positive_prompt: str | None = None
    override_negative_prompt: str | None = None


class RemixDraftOutcome(StrictModel):
    job: AIJob
    draft: StoredPromptDraft
    parent_asset_id: int
    prompt_source: RemixPromptSource


class RemixService:
    """Prepare a pre-filled editor draft from an asset for manual generation without auto-running."""

    def __init__(self, *, job_store: AIJobStore | None = None):
        self.job_store = job_store or AIJobStore()

    def create_remix_draft(
        self,
        *,
        request: RemixRequest,
        execution_backend: str = "direct",
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
        positive_prompt, negative_prompt = self._extract_prompts(
            image_row=image_row,
            request=request,
        )

        task = PromptTask(
            family=request.target_family,
            operation=PromptOperation.RECONSTRUCT,
            scenario=PromptScenario.SINGLE_CHARACTER,
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
            positive_prompt=positive_prompt or "A stylized creative portrait",
            negative_prompt=negative_prompt or "",
            source_kind=PromptDraftSource.ASSET,
            source_payload={
                "parent_asset_id": request.asset_id,
                "prompt_source": request.prompt_source.value,
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

    @staticmethod
    def _extract_prompts(
        *,
        image_row: sqlite3.Row,
        request: RemixRequest,
    ) -> tuple[str, str]:
        if request.override_positive_prompt is not None:
            return (
                request.override_positive_prompt,
                request.override_negative_prompt or "",
            )

        pos_prompt = ""
        neg_prompt = ""

        # Try parsing metadata_json or ai_annotations_json
        meta_json = image_row["metadata_json"]
        ai_json = image_row["ai_annotations_json"]

        if request.prompt_source in (RemixPromptSource.AI_RECONSTRUCTION, RemixPromptSource.SAVED_SCENE_SPEC) and ai_json:
            try:
                ai_data = json.loads(ai_json)
                if isinstance(ai_data, dict):
                    pos_prompt = ai_data.get("positive_prompt") or ai_data.get("prompt") or ""
                    neg_prompt = ai_data.get("negative_prompt") or ""
            except (json.JSONDecodeError, TypeError):
                pass

        if not pos_prompt and meta_json:
            try:
                meta_data = json.loads(meta_json)
                if isinstance(meta_data, dict):
                    prompt_parameters = meta_data.get("prompt_parameters")
                    if not isinstance(prompt_parameters, dict):
                        prompt_parameters = {}
                    pos_prompt = (
                        prompt_parameters.get("positive_prompt")
                        or prompt_parameters.get("prompt")
                        or prompt_parameters.get("positive")
                        or meta_data.get("prompt")
                        or meta_data.get("positive_prompt")
                        or meta_data.get("positive")
                        or ""
                    )
                    neg_prompt = (
                        prompt_parameters.get("negative_prompt")
                        or prompt_parameters.get("negative")
                        or meta_data.get("negative_prompt")
                        or meta_data.get("negative")
                        or ""
                    )
            except (json.JSONDecodeError, TypeError):
                pass

        return (pos_prompt, neg_prompt)


__all__ = [
    "RemixDraftOutcome",
    "RemixError",
    "RemixPromptSource",
    "RemixRequest",
    "RemixService",
]
