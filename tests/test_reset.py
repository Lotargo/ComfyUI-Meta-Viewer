from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import database as db
from app.config_store import ConfigStore, ConfigStoreError
from app.indexing import index_source_directory
from app.main import app, configure_runtime
from app.paths import RuntimePaths, build_runtime_paths
from app.reset_service import (
    ResetOperationError,
    ResetResult,
    database_files,
    reset_application_index,
)


class ResetTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.paths = build_runtime_paths(
            {
                "COMFY_META_DATA_DIR": str(self.root / "data"),
                "COMFY_META_CACHE_DIR": str(self.root / "cache"),
            },
            project_root=self.root,
        )
        self.paths.ensure_directories()
        self.old_db_path = db.get_db_path()
        db.set_db_path(self.paths.database)
        db.init_db()
        self.old_config = {
            key: app.config.get(key)
            for key in (
                "TESTING",
                "THUMBNAIL_FOLDER",
                "PREVIEW_FOLDER",
                "CUTOUT_FOLDER",
                "CONFIG_FILE",
                "UPLOAD_FOLDER",
            )
        }
        app.config.update(TESTING=True, **self.paths.flask_config())

    def tearDown(self) -> None:
        db.set_db_path(self.old_db_path)
        app.config.update(self.old_config)
        self.temp_dir.cleanup()

    def make_source(self) -> tuple[Path, Path]:
        source = self.root / "source files" / "кириллица 🖼"
        source.mkdir(parents=True)
        image = source / "image one.png"
        Image.new("RGB", (2, 2), color="green").save(image)
        return source, image

    def index_source(self, source: Path) -> None:
        index_source_directory(
            source,
            thumbnail_dir=self.paths.thumbnails,
            preview_dir=self.paths.previews,
            cutout_dir=self.paths.cutouts,
        )


class ConfigStoreTest(ResetTestCase):
    def test_sources_are_saved_atomically_and_deduplicated(self) -> None:
        source, _ = self.make_source()
        store = ConfigStore(self.paths.config)
        store.add_source(source)
        store.add_source(source)

        self.assertEqual(store.active_sources(), [source.resolve()])
        self.assertFalse(store.temporary_path.exists())
        raw = json.loads(self.paths.config.read_text(encoding="utf-8"))
        self.assertEqual(raw["version"], 2)
        self.assertEqual(len(raw["sources"]), 1)

    def test_existing_inactive_source_is_reactivated(self) -> None:
        source, _ = self.make_source()
        store = ConfigStore(self.paths.config)
        store.save({
            "version": 1,
            "sources": [{"path": str(source), "active": False}],
        })

        store.add_source(source)

        self.assertEqual(store.active_sources(), [source.resolve()])

    def test_derived_folder_removes_its_saved_source(self) -> None:
        source, _ = self.make_source()
        store = ConfigStore(self.paths.config)
        store.add_source(source)

        removed = store.remove_source_for_index_path(f"{source} (no metadata)")

        self.assertTrue(removed)
        self.assertEqual(store.active_sources(), [])

    def test_corrupt_configuration_is_reported_but_factory_delete_still_works(self) -> None:
        self.paths.config.write_text("{broken", encoding="utf-8")
        store = ConfigStore(self.paths.config)
        with self.assertRaises(ConfigStoreError):
            store.active_sources()

        store.delete()
        self.assertFalse(self.paths.config.exists())


