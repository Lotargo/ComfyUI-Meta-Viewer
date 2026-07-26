from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import database
from app.ai.job_store import AIJobStore, PromptDraft, PromptDraftSource
from app.ai.prompting import (
    PromptFamily,
    PromptOperation,
    PromptScenario,
    PromptTask,
    PromptResult,
)
from app.ai.translation import PromptText, PromptTranslationStore
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

    def test_generate_creates_reviewable_prompt_draft_without_workflow_run(self) -> None:
        captured = {}
        profile = {
            "id": "saved-text-profile",
            "kind": "openai_compatible",
            "name": "Saved text profile",
            "model": "prompt-model",
            "base_url": "https://provider.example/v1",
            "api_key_source": "system",
            "multimodal": False,
            "timeout_seconds": 30,
            "extra_body": {},
        }

        class StubProfileStore:
            @staticmethod
            def list():
                return {
                    "profiles": [],
                    "defaults": {"text_profile_id": profile["id"]},
                }

            @staticmethod
            def get(profile_id):
                self.assertEqual(profile_id, profile["id"])
                return profile

            @staticmethod
            def resolve_api_key(resolved_profile):
                self.assertIs(resolved_profile, profile)
                return "resolved-server-side-secret"

        class StubRouter:
            @staticmethod
            def execute(**kwargs):
                captured.update(kwargs)
                store = AIJobStore()
                job = store.create(
                    task=kwargs["task"],
                    execution_backend="openai_compatible",
                    provider_profile_id=profile["id"],
                    model_id=profile["model"],
                    user_input=kwargs["user_input"],
                )
                store.save_draft(
                    job.id,
                    PromptDraft(
                        positive_prompt="A quiet glass house at blue hour",
                        negative_prompt="blurry, flat light",
                        source_kind=PromptDraftSource.USER_TEXT,
                        source_payload={"user_input": kwargs["user_input"]},
                        versions={"family": "1", "operation": "1"},
                    ),
                )
                store.wait_for_review(
                    job.id,
                    result=PromptResult(
                        positive_prompt="A quiet glass house at blue hour",
                        negative_prompt="blurry, flat light",
                    ),
                )
                return SimpleNamespace(job_id=job.id)

        with (
            patch("app.ai.routes._store", return_value=StubProfileStore()),
            patch("app.ai.routes.ExecutionRouter", return_value=StubRouter()),
        ):
            generated = self.client.post(
                "/api/ai/generate",
                json={
                    "user_input": "тихий стеклянный дом в сосновом лесу",
                    "task": {"family": "flux", "scenario": "architecture_interior"},
                },
            )

        self.assertEqual(generated.status_code, 201)
        generated_payload = generated.get_json()
        self.assertEqual(generated_payload["job"]["task"]["operation"], "generate")
        self.assertEqual(generated_payload["job"]["status"], "waiting_for_review")
        self.assertEqual(generated_payload["context"]["family"], "flux")
        self.assertEqual(captured["api_key"], "resolved-server-side-secret")
        self.assertNotIn("resolved-server-side-secret", generated.get_data(as_text=True))

        prompt_draft_id = generated_payload["prompt_draft"]["id"]
        workflow = self.client.post(
            "/api/editor/drafts",
            json={
                "template_id": "core-flux",
                "ai_prompt_draft_id": prompt_draft_id,
            },
        )
        self.assertEqual(workflow.status_code, 201)
        workflow_draft = workflow.get_json()["draft"]
        self.assertEqual(workflow_draft["status"], "editing")
        self.assertEqual(workflow_draft["ai_prompt_draft_id"], prompt_draft_id)
        self.assertEqual(
            workflow_draft["values"]["positive_prompt"],
            "A quiet glass house at blue hour",
        )

        conn = database.get_conn()
        try:
            run_count = conn.execute("SELECT COUNT(*) FROM workflow_runs").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(run_count, 0)

    def test_prompt_capabilities_exclude_unsupported_scenarios(self) -> None:
        response = self.client.get("/api/ai/prompt-capabilities")
        self.assertEqual(response.status_code, 200)
        families = {item["id"]: item for item in response.get_json()["families"]}
        pony = {item["id"]: item["status"] for item in families["pony"]["scenarios"]}
        self.assertNotIn("graphic_design_text", pony)
        self.assertNotIn("multi_character", pony)
        self.assertEqual(pony["product_object"], "limited")

    def test_translate_creates_new_editor_draft_and_preserves_source(self) -> None:
        captured = {}
        profile = {
            "id": "saved-translator",
            "kind": "openai_compatible",
            "name": "Saved translator",
            "model": "translation-model",
        }

        class StubProfileStore:
            @staticmethod
            def list():
                return {
                    "profiles": [],
                    "defaults": {"text_profile_id": profile["id"]},
                }

            @staticmethod
            def get(profile_id):
                self.assertEqual(profile_id, profile["id"])
                return profile

            @staticmethod
            def resolve_api_key(resolved_profile):
                self.assertIs(resolved_profile, profile)
                return "server-side-translation-secret"

        class StubTranslationService:
            @staticmethod
            def translate(**kwargs):
                captured.update(kwargs)
                translated = PromptResult(
                    positive_prompt="a quiet glass house in the northern forest",
                    negative_prompt="text, watermark",
                )
                store = AIJobStore()
                job = store.create(
                    task=kwargs["task"],
                    execution_backend="openai_compatible",
                    provider_profile_id=profile["id"],
                    model_id=profile["model"],
                    user_input="translation request",
                )
                store.save_draft(
                    job.id,
                    PromptDraft(
                        positive_prompt=translated.positive_prompt,
                        negative_prompt=translated.negative_prompt,
                        source_kind=PromptDraftSource.TRANSLATION,
                        source_payload={
                            "source": kwargs["source"].model_dump(mode="json"),
                            "target_language": kwargs["target_language"],
                        },
                        versions={"family": "1", "operation": "1"},
                    ),
                )
                store.complete(job.id, result=translated)
                translation = PromptTranslationStore().save(
                    job_id=job.id,
                    source=kwargs["source"],
                    translated=PromptText(
                        positive_prompt=translated.positive_prompt,
                        negative_prompt=translated.negative_prompt,
                    ),
                    source_language=kwargs["source_language"],
                    target_language=kwargs["target_language"],
                )
                return SimpleNamespace(
                    execution=SimpleNamespace(job_id=job.id),
                    translation=translation,
                )

        with (
            patch("app.ai.routes._store", return_value=StubProfileStore()),
            patch(
                "app.ai.routes.PromptTranslationService",
                return_value=StubTranslationService(),
            ),
        ):
            response = self.client.post(
                "/api/ai/translate",
                json={
                    "source_language": "ru",
                    "target_language": "en",
                    "source": {
                        "positive_prompt": "тихий стеклянный дом в северном лесу",
                        "negative_prompt": "текст, водяной знак",
                    },
                    "task": {
                        "family": "sdxl",
                        "scenario": "architecture_interior",
                    },
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(payload["job"]["task"]["operation"], "translate")
        self.assertEqual(payload["context"]["operation"], "translate")
        self.assertEqual(
            payload["translation"]["source"]["positive_prompt"],
            "тихий стеклянный дом в северном лесу",
        )
        self.assertEqual(
            payload["translation"]["translated"]["positive_prompt"],
            "a quiet glass house in the northern forest",
        )
        self.assertEqual(captured["api_key"], "server-side-translation-secret")
        self.assertNotIn("server-side-translation-secret", response.get_data(as_text=True))

        prompt_draft_id = payload["prompt_draft"]["id"]
        workflow = self.client.post(
            "/api/editor/drafts",
            json={
                "template_id": "core-image",
                "ai_prompt_draft_id": prompt_draft_id,
            },
        )
        self.assertEqual(workflow.status_code, 201)
        workflow_payload = workflow.get_json()
        workflow_draft = workflow_payload["draft"]
        self.assertEqual(workflow_draft["status"], "editing")
        self.assertEqual(workflow_payload["ai_prompt_context"]["operation"], "translate")
        self.assertEqual(
            workflow_payload["ai_prompt_translation"]["source"]["positive_prompt"],
            "тихий стеклянный дом в северном лесу",
        )
        self.assertEqual(
            workflow_draft["values"]["positive_prompt"],
            "a quiet glass house in the northern forest",
        )
        self.assertEqual(workflow_draft["values"]["negative_prompt"], "text, watermark")

        reloaded = self.client.get(f"/api/editor/drafts/{workflow_draft['id']}")
        self.assertEqual(reloaded.status_code, 200)
        self.assertEqual(
            reloaded.get_json()["ai_prompt_context"]["operation"],
            "translate",
        )
        stored_translation = PromptTranslationStore().get(payload["job"]["id"])
        self.assertEqual(stored_translation.source_language, "ru")
        self.assertEqual(stored_translation.target_language, "en")

        conn = database.get_conn()
        try:
            run_count = conn.execute("SELECT COUNT(*) FROM workflow_runs").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(run_count, 0)

    def test_editor_exposes_ai_prompt_draft_controls(self) -> None:
        response = self.client.get("/editor")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="ai-prompt-open"', response.data)
        self.assertIn(b'id="ai-prompt-dialog"', response.data)
        self.assertIn(b'id="translate-prompt-open"', response.data)
        self.assertIn(b'id="translate-prompt-dialog"', response.data)
        self.assertIn(b'id="prompt-provenance-dialog"', response.data)
        self.assertIn(b'Generation stays manual', response.data)


if __name__ == "__main__":
    unittest.main()
