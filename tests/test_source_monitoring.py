from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import database as db
from app.config_store import ConfigStore
from app.indexing import index_source_directory
from app.main import app
from app.paths import build_runtime_paths
from app.source_monitor import SourceMonitor
from app.worker import stop_worker


class FakeObserver:
    def __init__(self) -> None:
        self.alive = False
        self.watches: list[object] = []

    def start(self) -> None:
        self.alive = True

    def stop(self) -> None:
        self.alive = False

    def join(self, _timeout: float | None = None) -> None:
        return None

    def is_alive(self) -> bool:
        return self.alive

    def schedule(self, _handler, _path: str, *, recursive: bool = False) -> object:
        watch = {"recursive": recursive}
        self.watches.append(watch)
        return watch

    def unschedule(self, watch: object) -> None:
        if watch in self.watches:
            self.watches.remove(watch)


def wait_until(predicate, *, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for source monitor state")


class SourceMonitoringTest(unittest.TestCase):
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
        self.old_app_config = {
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
        self.source = self.root / "cloud mirror" / "images"
        self.source.mkdir(parents=True)
        self.monitor: SourceMonitor | None = None

    def tearDown(self) -> None:
        if self.monitor is not None:
            self.monitor.stop()
        stop_worker(wait=True)
        app.config.update(self.old_app_config)
        db.set_db_path(self.old_db_path)
        self.temp_dir.cleanup()

    def make_image(self, relative: str, *, size: tuple[int, int] = (3, 3)) -> Path:
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, color="green").save(path)
        return path

    def index(self, *, recursive: bool = False):
        return index_source_directory(
            self.source,
            thumbnail_dir=self.paths.thumbnails,
            preview_dir=self.paths.previews,
            cutout_dir=self.paths.cutouts,
            recursive=recursive,
        )

    def start_monitor(self, *, reconnect_interval: float = 0.1) -> SourceMonitor:
        self.monitor = SourceMonitor(
            self.paths,
            debounce_seconds=0.05,
            stability_seconds=0.03,
            reconcile_interval=60.0,
            reconnect_interval=reconnect_interval,
            observer_factory=FakeObserver,
        )
        self.monitor.start()
        return self.monitor

    def test_recursive_reconciliation_is_optional(self) -> None:
        self.make_image("root.png")
        self.make_image("nested/child.png")

        result = self.index(recursive=False)
        self.assertEqual(set(db.get_folder_file_stats(result.folder_id)), {"root.png"})

        self.index(recursive=True)
        self.assertEqual(
            set(db.get_folder_file_stats(result.folder_id)),
            {"root.png", "nested/child.png"},
        )

        self.index(recursive=False)
        self.assertEqual(set(db.get_folder_file_stats(result.folder_id)), {"root.png"})

    def test_source_api_persists_controls_and_reconciles_enable(self) -> None:
        self.make_image("root.png")
        nested = self.make_image("nested/old.png")
        client = app.test_client()

        response = client.post(
            "/api/scan",
            json={"path": str(self.source), "recursive": True},
        )
        self.assertEqual(response.status_code, 200)
        source_id = response.get_json()["folder_id"]
        self.assertEqual(
            set(db.get_folder_file_stats(source_id)),
            {"root.png", "nested/old.png"},
        )

        response = client.patch(
            f"/api/folders/{source_id}",
            json={"enabled": False},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["folder"]["enabled"])
        self.assertEqual(db.get_images_page(None).total, 0)
        self.assertEqual(len(db.get_folder_image_ids(source_id)), 2)

        nested.unlink()
        self.make_image("nested/new.png")
        response = client.patch(
            f"/api/folders/{source_id}",
            json={"enabled": True},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(db.get_folder_file_stats(source_id)),
            {"root.png", "nested/new.png"},
        )

        response = client.patch(
            f"/api/folders/{source_id}",
            json={"recursive": False},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(db.get_folder_file_stats(source_id)), {"root.png"})

    def test_disabled_source_hides_assets_and_reconciles_on_enable(self) -> None:
        old_image = self.make_image("old.png")
        ConfigStore(self.paths.config).add_source(self.source)
        result = self.index()
        monitor = self.start_monitor()
        wait_until(lambda: db.get_folder_record(result.folder_id)["source_status"] == "available")

        monitor.update_source(result.folder_id, enabled=False)
        self.assertEqual(db.get_images_page(None).total, 0)
        self.assertEqual(len(db.get_folder_image_ids(result.folder_id)), 1)

        old_image.unlink()
        self.make_image("new.png")
        monitor.update_source(result.folder_id, enabled=True)
        wait_until(
            lambda: set(db.get_folder_file_stats(result.folder_id)) == {"new.png"}
        )
        self.assertEqual(db.get_images_page(None).total, 1)

    def test_unavailable_source_keeps_index_and_recovers(self) -> None:
        self.make_image("kept.png")
        ConfigStore(self.paths.config).add_source(self.source)
        result = self.index()
        monitor = self.start_monitor()
        wait_until(lambda: db.get_folder_record(result.folder_id)["source_status"] == "available")

        offline = self.source.with_name("images-offline")
        self.source.rename(offline)
        monitor.request_reconcile(result.folder_id)
        wait_until(lambda: db.get_folder_record(result.folder_id)["source_status"] == "unavailable")
        self.assertEqual(set(db.get_folder_file_stats(result.folder_id)), {"kept.png"})

        offline.rename(self.source)
        wait_until(lambda: db.get_folder_record(result.folder_id)["source_status"] == "available")
        self.assertEqual(set(db.get_folder_file_stats(result.folder_id)), {"kept.png"})

    def test_event_burst_is_coalesced_before_reconciliation(self) -> None:
        self.make_image("initial.png")
        ConfigStore(self.paths.config).add_source(self.source)
        result = self.index()
        monitor = self.start_monitor()
        wait_until(lambda: db.get_folder_record(result.folder_id)["source_status"] == "available")
        self.make_image("burst.png")

        with patch(
            "app.source_monitor.index_source_directory",
            wraps=index_source_directory,
        ) as reconcile:
            for _ in range(100):
                monitor._on_file_event(result.folder_id, {"burst.png"})
            wait_until(
                lambda: set(db.get_folder_file_stats(result.folder_id))
                == {"initial.png", "burst.png"}
            )

        self.assertEqual(reconcile.call_count, 1)

    def test_native_watcher_reflects_create_modify_rename_and_delete(self) -> None:
        ConfigStore(self.paths.config).add_source(self.source)
        self.monitor = SourceMonitor(
            self.paths,
            debounce_seconds=0.05,
            stability_seconds=0.03,
            reconcile_interval=60.0,
            reconnect_interval=0.1,
        )
        self.monitor.start()
        source_id = db.get_source_records()[0]["id"]
        wait_until(lambda: db.get_folder_record(source_id)["source_status"] == "available")

        image = self.make_image("watched.png", size=(3, 3))
        wait_until(lambda: set(db.get_folder_file_stats(source_id)) == {"watched.png"})
        wait_until(
            lambda: db.get_folders()[0].processed_count
            == db.get_folders()[0].image_count
        )
        image_id = int(db.get_folder_file_records(source_id)["watched.png"]["id"])
        self.assertTrue((self.paths.thumbnails / f"{image_id}.jpg").is_file())
        first_mtime = db.get_folder_file_stats(source_id)["watched.png"][1]

        time.sleep(0.02)
        Image.new("RGB", (8, 5), color="blue").save(image)
        wait_until(
            lambda: db.get_folder_file_stats(source_id).get(
                "watched.png",
                (0, first_mtime),
            )[1] != first_mtime
        )

        renamed = image.with_name("renamed.png")
        image.rename(renamed)
        wait_until(lambda: set(db.get_folder_file_stats(source_id)) == {"renamed.png"})

        renamed.unlink()
        wait_until(lambda: not db.get_folder_file_stats(source_id))


if __name__ == "__main__":
    unittest.main()