class PhysicalResetTest(ResetTestCase):
    def test_reset_deletes_database_sidecars_and_caches_then_reindexes_sources(self) -> None:
        source, image = self.make_source()
        before = image.read_bytes()
        ConfigStore(self.paths.config).add_source(source)
        self.index_source(source)
        db.insert_upload_image("uploaded.png", b"uploaded original", True)

        cache_files = []
        for directory, name in (
            (self.paths.thumbnails, "1.jpg"),
            (self.paths.previews, "1-preview.jpg"),
            (self.paths.cutouts, "1.png"),
        ):
            path = directory / name
            path.write_bytes(b"cache")
            cache_files.append(path)
        for sidecar in database_files(self.paths.database)[:2]:
            sidecar.write_bytes(b"stale sidecar")

        result = reset_application_index(self.paths)

        self.assertEqual(result.reindexed_sources, [str(source.resolve())])
        self.assertEqual(result.skipped_sources, [])
        self.assertTrue(self.paths.database.is_file())
        self.assertTrue(self.paths.config.is_file())
        self.assertTrue(all(not path.exists() for path in cache_files))
        self.assertTrue(all(not path.exists() for path in database_files(self.paths.database)[:2]))
        self.assertEqual(image.read_bytes(), before)
        diagnostics = db.get_diagnostics()
        self.assertEqual(diagnostics["folders"], 1)
        self.assertEqual(diagnostics["images"], 1)
        self.assertEqual(diagnostics["uploads"], 0)

    def test_factory_reset_removes_configuration_without_touching_sources(self) -> None:
        source, image = self.make_source()
        before = image.read_bytes()
        ConfigStore(self.paths.config).add_source(source)
        self.index_source(source)

        result = reset_application_index(self.paths, factory_reset=True)

        self.assertTrue(result.factory_reset)
        self.assertFalse(self.paths.config.exists())
        self.assertEqual(db.get_diagnostics()["folders"], 0)
        self.assertEqual(image.read_bytes(), before)

    def test_corrupt_database_can_be_physically_recreated(self) -> None:
        self.paths.database.write_bytes(b"not a sqlite database")
        for sidecar in database_files(self.paths.database)[:2]:
            sidecar.write_bytes(b"broken")

        reset_application_index(self.paths)

        self.assertEqual(db.get_diagnostics()["images"], 0)
        self.assertTrue(self.paths.database.is_file())

    def test_database_delete_failure_is_reported_and_not_hidden(self) -> None:
        original_unlink = Path.unlink

        def fail_database_unlink(path: Path, *args, **kwargs):
            if path == self.paths.database:
                raise PermissionError("database is locked")
            return original_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", autospec=True, side_effect=fail_database_unlink):
            with self.assertRaises(ResetOperationError) as raised:
                reset_application_index(self.paths)

        self.assertIn("database is locked", str(raised.exception))
        self.assertTrue(self.paths.database.exists())

    def test_missing_saved_source_is_retained_and_reported_as_skipped(self) -> None:
        missing = self.root / "offline drive" / "images"
        ConfigStore(self.paths.config).add_source(missing)

        result = reset_application_index(self.paths)

        self.assertEqual(result.reindexed_sources, [])
        self.assertEqual(result.skipped_sources[0]["path"], str(missing.resolve()))
        self.assertEqual(ConfigStore(self.paths.config).active_sources(), [missing.resolve()])


class DatabaseMaintenanceTest(ResetTestCase):
    def test_maintenance_wait_timeout_reports_open_connections(self) -> None:
        connection = db.get_conn()
        try:
            with self.assertRaises(db.DatabaseMaintenanceError):
                with db.database_maintenance(timeout=0.01):
                    pass
        finally:
            connection.close()

    def test_maintenance_rejects_connections_from_other_threads(self) -> None:
        errors: list[Exception] = []

        def connect() -> None:
            try:
                db.get_conn()
            except Exception as exc:
                errors.append(exc)

        with db.database_maintenance():
            thread = threading.Thread(target=connect)
            thread.start()
            thread.join()

        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], db.DatabaseMaintenanceError)


class SourceMigrationTest(ResetTestCase):
    def test_existing_derived_index_folder_is_migrated_to_source_config(self) -> None:
        source, _ = self.make_source()
        db.upsert_folder(f"{source} (no metadata)")
        self.paths.config.unlink(missing_ok=True)

        configure_runtime(self.paths)

        self.assertEqual(
            ConfigStore(self.paths.config).active_sources(),
            [source.resolve()],
        )


class ResetApiTest(ResetTestCase):
    def test_reset_endpoints_require_distinct_confirmations(self) -> None:
        client = app.test_client()
        self.assertEqual(client.post("/api/reset-index", json={}).status_code, 400)
        self.assertEqual(client.post("/api/factory-reset", json={}).status_code, 400)

    def test_factory_reset_endpoint_uses_separate_operation(self) -> None:
        result = ResetResult(factory_reset=True)
        with (
            patch("app.main.reset_application_index", return_value=result) as reset,
            patch("app.worker.start_worker"),
        ):
            response = app.test_client().post(
                "/api/factory-reset",
                json={"confirm": "factory-reset"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["factory_reset"])
        reset.assert_called_once()
        self.assertTrue(reset.call_args.kwargs["factory_reset"])

    def test_deleting_an_index_folder_forgets_its_saved_source(self) -> None:
        source, _ = self.make_source()
        ConfigStore(self.paths.config).add_source(source)
        folder_id = db.upsert_folder(str(source))

        response = app.test_client().delete(f"/api/folders/{folder_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ConfigStore(self.paths.config).active_sources(), [])

    def test_ui_exposes_separate_reset_actions_and_warnings(self) -> None:
        html = (Path(__file__).parents[1] / "app" / "templates" / "index.html").read_text(
            encoding="utf-8"
        )
        events = (
            Path(__file__).parents[1] / "app" / "static" / "js" / "events.js"
        ).read_text(encoding="utf-8")
        self.assertIn('id="btn-reset-index"', html)
        self.assertIn('id="btn-factory-reset"', html)
        self.assertIn("uploaded originals", events)
        self.assertIn("virtual albums", events)
        self.assertIn("browser preferences", events)


if __name__ == "__main__":
    unittest.main()
