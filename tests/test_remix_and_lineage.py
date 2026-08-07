from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app import database
from app.ai.job_store import AIJobStatus, AIJobStore, PromptDraft, PromptDraftSource
from app.ai.prompting import (
    PromptFamily,
    PromptOperation,
    PromptScenario,
    PromptTask,
    SceneSpec,
)
from app.ai.remix import RemixError, RemixPromptSource, RemixRequest, RemixService


class RemixAndLineageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()

        conn = database.get_conn()
        try:
            folder_id = conn.execute(
                "INSERT INTO folders (path, name) VALUES ('/test', 'test')",
            ).lastrowid
            self.parent_id = conn.execute(
                """INSERT INTO images (
                    folder_id, rel_path, file_name, metadata_json
                ) VALUES (?, 'orig.png', 'orig.png', ?)""",
                (
                    folder_id,
                    json.dumps({
                        "prompt": "An ancient stone portal glowing in the misty forest",
                        "negative_prompt": "blurry, low quality",
                    }),
                ),
            ).lastrowid
            self.child_id = conn.execute(
                "INSERT INTO images (folder_id, rel_path, file_name) VALUES (?, 'remix.png', 'remix.png')",
                (folder_id,),
            ).lastrowid
            conn.commit()
        finally:
            conn.close()

        self.job_store = AIJobStore()
        self.service = RemixService(job_store=self.job_store)

    def tearDown(self) -> None:
        database.set_db_path(self.old_db_path)
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_create_remix_draft_from_asset_metadata(self) -> None:
        req = RemixRequest(
            asset_id=self.parent_id,
            prompt_source=RemixPromptSource.ORIGINAL_METADATA,
            target_family=PromptFamily.FLUX,
        )
        outcome = self.service.create_remix_draft(request=req)

        self.assertEqual(outcome.parent_asset_id, self.parent_id)
        self.assertEqual(outcome.job.status, AIJobStatus.WAITING_FOR_REVIEW)
        self.assertEqual(
            outcome.draft.draft.positive_prompt,
            "An ancient stone portal glowing in the misty forest",
        )
        self.assertEqual(
            outcome.draft.draft.negative_prompt,
            "blurry, low quality",
        )
        self.assertEqual(outcome.draft.draft.source_payload["parent_asset_id"], self.parent_id)

    def test_link_derived_asset_records_lineage(self) -> None:
        self.service.link_derived_asset(
            child_asset_id=self.child_id,
            parent_asset_id=self.parent_id,
        )

        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT derived_from_asset_id FROM images WHERE id=?",
                (self.child_id,),
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(row["derived_from_asset_id"], self.parent_id)

    def test_prompt_source_options_include_persisted_ai_operations(self) -> None:
        saved_drafts = {}
        for operation, positive in (
            (PromptOperation.TRANSLATE, "Translated stone portal"),
            (PromptOperation.ADAPT, "score_9, ancient stone portal"),
            (PromptOperation.RECONSTRUCT, "A reconstructed portal in forest mist"),
        ):
            job = self.job_store.create(
                task=PromptTask(
                    family=PromptFamily.SDXL,
                    operation=operation,
                    scenario=PromptScenario.LANDSCAPE_ENVIRONMENT,
                ),
                execution_backend="openai_compatible",
                asset_id=self.parent_id,
                user_input=positive,
            )
            if operation is PromptOperation.RECONSTRUCT:
                self.job_store.save_scene_spec(
                    job.id,
                    SceneSpec(recommended_scenario=PromptScenario.LANDSCAPE_ENVIRONMENT),
                )
            saved_drafts[operation] = self.job_store.save_draft(
                job.id,
                PromptDraft(
                    positive_prompt=positive,
                    negative_prompt="watermark",
                    source_kind={
                        PromptOperation.TRANSLATE: PromptDraftSource.TRANSLATION,
                        PromptOperation.ADAPT: PromptDraftSource.ADAPTATION,
                        PromptOperation.RECONSTRUCT: PromptDraftSource.SCENE_SPEC,
                    }[operation],
                ),
            )

        options = self.service.list_prompt_sources(self.parent_id)
        by_source = {option.prompt_source: option for option in options}

        self.assertIn(RemixPromptSource.ORIGINAL_METADATA, by_source)
        self.assertEqual(
            by_source[RemixPromptSource.TRANSLATION].prompt_draft_id,
            saved_drafts[PromptOperation.TRANSLATE].id,
        )
        self.assertEqual(
            by_source[RemixPromptSource.FAMILY_ADAPTATION].prompt_draft_id,
            saved_drafts[PromptOperation.ADAPT].id,
        )
        self.assertEqual(
            by_source[RemixPromptSource.SAVED_SCENE_SPEC].prompt_draft_id,
            saved_drafts[PromptOperation.RECONSTRUCT].id,
        )
        self.assertIn(RemixPromptSource.USER_EDITED, by_source)

        translated = self.service.create_remix_draft(
            request=RemixRequest(
                asset_id=self.parent_id,
                prompt_source=RemixPromptSource.TRANSLATION,
                prompt_draft_id=saved_drafts[PromptOperation.TRANSLATE].id,
                workflow_template_id="core-image",
                target_family=PromptFamily.SDXL,
            )
        )
        self.assertEqual(
            translated.draft.draft.positive_prompt,
            "Translated stone portal",
        )
        self.assertEqual(
            translated.draft.draft.source_payload["source_prompt_draft_id"],
            saved_drafts[PromptOperation.TRANSLATE].id,
        )

    def test_prompt_draft_from_unrelated_asset_is_rejected(self) -> None:
        job = self.job_store.create(
            task=PromptTask(
                family=PromptFamily.SDXL,
                operation=PromptOperation.TRANSLATE,
                scenario=PromptScenario.PORTRAIT,
            ),
            execution_backend="openai_compatible",
            asset_id=self.child_id,
            user_input="unrelated",
        )
        unrelated = self.job_store.save_draft(
            job.id,
            PromptDraft(
                positive_prompt="Unrelated translated portrait",
                source_kind=PromptDraftSource.TRANSLATION,
            ),
        )

        with self.assertRaisesRegex(RemixError, "not related"):
            self.service.create_remix_draft(
                request=RemixRequest(
                    asset_id=self.parent_id,
                    prompt_source=RemixPromptSource.TRANSLATION,
                    prompt_draft_id=unrelated.id,
                )
            )


if __name__ == "__main__":
    unittest.main()
