from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app import database
from app.ai.job_store import AIJobStore, PromptDraft, PromptDraftSource
from app.ai.prompting import (
    PromptFamily,
    PromptOperation,
    PromptScenario,
    PromptTask,
    PromptResult,
)
from app.main import app


class PromptDraftRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()
        self.store = AIJobStore()
        self.job = self.store.create(
            task=PromptTask(
                family=PromptFamily.SDXL,
                operation=PromptOperation.ADAPT,
                scenario=PromptScenario.PORTRAIT,
                checkpoint_profile="photo-xl",
            ),
            execution_backend="openai_compatible",
            provider_profile_id="editor-profile",
            model_id="editor-model",
            user_input="adapt this portrait",
        )
        self.draft = self.store.save_draft(
            self.job.id,
            PromptDraft(
                positive_prompt="studio portrait",
                source_kind=PromptDraftSource.ADAPTATION,
                source_payload={"user_input": "adapt this portrait"},
                versions={"family": "1", "operation": "1"},
            ),
        )
        self.client = app.test_client()

    def tearDown(self) -> None:
        database.set_db_path(self.old_db_path)
        self.temp_dir.cleanup()

    def test_get_job_returns_restart_safe_draft_history(self) -> None:
        response = self.client.get(f"/api/ai/jobs/{self.job.id}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["job"]["model_id"], "editor-model")
        self.assertEqual(payload["drafts"][0]["id"], self.draft.id)
        self.assertEqual(
            payload["drafts"][0]["draft"]["source_kind"], "adaptation"
        )

    def test_patch_creates_revision_and_returns_complete_context(self) -> None:
        response = self.client.patch(
            f"/api/ai/prompt-drafts/{self.draft.id}",
            json={"positive_prompt": "cinematic studio portrait"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        revised = payload["draft"]
        self.assertNotEqual(revised["id"], self.draft.id)
        self.assertEqual(revised["parent_draft_id"], self.draft.id)
        self.assertEqual(revised["draft"]["source_kind"], "manual")
        self.assertEqual(payload["context"]["family"], "sdxl")
        self.assertEqual(payload["context"]["checkpoint_profile"], "photo-xl")
        self.assertEqual(payload["context"]["scenario"], "portrait")
        self.assertEqual(payload["context"]["provider_profile_id"], "editor-profile")
        self.assertEqual(payload["context"]["model_id"], "editor-model")
        self.assertEqual(payload["context"]["technical_status"], "queued")
        self.assertEqual(len(AIJobStore().get(self.job.id).drafts), 2)

    def test_patch_rejects_invalid_fields_and_content(self) -> None:
        unsupported = self.client.patch(
            f"/api/ai/prompt-drafts/{self.draft.id}",
            json={"model_id": "silently-change-context"},
        )
        self.assertEqual(unsupported.status_code, 422)

        invalid = self.client.patch(
            f"/api/ai/prompt-drafts/{self.draft.id}",
            json={"positive_prompt": 42},
        )
        self.assertEqual(invalid.status_code, 422)

        missing = self.client.get("/api/ai/prompt-drafts/999999")
        self.assertEqual(missing.status_code, 404)

    def test_review_accepts_latest_edit_as_final_result(self) -> None:
        self.store.wait_for_review(
            self.job.id,
            result=PromptResult(positive_prompt="studio portrait"),
            execution_metadata={"latency_ms": 25},
        )
        edit_response = self.client.patch(
            f"/api/ai/prompt-drafts/{self.draft.id}",
            json={"positive_prompt": "reviewed cinematic portrait"},
        )
        edited_id = edit_response.get_json()["draft"]["id"]
        review = self.client.post(
            f"/api/ai/jobs/{self.job.id}/review",
            json={"draft_id": edited_id},
        )
        self.assertEqual(review.status_code, 200)
        payload = review.get_json()
        self.assertEqual(payload["job"]["status"], "completed")
        self.assertEqual(
            payload["result"]["positive_prompt"],
            "reviewed cinematic portrait",
        )
        self.assertEqual(payload["execution_metadata"], {"latency_ms": 25})

    def test_waiting_job_can_be_cancelled_through_api(self) -> None:
        self.store.wait_for_review(
            self.job.id,
            result=PromptResult(positive_prompt="studio portrait"),
        )
        response = self.client.post(f"/api/ai/jobs/{self.job.id}/cancel")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["job"]["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
