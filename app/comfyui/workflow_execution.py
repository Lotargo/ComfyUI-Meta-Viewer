from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from app import database
from app.extractor import extract_metadata_from_bytes
from app.media import (
    MediaToolUnavailableError,
    VideoProcessingError,
    media_type_for_path,
    probe_video,
    temporary_media_file,
)

from .client import ComfyUIClient, ComfyUIClientError
from .workflow_errors import normalize_comfyui_error
from .workflow_models import WorkflowDraft, WorkflowRun, WorkflowTemplate
from .workflow_registry import WorkflowTemplateError, WorkflowTemplateRegistry
from .workflow_store import WorkflowStore, WorkflowStoreError


class WorkflowExecutionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "workflow_execution_error",
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.details = details or {}
        super().__init__(message)


class WorkflowExecutionService:
    def __init__(
        self,
        *,
        store: WorkflowStore,
        client: ComfyUIClient,
        registry: WorkflowTemplateRegistry | None = None,
        profile_store: Any | None = None,
    ):
        self.store = store
        self.client = client
        self.registry = registry or WorkflowTemplateRegistry()
        self.profile_store = profile_store

    def queue(
        self,
        *,
        draft: WorkflowDraft,
        template: WorkflowTemplate,
        workflow: dict[str, Any],
        auto_rate: bool = False,
    ) -> WorkflowRun:
        client_id = str(uuid.uuid4())
        try:
            response = self.client.queue_prompt(
                workflow,
                client_id=client_id,
                extra_data={
                    "comfy_meta_viewer": {
                        "draft_id": draft.id,
                        "template_id": template.manifest.id,
                        "template_version": template.manifest.version,
                    },
                    "extra_pnginfo": {
                        "cmv_template": {
                            "id": template.manifest.id,
                            "version": template.manifest.version,
                        },
                        "cmv_draft_id": draft.id,
                    },
                },
            )
        except ComfyUIClientError as exc:
            diagnostic = normalize_comfyui_error(
                exc.payload if isinstance(exc.payload, dict) else {"message": str(exc)},
                template=template,
            )
            raise WorkflowExecutionError(
                diagnostic["message"],
                code="comfyui_prompt_rejected",
                details={"diagnostic": diagnostic},
            ) from exc
        effective_auto_rate = auto_rate or draft.auto_rate
        return self.store.create_run(
            draft_id=draft.id,
            prompt_id=str(response["prompt_id"]),
            client_id=client_id,
            auto_rate=effective_auto_rate,
        )

    def refresh(self, run_id: int) -> WorkflowRun:
        run = self.store.get_run(run_id)
        if run.status in {"completed", "failed", "cancelled"}:
            return run
        job = self.client.get_job(run.prompt_id)
        if job is None:
            return run

        remote_status = str(job.get("status") or "").lower()
        if remote_status in {"pending", "queued"}:
            return self.store.update_run(
                run.id,
                status="queued",
                progress=0.05,
                queue_position=self._queue_position(job),
            )
        if remote_status in {"in_progress", "running"}:
            return self.store.update_run(
                run.id,
                status="running",
                progress=0.5,
                current_node=self._current_node(job),
            )
        if remote_status in {"failed", "error"}:
            diagnostic = self._normalized_error(run, job, status="failed")
            return self.store.update_run(
                run.id,
                status="failed",
                progress=1.0,
                error=diagnostic,
            )
        if remote_status in {"cancelled", "canceled", "interrupted"}:
            diagnostic = self._normalized_error(run, job, status="cancelled")
            return self.store.update_run(
                run.id,
                status="cancelled",
                progress=1.0,
                error=diagnostic,
            )
        if remote_status not in {"completed", "success"}:
            return run

        output_refs = self._output_refs(job)
        draft = self.store.get_draft(run.draft_id)
        asset_ids = list(run.output_asset_ids)
        if not asset_ids:
            workflow = self._workflow_from_job(job)
            for output in output_refs:
                asset_id = self._import_output(
                    output,
                    run=run,
                    draft=draft,
                    workflow=workflow,
                )
                if asset_id is not None:
                    asset_ids.append(asset_id)
        updated_run = self.store.update_run(
            run.id,
            status="completed",
            progress=1.0,
            output_refs=output_refs,
            output_asset_ids=asset_ids,
        )
        self._maybe_auto_rate_run(updated_run, draft)
        return updated_run

    def _maybe_auto_rate_run(self, run: WorkflowRun, draft: WorkflowDraft) -> None:
        try:
            from app.ai.profiles import AIProfileStore
            from app.ai.ranking import AIRankingService
            profile_store = self.profile_store
            if profile_store is None:
                try:
                    from flask import current_app
                    config_file = current_app.config.get("CONFIG_FILE")
                    if config_file:
                        profile_store = AIProfileStore(config_file, secret_store=current_app.config.get("AI_SECRET_STORE"))
                except Exception:
                    pass
            if profile_store is None:
                return
            defaults = profile_store.get_defaults()
            is_auto = run.auto_rate or draft.auto_rate or bool(defaults.get("rating_auto_enabled"))
            if not is_auto:
                return
            mm_id = defaults.get("multimodal_profile_id")
            if not mm_id:
                return
            try:
                profile = profile_store.get(mm_id)
            except Exception:
                return
            api_key = profile_store.resolve_api_key(profile) if profile.get("kind") == "openai_compatible" else None
            prompt_text = str(draft.values.get("prompt") or draft.values.get("positive_prompt") or "")
            service = AIRankingService()
            for asset_id in run.output_asset_ids:
                service.evaluate_asset(
                    profile=profile,
                    image_id=asset_id,
                    prompt_text=prompt_text,
                    api_key=api_key,
                )
        except Exception:
            pass

    def cancel(self, run_id: int) -> WorkflowRun:
        run = self.store.get_run(run_id)
        if run.status in {"completed", "failed", "cancelled"}:
            return run
        self.client.cancel_prompt(run.prompt_id)
        return self.store.update_run(
            run.id,
            status="cancelled",
            progress=1.0,
            error=self._normalized_error(
                run,
                {"error": {"message": "Cancelled by the user."}},
                status="cancelled",
            ),
        )

    def _normalized_error(
        self,
        run: WorkflowRun,
        job: dict[str, Any],
        *,
        status: str,
    ) -> dict[str, Any]:
        template: WorkflowTemplate | None = None
        try:
            draft = self.store.get_draft(run.draft_id)
            template = self.registry.get(draft.template_id)
        except (WorkflowStoreError, WorkflowTemplateError):
            # A removed user template must not hide the original runtime error.
            template = None
        return normalize_comfyui_error(
            self._execution_error(job),
            template=template,
            status=status,
        )

    @staticmethod
    def _queue_position(job: dict[str, Any]) -> int | None:
        value = job.get("queue_position")
        return int(value) if isinstance(value, int) else None

    @staticmethod
    def _current_node(job: dict[str, Any]) -> str | None:
        for key in ("current_node", "node", "node_id"):
            value = job.get(key)
            if value is not None:
                return str(value)
        return None

    @staticmethod
    def _execution_error(job: dict[str, Any]) -> dict[str, Any]:
        error = job.get("execution_error") or job.get("error")
        if isinstance(error, dict):
            return error
        if error:
            return {"message": str(error)}
        execution_status = job.get("execution_status")
        if isinstance(execution_status, dict):
            return execution_status
        return {"message": "ComfyUI execution did not complete successfully."}

    @staticmethod
    def _workflow_from_job(job: dict[str, Any]) -> dict[str, Any] | None:
        workflow = job.get("workflow")
        if isinstance(workflow, dict) and isinstance(workflow.get("prompt"), dict):
            return workflow["prompt"]
        return None

    @staticmethod
    def _output_refs(job: dict[str, Any]) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        outputs = job.get("outputs")
        if not isinstance(outputs, dict):
            return refs
        for node_id, node_outputs in outputs.items():
            if not isinstance(node_outputs, dict):
                continue
            for media_key, items in node_outputs.items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict) or not item.get("filename"):
                        continue
                    ref = dict(item)
                    ref["node_id"] = str(node_id)
                    ref["media_key"] = str(media_key)
                    if ref not in refs:
                        refs.append(ref)
        return refs

    def _import_output(
        self,
        output: dict[str, Any],
        *,
        run: WorkflowRun,
        draft: WorkflowDraft,
        workflow: dict[str, Any] | None,
    ) -> int | None:
        filename = Path(str(output.get("filename") or "output")).name
        media_type = media_type_for_path(filename)
        if media_type not in {"image", "video"}:
            return None
        data = self.client.download_output(output)
        provenance = {
            "source": "comfyui_editor",
            "workflow_run_id": run.id,
            "prompt_id": run.prompt_id,
            "workflow_draft_id": draft.id,
            "template_id": draft.template_id,
            "template_version": draft.template_version,
            "output_node_id": output.get("node_id"),
        }

        if media_type == "image":
            extracted = extract_metadata_from_bytes(data, filename)
            embedded = extracted.model_dump(mode="json")
            embedded["generation"] = provenance
            if workflow is not None:
                embedded["prompt_api_json"] = workflow
                embedded["workflow"] = workflow
            width = extracted.size[0] if extracted.size else 0
            height = extracted.size[1] if extracted.size else 0
            asset_id, _ = database.insert_upload_asset(
                filename,
                data,
                media_type="image",
                has_generation_metadata=True,
                format_name=extracted.format,
                width=width,
                height=height,
                mode=extracted.mode,
                embedded_metadata=embedded,
            )
        else:
            width = height = 0
            duration = frame_rate = None
            codec = format_name = None
            technical: dict[str, Any] = {}
            try:
                with temporary_media_file(data, filename) as temp_path:
                    probe = probe_video(temp_path)
                width = probe.width
                height = probe.height
                duration = probe.duration
                frame_rate = probe.frame_rate
                codec = probe.codec
                format_name = probe.format
                technical = probe.metadata
            except (MediaToolUnavailableError, VideoProcessingError) as exc:
                technical = {"status": "unavailable", "error": str(exc)}
            embedded = {
                "file": filename,
                "path": None,
                "media_type": "video",
                "technical_metadata": technical,
                "generation": provenance,
                "prompt_api_json": workflow,
                "workflow": workflow,
            }
            asset_id, _ = database.insert_upload_asset(
                filename,
                data,
                media_type="video",
                has_generation_metadata=True,
                format_name=format_name,
                width=width,
                height=height,
                duration=duration,
                frame_rate=frame_rate,
                codec=codec,
                embedded_metadata=embedded,
            )

        if draft.source_asset_id is not None:
            conn = database.get_conn()
            try:
                conn.execute(
                    "UPDATE images SET derived_from_asset_id=? WHERE id=?",
                    (draft.source_asset_id, asset_id),
                )
                conn.commit()
            finally:
                conn.close()
        return int(asset_id)


__all__ = ["WorkflowExecutionError", "WorkflowExecutionService"]
