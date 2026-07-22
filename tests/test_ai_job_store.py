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
    PromptDraftSource,
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

    def test_prompt_edits_create_durable_revisions_with_execution_context(self) -> None:
        job = self.store.create(
            task=self.task,
            execution_backend="openai_compatible",
            provider_profile_id="vision-local",
            model_id="vision-model-1",
            user_input="Reconstruct this asset.",
        )
        original = self.store.save_draft(
            job.id,
            PromptDraft(
                positive_prompt="glass bottle",
                source_kind=PromptDraftSource.SCENE_SPEC,
                source_payload={"subjects": [{"kind": "glass bottle"}]},
                versions={"family": "1", "output_contract": "1"},
            ),
        )
        revised = self.store.revise_draft(
            original.id,
            positive_prompt="clear glass bottle, centered",
            negative_prompt="duplicate bottle",
        )

        self.assertNotEqual(revised.id, original.id)
        self.assertEqual(revised.parent_draft_id, original.id)
        self.assertEqual(revised.draft.source_kind, PromptDraftSource.MANUAL)
        self.assertEqual(
            revised.draft.source_payload,
            {"revised_from_draft_id": original.id},
        )
        self.assertEqual(revised.draft.versions, original.draft.versions)

        snapshot = self.store.get(job.id)
        self.assertEqual(len(snapshot.drafts), 2)
        self.assertEqual(
            snapshot.drafts[0].draft.source_payload,
            {"subjects": [{"kind": "glass bottle"}]},
        )
        context = self.store.draft_context(snapshot.drafts[-1], snapshot.job)
        self.assertEqual(context.family, "flux")
        self.assertEqual(context.checkpoint_profile, "flux-dev")
        self.assertEqual(context.scenario, "product_object")
        self.assertEqual(context.execution_backend, "openai_compatible")
        self.assertEqual(context.provider_profile_id, "vision-local")
        self.assertEqual(context.model_id, "vision-model-1")
        self.assertEqual(context.output_contract, "prompt_result")
        self.assertEqual(context.technical_status, AIJobStatus.QUEUED)

    def test_draft_revision_rejects_cross_job_parent_and_empty_content(self) -> None:
        first_job = self.store.create(task=self.task, execution_backend="opencode")
        second_job = self.store.create(task=self.task, execution_backend="opencode")
        first_draft = self.store.save_draft(
            first_job.id, PromptDraft(positive_prompt="first")
        )

        with self.assertRaisesRegex(AIJobStoreError, "same AI job"):
            self.store.save_draft(
                second_job.id,
                PromptDraft(positive_prompt="second"),
                parent_draft_id=first_draft.id,
            )
        with self.assertRaisesRegex(AIJobStoreError, "Invalid prompt draft revision"):
            self.store.revise_draft(
                first_draft.id,
                positive_prompt="",
                negative_prompt="",
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

    def test_generated_draft_waits_for_review_and_accepts_an_edited_revision(self) -> None:
        job = self.store.create(task=self.task, execution_backend="opencode")
        bundle = PromptCompiler().compile(self.task)
        self.store.mark_running(job.id, bundle)
        generated = self.store.save_draft(
            job.id,
            PromptDraft(
                positive_prompt="generated bottle prompt",
                negative_prompt="generated defects",
                versions=bundle.versions,
            ),
        )
        waiting = self.store.wait_for_review(
            job.id,
            result=PromptResult(
                positive_prompt=generated.draft.positive_prompt,
                negative_prompt=generated.draft.negative_prompt,
            ),
            execution_metadata={"transport": "opencode"},
            bundle=bundle,
        )
        self.assertEqual(waiting.job.status, AIJobStatus.WAITING_FOR_REVIEW)
        self.assertIsNone(waiting.job.completed_at)

        edited = self.store.revise_draft(
            generated.id,
            positive_prompt="reviewed bottle prompt",
        )
        accepted = self.store.accept_draft(job.id, draft_id=edited.id)
        self.assertEqual(accepted.job.status, AIJobStatus.COMPLETED)
        self.assertEqual(accepted.result.positive_prompt, "reviewed bottle prompt")
        self.assertEqual(accepted.result.negative_prompt, "generated defects")
        self.assertEqual(accepted.execution_metadata, {"transport": "opencode"})
        self.assertIsNotNone(accepted.job.completed_at)

    def test_waiting_job_can_be_cancelled_but_not_completed_afterwards(self) -> None:
        job = self.store.create(task=self.task, execution_backend="opencode")
        self.store.save_draft(job.id, PromptDraft(positive_prompt="draft"))
        self.store.wait_for_review(
            job.id,
            result=PromptResult(positive_prompt="draft"),
        )
        cancelled = self.store.cancel(job.id)
        self.assertEqual(cancelled.status, AIJobStatus.CANCELLED)
        with self.assertRaisesRegex(AIJobStoreError, "cancelled.*completed"):
            self.store.accept_draft(job.id)

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

    def test_rejects_unbounded_user_input_before_writing(self) -> None:
        with self.assertRaisesRegex(AIJobStoreError, "exceeds 100000"):
            self.store.create(
                task=self.task,
                execution_backend="openai_compatible",
                user_input="x" * 100_001,
            )

    def test_legacy_prompt_drafts_are_migrated_without_losing_content(self) -> None:
        job = self.store.create(task=self.task, execution_backend="opencode")
        conn = database.get_conn()
        try:
            conn.execute("DROP TABLE ai_prompt_drafts")
            conn.execute(
                """CREATE TABLE ai_prompt_drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL REFERENCES ai_jobs(id) ON DELETE CASCADE,
                    schema_version TEXT NOT NULL,
                    positive_prompt TEXT NOT NULL DEFAULT '',
                    negative_prompt TEXT NOT NULL DEFAULT '',
                    versions_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )"""
            )
            conn.execute(
                """INSERT INTO ai_prompt_drafts (
                    job_id, schema_version, positive_prompt, versions_json
                ) VALUES (?, '1', 'legacy prompt', '{"family":"1"}')""",
                (job.id,),
            )
            conn.commit()
        finally:
            conn.close()

        database.init_db()
        migrated = AIJobStore().get(job.id).drafts[0]
        self.assertEqual(migrated.draft.positive_prompt, "legacy prompt")
        self.assertEqual(migrated.draft.source_kind, PromptDraftSource.USER_TEXT)
        self.assertEqual(migrated.draft.source_payload, {})
        self.assertEqual(migrated.draft.versions, {"family": "1"})
        self.assertEqual(migrated.updated_at, migrated.created_at)

    def test_legacy_ai_job_status_constraint_is_migrated_with_children(self) -> None:
        job = self.store.create(task=self.task, execution_backend="opencode")
        self.store.save_scene_spec(job.id, SceneSpec(uncertain_details=("label",)))
        self.store.save_draft(job.id, PromptDraft(positive_prompt="preserved"))
        conn = database.get_conn()
        try:
            current_sql = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='ai_jobs'"
            ).fetchone()["sql"]
            legacy_sql = current_sql.replace(
                "CREATE TABLE ai_jobs", "CREATE TABLE ai_jobs_legacy", 1
            ).replace(", 'waiting_for_review'", "", 1)
            columns = (
                "id, asset_id, family, operation, scenario, modifiers_json, "
                "checkpoint_profile, output_contract, execution_backend, "
                "provider_profile_id, model_id, user_input, status, "
                "bundle_metadata_json, technical_error, created_at, updated_at, "
                "started_at, completed_at"
            )
            conn.commit()
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.executescript(f"""
                BEGIN IMMEDIATE;
                {legacy_sql};
                INSERT INTO ai_jobs_legacy ({columns}) SELECT {columns} FROM ai_jobs;
                DROP TABLE ai_jobs;
                ALTER TABLE ai_jobs_legacy RENAME TO ai_jobs;
                COMMIT;
            """)
            conn.execute("PRAGMA foreign_keys=ON")
        finally:
            conn.close()

        database.init_db()
        migrated = AIJobStore()
        snapshot = migrated.get(job.id)
        self.assertEqual(snapshot.scene_spec.uncertain_details, ("label",))
        self.assertEqual(snapshot.drafts[0].draft.positive_prompt, "preserved")
        migrated.wait_for_review(
            job.id,
            result=PromptResult(positive_prompt="preserved"),
        )
        self.assertEqual(
            migrated.get(job.id).job.status,
            AIJobStatus.WAITING_FOR_REVIEW,
        )


if __name__ == "__main__":
    unittest.main()
