from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import database as db
from app import file_actions
from app.config_store import ConfigStore
from app.folder_picker import FolderPickerUnavailable
from app.main import app
from app.paths import (
    PathValidationError,
    build_runtime_paths,
    normalize_existing_directory,
    normalize_path,
    portable_filename,
)


class RuntimePathsTest(unittest.TestCase):
    def test_defaults_are_anchored_to_project_root_not_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "project root"
            root.mkdir()
            other_cwd = Path(temp_dir) / "other cwd"
            other_cwd.mkdir()
            previous_cwd = Path.cwd()
            try:
                os.chdir(other_cwd)
                paths = build_runtime_paths({}, project_root=root)
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(paths.data_dir, root / ".comfy_meta_uploads")
            self.assertEqual(paths.cache_dir, root / "cache")

    def test_relative_overrides_support_spaces_and_unicode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = build_runtime_paths(
                {
                    "COMFY_META_DATA_DIR": "данные приложения",
                    "COMFY_META_CACHE_DIR": "кэш 🖼",
                },
                project_root=root,
            )

            self.assertEqual(paths.database, root / "данные приложения" / "meta.db")
            self.assertEqual(paths.thumbnails, root / "кэш 🖼" / "thumbnails")
            self.assertFalse(paths.data_dir.exists())
            paths.ensure_directories()
            self.assertTrue(paths.database.parent.is_dir())
            self.assertTrue(paths.previews.is_dir())

    def test_legacy_upload_override_remains_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = build_runtime_paths(
                {"COMFY_META_UPLOAD": "legacy-data"},
                project_root=root,
            )
            self.assertEqual(paths.data_dir, root / "legacy-data")

    def test_normalize_directory_does_not_modify_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "медиа с пробелами"
            source.mkdir()
            original = source / "кадр 🖼.png"
            original.write_bytes(b"original")
            before = {item.name: item.read_bytes() for item in source.iterdir()}

            normalized = normalize_existing_directory(source)

            after = {item.name: item.read_bytes() for item in source.iterdir()}
            self.assertEqual(normalized, source.resolve())
            self.assertEqual(after, before)

    def test_relative_user_paths_use_an_explicit_base(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            self.assertEqual(
                normalize_path(Path("folder") / "image.png", base_dir=base),
                base / "folder" / "image.png",
            )

    def test_portable_filename_accepts_windows_and_posix_inputs(self) -> None:
        self.assertEqual(portable_filename(r"C:\images\кадр.png"), "кадр.png")
        self.assertEqual(portable_filename(r"\\server\share\frame.webp"), "frame.webp")
        self.assertEqual(portable_filename("/home/user/image.jpg"), "image.jpg")

    def test_missing_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(PathValidationError):
                normalize_existing_directory(Path(temp_dir) / "missing")


class NativeDirectoryScanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.old_db_path = db.get_db_path()
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
        db.set_db_path(self.root / "state" / "meta.db")
        db.init_db()
        app.config.update(
            TESTING=True,
            THUMBNAIL_FOLDER=str(self.root / "cache" / "thumbnails"),
            PREVIEW_FOLDER=str(self.root / "cache" / "previews"),
            CUTOUT_FOLDER=str(self.root / "cache" / "cutouts"),
            CONFIG_FILE=str(self.root / "config.json"),
            UPLOAD_FOLDER=str(self.root / "data"),
        )
        self.client = app.test_client()

    def tearDown(self) -> None:
        db.set_db_path(self.old_db_path)
        app.config.update(self.old_config)
        self.temp_dir.cleanup()

    def index_image(self, name: str = "sample image.png") -> tuple[Path, int]:
        source = self.root / "source media"
        source.mkdir(parents=True, exist_ok=True)
        image_path = source / name
        Image.new("RGB", (2, 2), color="blue").save(image_path)
        with patch("app.worker.start_worker"):
            response = self.client.post("/api/scan", json={"path": str(source)})
        self.assertEqual(response.status_code, 200, response.get_json())
        image_id = db.get_folder_image_ids(response.get_json()["folder_id"])[0]
        return image_path, image_id

    def test_scan_normalizes_native_unicode_path_without_source_writes(self) -> None:
        source = self.root / "source media" / "кириллица 🖼"
        source.mkdir(parents=True)
        image_path = source / "sample image.png"
        Image.new("RGB", (2, 2), color="blue").save(image_path)
        before = sorted(item.name for item in source.iterdir())

        with patch("app.worker.start_worker") as start_worker:
            response = self.client.post("/api/scan", json={"path": str(source)})

        self.assertEqual(response.status_code, 200, response.get_json())
        start_worker.assert_called_once_with(Path(app.config["THUMBNAIL_FOLDER"]))
        self.assertEqual(sorted(item.name for item in source.iterdir()), before)

        conn = sqlite3.connect(db.get_db_path())
        try:
            stored_folder, stored_image = conn.execute(
                """SELECT folders.path, images.rel_path
                FROM images JOIN folders ON folders.id = images.folder_id"""
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(stored_folder, str(source.resolve()))
        self.assertEqual(stored_image, image_path.name)
        self.assertEqual(
            ConfigStore(app.config["CONFIG_FILE"]).active_sources(),
            [source.resolve()],
        )

    def test_folder_picker_reports_a_manual_fallback(self) -> None:
        with patch(
            "app.main.choose_folder",
            side_effect=FolderPickerUnavailable("Tk is unavailable"),
        ):
            response = self.client.post("/api/choose-folder")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["code"], "folder_picker_unavailable")
        self.assertIn("manual", response.get_json()["fallback"].lower())

    def test_file_location_and_reveal_use_the_indexed_image_path(self) -> None:
        image_path, image_id = self.index_image("кадр с пробелами.png")

        location = self.client.get(f"/api/images/{image_id}/file-location")
        self.assertEqual(location.status_code, 200)
        self.assertEqual(Path(location.get_json()["path"]), image_path.resolve())

        with (
            patch("app.file_actions.sys.platform", "win32"),
            patch("app.file_actions.subprocess.Popen") as popen,
        ):
            reveal = self.client.post(f"/api/images/{image_id}/reveal")

        self.assertEqual(reveal.status_code, 200)
        command = popen.call_args.args[0]
        self.assertEqual(command[0], "explorer.exe")
        self.assertEqual(command[1], f"/select,{image_path.resolve()}")

    def test_uploaded_original_has_no_physical_file_actions(self) -> None:
        original = BytesIO()
        Image.new("RGB", (2, 2), color="red").save(original, format="PNG")
        image_id, _ = db.insert_upload_image(
            "uploaded.png",
            original.getvalue(),
            has_metadata=False,
        )

        location = self.client.get(f"/api/images/{image_id}/file-location")
        self.assertEqual(location.status_code, 409)
        self.assertEqual(location.get_json()["code"], "no_local_file")
        reveal = self.client.post(f"/api/images/{image_id}/reveal")
        self.assertEqual(reveal.status_code, 409)
        self.assertEqual(reveal.get_json()["code"], "no_local_file")

        viewer_asset = self.client.get("/api/images").get_json()["images"][0]
        self.assertFalse(viewer_asset["has_local_file"])
        library_asset = self.client.get("/api/library/assets").get_json()["assets"][0]
        self.assertFalse(library_asset["has_local_file"])

    def test_missing_physical_file_reports_unavailable(self) -> None:
        image_path, image_id = self.index_image()
        image_path.unlink()

        response = self.client.get(f"/api/images/{image_id}/file-location")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["code"], "local_file_unavailable")


class FileManagerCommandTest(unittest.TestCase):
    def test_platform_commands_select_when_supported(self) -> None:
        path = Path("/images/example image.png")
        self.assertEqual(
            file_actions._file_manager_command(path, "win32"),
            ["explorer.exe", f"/select,{path}"],
        )
        self.assertEqual(
            file_actions._file_manager_command(path, "darwin"),
            ["open", "-R", str(path)],
        )
        with patch("app.file_actions.shutil.which", return_value="/usr/bin/xdg-open"):
            self.assertEqual(
                file_actions._file_manager_command(path, "linux"),
                ["/usr/bin/xdg-open", str(path.parent)],
            )

    def test_linux_requires_a_desktop_launcher(self) -> None:
        with patch("app.file_actions.shutil.which", return_value=None):
            with self.assertRaises(file_actions.FileManagerUnavailableError):
                file_actions._file_manager_command(Path("/images/example.png"), "linux")


if __name__ == "__main__":
    unittest.main()
