"""Durable trash queue: instant accept, tombstones, crash resume, idempotency."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import database
from app import library as media_library
from app import job_worker
from app.indexing import index_source_directory
from app.main import app
from app.schemas import AssetInsertRow


def _write_files(directory: Path, names: list[str]) -> None:
    for name in names:
        (directory / name).write_bytes(b"fake-image-bytes:" + name.encode())


def _insert_named(folder_id: int, names: list[str]) -> dict[str, int]:
    folder = database.get_folder_record(folder_id)
    root = Path(str(folder["path"]))
    rows = []
    for name in names:
        stat = (root / name).stat()
        rows.append(
            AssetInsertRow(
                rel_path=name,
                file_name=name,
                file_size=stat.st_size,
                file_mtime=stat.st_mtime,
            )
        )
    database.insert_assets(folder_id, rows)
    conn = database.get_conn()
    try:
        return {
            str(row["file_name"]): int(row["id"])
            for row in conn.execute(
                "SELECT id, file_name FROM images WHERE folder_id = ?",
                (folder_id,),
            ).fetchall()
        }
    finally:
        conn.close()


class TrashQueueTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()
        self.media_dir = Path(self.temp_dir.name) / "media"
        self.media_dir.mkdir()
        self.cache_dir = Path(self.temp_dir.name) / "cache"
        (self.cache_dir / "thumbnails").mkdir(parents=True)
        (self.cache_dir / "previews").mkdir()
        (self.cache_dir / "cutouts").mkdir()
        _write_files(self.media_dir, ["a.png", "b.png", "c.png"])
        self.folder_id = database.upsert_source(str(self.media_dir), name="media")
        self.ids = _insert_named(self.folder_id, ["a.png", "b.png", "c.png"])
        self.client = app.test_client()
        self._patcher = patch("app.job_worker.send2trash")
        self.mock_trash = self._patcher.start()
        self._paths_patcher = patch(
            "app.job_worker.build_runtime_paths",
            return_value=SimpleNamespace(
                thumbnails=self.cache_dir / "thumbnails",
                previews=self.cache_dir / "previews",
                cutouts=self.cache_dir / "cutouts",
            ),
        )
        self._paths_patcher.start()

    def tearDown(self) -> None:
        try:
            job_worker.stop_job_worker(wait=True, timeout=5.0)
        finally:
            self._patcher.stop()
            self._paths_patcher.stop()
            database.set_db_path(self.old_db_path)
            try:
                self.temp_dir.cleanup()
            except Exception:
                pass

    def _listed_ids(self) -> list[int]:
        result = media_library.get_assets(
            collection="all", source_id=self.folder_id, sort_by="date"
        )
        return [int(asset["id"]) for asset in result["assets"]]

    def _tombstone_count(self) -> int:
        conn = database.get_conn()
        try:
            return int(
                conn.execute("SELECT COUNT(*) AS c FROM trash_tombstones").fetchone()[
                    "c"
                ]
            )
        finally:
            conn.close()

    def _pending_jobs(self) -> list[dict]:
        conn = database.get_conn()
        try:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT id, op, status FROM job_queue"
                ).fetchall()
            ]
        finally:
            conn.close()

    def test_trash_route_hides_rows_instantly_and_queues_files(self) -> None:
        response = self.client.post(
            "/api/library/assets/trash",
            json={"asset_ids": [self.ids["a.png"], self.ids["b.png"]]},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(
            sorted(payload["removed_ids"]),
            sorted([self.ids["a.png"], self.ids["b.png"]]),
        )
        # Rows are gone from listings immediately…
        self.assertEqual(self._listed_ids(), [self.ids["c.png"]])
        # …but the files are still on disk until the worker runs…
        self.assertTrue((self.media_dir / "a.png").is_file())
        # …with tombstones + exactly one job covering the crash window.
        self.assertEqual(self._tombstone_count(), 2)
        jobs = self._pending_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["op"], "trash_assets")
        self.assertEqual(jobs[0]["status"], "pending")
        self.mock_trash.assert_not_called()

    def test_worker_completes_trash_and_clears_caches(self) -> None:
        (self.cache_dir / "thumbnails" / f"{self.ids['a.png']}.jpg").write_bytes(b"x")
        self.client.post(
            "/api/library/assets/trash", json={"asset_ids": [self.ids["a.png"]]}
        )
        self.assertTrue(job_worker.process_pending_job())
        trashed = {Path(call.args[0]).name for call in self.mock_trash.call_args_list}
        self.assertEqual(trashed, {"a.png"})
        self.assertEqual(self._tombstone_count(), 0)
        self.assertEqual(self._pending_jobs(), [])
        self.assertFalse(
            (self.cache_dir / "thumbnails" / f"{self.ids['a.png']}.jpg").exists()
        )
        # Queue drained: nothing left to do.
        self.assertFalse(job_worker.process_pending_job())

    def test_missing_file_is_already_gone_not_an_error(self) -> None:
        self.client.post(
            "/api/library/assets/trash", json={"asset_ids": [self.ids["a.png"]]}
        )
        (self.media_dir / "a.png").unlink()
        self.assertTrue(job_worker.process_pending_job())
        self.mock_trash.assert_not_called()
        self.assertEqual(self._tombstone_count(), 0)
        self.assertEqual(self._pending_jobs(), [])

    def test_reconcile_does_not_resurrect_trashed_files(self) -> None:
        self.client.post(
            "/api/library/assets/trash", json={"asset_ids": [self.ids["a.png"]]}
        )
        result = index_source_directory(
            self.media_dir,
            thumbnail_dir=self.cache_dir / "thumbnails",
            cutout_dir=self.cache_dir / "cutouts",
            preview_dir=self.cache_dir / "previews",
            name="media",
        )
        self.assertEqual(result.processed, 0)
        self.assertEqual(
            sorted(self._listed_ids()), sorted([self.ids["b.png"], self.ids["c.png"]])
        )

    def test_crash_mid_job_resumes_on_startup(self) -> None:
        self.client.post(
            "/api/library/assets/trash", json={"asset_ids": [self.ids["a.png"]]}
        )
        # Simulate a crash after claim: job stuck in 'running', files untouched.
        conn = database.get_conn()
        try:
            conn.execute("UPDATE job_queue SET status = 'running'")
            conn.commit()
        finally:
            conn.close()
        self.assertFalse(job_worker.process_pending_job())
        # Startup resume picks it up and finishes the work.
        self.assertEqual(database.reset_stuck_jobs(), 1)
        self.assertTrue(job_worker.process_pending_job())
        self.assertEqual(
            {Path(call.args[0]).name for call in self.mock_trash.call_args_list},
            {"a.png"},
        )
        self.assertEqual(self._tombstone_count(), 0)

    def test_poison_job_parks_as_dead_after_retries(self) -> None:
        job_id = database.enqueue_job("bogus_op", {})
        for _ in range(database.JOB_MAX_ATTEMPTS):
            conn = database.get_conn()
            try:
                # Jump the backoff so each attempt is immediately claimable.
                conn.execute(
                    "UPDATE job_queue SET run_after = datetime('now', '-1 minute')"
                    " WHERE id = ?",
                    (job_id,),
                )
                conn.commit()
            finally:
                conn.close()
            self.assertTrue(job_worker.process_pending_job())
        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT status, last_error FROM job_queue WHERE id = ?",
                (job_id,),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "dead")
        self.assertIn("bogus_op", row["last_error"])
        # Dead jobs are never re-claimed.
        self.assertFalse(job_worker.process_pending_job())

    def test_double_trash_reports_not_found(self) -> None:
        first = self.client.post(
            "/api/library/assets/trash", json={"asset_ids": [self.ids["a.png"]]}
        )
        self.assertTrue(first.get_json()["ok"])
        second = self.client.post(
            "/api/library/assets/trash", json={"asset_ids": [self.ids["a.png"]]}
        )
        payload = second.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["removed_ids"], [])
        self.assertEqual(len(payload["failures"]), 1)
        self.assertEqual(payload["failures"][0]["code"], "image_not_found")

    def test_upload_original_trashes_without_local_file(self) -> None:
        conn = sqlite3.connect(database.get_db_path())
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                "UPDATE images SET original_data = ? WHERE id = ?",
                (b"upload-bytes", self.ids["c.png"]),
            )
            conn.commit()
        finally:
            conn.close()
        response = self.client.post(
            "/api/library/assets/trash", json={"asset_ids": [self.ids["c.png"]]}
        )
        self.assertTrue(response.get_json()["ok"])
        self.assertTrue(job_worker.process_pending_job())
        self.mock_trash.assert_not_called()
        self.assertEqual(self._tombstone_count(), 0)

    def test_worker_thread_lifecycle(self) -> None:
        job_worker.start_job_worker()
        self.assertTrue(job_worker.stop_job_worker(wait=True, timeout=10.0))


if __name__ == "__main__":
    unittest.main()
