from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app import database
from app.ai.job_store import (
    AIJobStatus,
    AIJobStore,
    AIJobStoreError,
    PromptDraft,
)
from app.ai.prompting import (
    PromptCompiler,
    PromptFamily,
    PromptModifier,
    PromptOperation,
    PromptResult,
    PromptScenario,
    PromptTask,
    SceneComposition,
    SceneSpec,
    SceneSubject,
)


class AIJobStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()
        self.store = AIJobStore()
        self.task = PromptTask(
            family=PromptFamily.FLUX,
            operation=PromptOperation.RECONSTRUCT,
            scenario=PromptScenario.PRODUCT_OBJECT,
            modifiers=(PromptModifier.SAFE,),
            checkpoint_profile="flux-dev",
        )

    def tearDown(self) -> None:
        database.set_db_path(self.old_db_path)
        self.temp_dir.cleanup()

    def test_persists_complete_backend_neutral_execution_state(self) -> None:
        job = self.store.create(
            task=self.task,
            execution_backend="openai_compatible",
            provider_profile_id="local-mimo",
            model_id="mimo-v2.5-free",
            user_input="Reconstruct the bottle.",
        )
        self.assertEqual(job.status, AIJobStatus.QUEUED)
        self.assertEqual(job.task, self.task)

        bundle = PromptCompiler().compile(self.task)
        running = self.store.mark_running(job.id, bundle)
        self.assertEqual(running.status, AIJobStatus.RUNNING)
        self.assertEqual(running.bundle_metadata["versions"], bundle.versions)

        scene_spec = SceneSpec(
            recommended_scenario=PromptScenario.PRODUCT_OBJECT,
            subjects=(SceneSubject(kind="glass perfume bottle", position="center"),),
            composition=SceneComposition(background="warm beige gradient"),
        )
        self.store.save_scene_spec(job.id, scene_spec)
        draft = PromptDraft(
            positive_prompt="clear glass perfume bottle, centered product photo",
            versions=bundle.versions,
        )
        stored_draft = self.store.save_draft(job.id, draft)
        self.assertGreater(stored_draft.id, 0)

        result = PromptResult(
            positive_prompt="clear glass perfume bottle, centered product photo",
            negative_prompt="distorted label, duplicate bottle",
        )
        snapshot = self.store.complete(
            job.id,
            result=result,
            execution_metadata={"latency_ms": 123, "transport": "openai_compatible"},
            bundle=bundle,
        )

        self.assertEqual(snapshot.job.status, AIJobStatus.COMPLETED)
        self.assertEqual(snapshot.scene_spec, scene_spec)
        self.assertEqual(snapshot.drafts[0].draft, draft)
        self.assertEqual(snapshot.result, result)
        self.assertEqual(snapshot.execution_metadata["latency_ms"], 123)
        self.assertIsNotNone(snapshot.job.started_at)
        self.assertIsNotNone(snapshot.job.completed_at)

    def test_scene_spec_is_editable_and_drafts_keep_history(self) -> None:
        job = self.store.create(task=self.task, execution_backend="opencode")
        first = SceneSpec(uncertain_details=("label text",))
        corrected = SceneSpec(uncertain_details=())
        self.store.save_scene_spec(job.id, first)
        self.store.save_scene_spec(job.id, corrected)
        self.store.save_draft(job.id, PromptDraft(positive_prompt="first draft"))
        self.store.save_draft(job.id, PromptDraft(positive_prompt="second draft"))

        snapshot = self.store.get(job.id)
        self.assertEqual(snapshot.scene_spec, corrected)
        self.assertEqual(
            [item.draft.positive_prompt for item in snapshot.drafts],
            ["first draft", "second draft"],
        )

    def test_failure_is_terminal_and_does_not_create_a_result(self) -> None:
        job = self.store.create(task=self.task, execution_backend="opencode")
        failed = self.store.fail(job.id, "provider temporarily unavailable")
        self.assertEqual(failed.status, AIJobStatus.FAILED)
        self.assertEqual(failed.technical_error, "provider temporarily unavailable")
        self.assertIsNone(self.store.get(job.id).result)

        with self.assertRaisesRegex(AIJobStoreError, "failed.*completed"):
            self.store.complete(
                job.id,
                result=PromptResult(positive_prompt="must not be saved"),
            )

    def test_database_foreign_keys_and_reset_semantics_are_preserved(self) -> None:
        with self.assertRaisesRegex(AIJobStoreError, "FOREIGN KEY"):
            self.store.create(
                task=self.task,
                execution_backend="openai_compatible",
                asset_id=999,
            )

        job = self.store.create(task=self.task, execution_backend="opencode")
        conn = database.get_conn()
        try:
            conn.execute("DELETE FROM ai_jobs WHERE id=?", (job.id,))
            conn.commit()
            counts = {
                table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "ai_jobs",
                    "ai_scene_specs",
                    "ai_prompt_drafts",
                    "ai_results",
                )
            }
        finally:
            conn.close()
        self.assertEqual(counts, {name: 0 for name in counts})


if __name__ == "__main__":
    unittest.main()
