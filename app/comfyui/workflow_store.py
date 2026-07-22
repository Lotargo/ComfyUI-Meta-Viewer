from __future__ import annotations

import json
import sqlite3
from typing import Any

from app import database

from .workflow_models import WorkflowDraft, WorkflowRun


class WorkflowStoreError(RuntimeError):
    def __init__(self, message: str, *, code: str = "workflow_store_error"):
        self.code = code
        super().__init__(message)


class WorkflowStore:
    def create_draft(
        self,
        *,
        template_id: str,
        template_version: str,
        values: dict[str, Any],
        resource_selections: dict[str, Any],
        source_asset_id: int | None = None,
        ai_prompt_draft_id: int | None = None,
    ) -> WorkflowDraft:
        conn = database.get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO workflow_drafts (
                    template_id, template_version, values_json,
                    resource_selections_json, source_asset_id, ai_prompt_draft_id
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    template_id,
                    template_version,
                    self._json(values),
                    self._json(resource_selections),
                    source_asset_id,
                    ai_prompt_draft_id,
                ),
            )
            draft_id = int(cursor.lastrowid)
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise WorkflowStoreError(
                f"Cannot create workflow draft: {exc}",
                code="invalid_workflow_draft_reference",
            ) from exc
        finally:
            conn.close()
        return self.get_draft(draft_id)

    def get_draft(self, draft_id: int) -> WorkflowDraft:
        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM workflow_drafts WHERE id=?",
                (draft_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise WorkflowStoreError(
                f"Workflow draft {draft_id} was not found.",
                code="workflow_draft_not_found",
            )
        return self._draft_from_row(row)

    def update_draft(
        self,
        draft_id: int,
        *,
        values: dict[str, Any] | None = None,
        resource_selections: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> WorkflowDraft:
        assignments: list[str] = []
        params: list[Any] = []
        if values is not None:
            assignments.append("values_json=?")
            params.append(self._json(values))
        if resource_selections is not None:
            assignments.append("resource_selections_json=?")
            params.append(self._json(resource_selections))
        if status is not None:
            assignments.append("status=?")
            params.append(status)
        if not assignments:
            return self.get_draft(draft_id)
        assignments.append("updated_at=datetime('now')")
        params.append(draft_id)
        conn = database.get_conn()
        try:
            cursor = conn.execute(
                f"UPDATE workflow_drafts SET {', '.join(assignments)} WHERE id=?",
                params,
            )
            if cursor.rowcount != 1:
                raise WorkflowStoreError(
                    f"Workflow draft {draft_id} was not found.",
                    code="workflow_draft_not_found",
                )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise WorkflowStoreError(
                f"Cannot update workflow draft: {exc}",
                code="invalid_workflow_draft",
            ) from exc
        finally:
            conn.close()
        return self.get_draft(draft_id)

    def create_run(
        self,
        *,
        draft_id: int,
        prompt_id: str,
        client_id: str,
    ) -> WorkflowRun:
        conn = database.get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO workflow_runs (draft_id, prompt_id, client_id)
                VALUES (?, ?, ?)""",
                (draft_id, prompt_id, client_id),
            )
            run_id = int(cursor.lastrowid)
            conn.execute(
                "UPDATE workflow_drafts SET status='queued', updated_at=datetime('now') WHERE id=?",
                (draft_id,),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise WorkflowStoreError(
                f"Cannot create workflow run: {exc}",
                code="invalid_workflow_run",
            ) from exc
        finally:
            conn.close()
        return self.get_run(run_id)

    def get_run(self, run_id: int) -> WorkflowRun:
        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM workflow_runs WHERE id=?",
                (run_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise WorkflowStoreError(
                f"Workflow run {run_id} was not found.",
                code="workflow_run_not_found",
            )
        return self._run_from_row(row)

    def list_runs(self, *, limit: int = 30) -> list[WorkflowRun]:
        safe_limit = max(1, min(int(limit), 200))
        conn = database.get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM workflow_runs ORDER BY id DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        finally:
            conn.close()
        return [self._run_from_row(row) for row in rows]

    def update_run(
        self,
        run_id: int,
        *,
        status: str | None = None,
        progress: float | None = None,
        queue_position: int | None = None,
        current_node: str | None = None,
        error: dict[str, Any] | None = None,
        output_refs: list[dict[str, Any]] | None = None,
        output_asset_ids: list[int] | None = None,
    ) -> WorkflowRun:
        current = self.get_run(run_id)
        assignments: list[str] = []
        params: list[Any] = []
        if status is not None:
            assignments.append("status=?")
            params.append(status)
            if status == "running" and current.started_at is None:
                assignments.append("started_at=datetime('now')")
            if status in {"completed", "failed", "cancelled"}:
                assignments.append("completed_at=COALESCE(completed_at, datetime('now'))")
        if progress is not None:
            assignments.append("progress=?")
            params.append(progress)
        if queue_position is not None:
            assignments.append("queue_position=?")
            params.append(queue_position)
        elif status in {"running", "completed", "failed", "cancelled"}:
            assignments.append("queue_position=NULL")
        if current_node is not None:
            assignments.append("current_node=?")
            params.append(current_node)
        if error is not None:
            assignments.append("error_json=?")
            params.append(self._json(error))
        if output_refs is not None:
            assignments.append("output_refs_json=?")
            params.append(self._json(output_refs))
        if output_asset_ids is not None:
            assignments.append("output_asset_ids_json=?")
            params.append(self._json(output_asset_ids))
        assignments.append("updated_at=datetime('now')")
        params.append(run_id)

        conn = database.get_conn()
        try:
            cursor = conn.execute(
                f"UPDATE workflow_runs SET {', '.join(assignments)} WHERE id=?",
                params,
            )
            if cursor.rowcount != 1:
                raise WorkflowStoreError(
                    f"Workflow run {run_id} was not found.",
                    code="workflow_run_not_found",
                )
            final_status = status or current.status
            if status is not None:
                draft_status = {
                    "queued": "queued",
                    "running": "queued",
                    "completed": "completed",
                    "failed": "failed",
                    "cancelled": "cancelled",
                }[final_status]
                conn.execute(
                    "UPDATE workflow_drafts SET status=?, updated_at=datetime('now') WHERE id=?",
                    (draft_status, current.draft_id),
                )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise WorkflowStoreError(
                f"Cannot update workflow run: {exc}",
                code="invalid_workflow_run",
            ) from exc
        finally:
            conn.close()
        return self.get_run(run_id)

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _parse_json(value: Any, fallback: Any) -> Any:
        if not value:
            return fallback
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return fallback
        return parsed

    @classmethod
    def _draft_from_row(cls, row: sqlite3.Row) -> WorkflowDraft:
        return WorkflowDraft(
            id=int(row["id"]),
            template_id=row["template_id"],
            template_version=row["template_version"],
            values=cls._parse_json(row["values_json"], {}),
            resource_selections=cls._parse_json(row["resource_selections_json"], {}),
            source_asset_id=row["source_asset_id"],
            ai_prompt_draft_id=row["ai_prompt_draft_id"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @classmethod
    def _run_from_row(cls, row: sqlite3.Row) -> WorkflowRun:
        return WorkflowRun(
            id=int(row["id"]),
            draft_id=int(row["draft_id"]),
            prompt_id=row["prompt_id"],
            client_id=row["client_id"],
            status=row["status"],
            progress=row["progress"],
            queue_position=row["queue_position"],
            current_node=row["current_node"],
            error=cls._parse_json(row["error_json"], None),
            output_refs=cls._parse_json(row["output_refs_json"], []),
            output_asset_ids=cls._parse_json(row["output_asset_ids_json"], []),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )


__all__ = ["WorkflowStore", "WorkflowStoreError"]
