from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app import database
from app.ai.job_store import AIJobStatus, AIJobStore
from app.ai.prompting import PromptFamily
from app.ai.remix import RemixPromptSource, RemixRequest, RemixService


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
        self.temp_dir.cleanup()

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


if __name__ == "__main__":
    unittest.main()
