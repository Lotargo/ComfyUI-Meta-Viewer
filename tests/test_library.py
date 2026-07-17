from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app import database as db
from app import library
from app.indexing import index_source_directory
from app.main import app
from app.paths import build_runtime_paths


class LibraryTestCase(unittest.TestCase):
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
        self.source = self.root / "source"
        self.source.mkdir()

    def tearDown(self) -> None:
        app.config.update(self.old_app_config)
        db.set_db_path(self.old_db_path)
        self.temp_dir.cleanup()

    def make_image(self, name: str, color: str = "green") -> Path:
        path = self.source / name
        Image.new("RGB", (5, 4), color=color).save(path)
        return path

    def index(self):
        return index_source_directory(
            self.source,
            thumbnail_dir=self.paths.thumbnails,
            preview_dir=self.paths.previews,
            cutout_dir=self.paths.cutouts,
        )


class VirtualOrganizationTest(LibraryTestCase):
    def test_assets_can_belong_to_multiple_albums_without_source_changes(self) -> None:
        first_path = self.make_image("first.png")
        second_path = self.make_image("second.png", "blue")
        source_bytes = {
            first_path: first_path.read_bytes(),
            second_path: second_path.read_bytes(),
        }
        result = self.index()
        image_ids = db.get_folder_image_ids(result.folder_id)
        first_id, second_id = image_ids

        portfolio = library.create_album("Portfolio")
        variants = library.create_album("Variants")
        self.assertEqual(
            library.add_assets_to_album(portfolio["id"], image_ids), 2
        )
        self.assertEqual(
            library.add_assets_to_album(variants["id"], [first_id]), 1
        )
        library.update_album(
            portfolio["id"], cover_image_id=second_id
        )
        asset = library.update_asset(
            first_id,
            favorite=True,
            rating=4,
            note="Use for the landing page",
            tags=["hero", "Warm Light", "hero"],
        )

        self.assertTrue(asset["favorite"])
        self.assertEqual(asset["rating"], 4)
        self.assertEqual(asset["tags"], ["hero", "Warm Light"])
        self.assertEqual(
            set(asset["album_ids"]), {portfolio["id"], variants["id"]}
        )
        self.assertEqual(
            library.get_assets(
                collection="album", album_id=portfolio["id"]
            )["total"],
            2,
        )

        self.assertTrue(library.delete_album(portfolio["id"]))
        remaining = library.get_assets(asset_id=first_id)["assets"][0]
        self.assertEqual(remaining["album_ids"], [variants["id"]])
        self.assertTrue(remaining["favorite"])
        for path, before in source_bytes.items():
            self.assertEqual(path.read_bytes(), before)

    def test_unavailable_source_keeps_virtual_relations_visible(self) -> None:
        self.make_image("offline.png")
        result = self.index()
        image_id = db.get_folder_image_ids(result.folder_id)[0]
        album = library.create_album("Offline work")
        library.add_assets_to_album(album["id"], [image_id])
        library.update_asset(image_id, favorite=True)

        db.update_source_state(result.folder_id, "unavailable", "Drive offline")

        unavailable = library.get_assets(collection="unavailable")
        self.assertEqual(unavailable["total"], 1)
        self.assertFalse(unavailable["assets"][0]["available"])
        self.assertEqual(unavailable["assets"][0]["album_ids"], [album["id"]])
        self.assertEqual(
            library.get_assets(collection="favorites")["assets"][0]["id"],
            image_id,
        )

    def test_content_fingerprint_preserves_identity_and_album_on_rename(self) -> None:
        original = self.make_image("before.png")
        result = self.index()
        old_record = db.get_folder_file_records(result.folder_id)["before.png"]
        image_id = int(old_record["id"])
        self.assertTrue(old_record["content_fingerprint"])
        album = library.create_album("Keep identity")
        library.add_assets_to_album(album["id"], [image_id])
        library.update_asset(image_id, favorite=True, note="Survives rename")

        original.rename(self.source / "after.png")
        reconciled = self.index()

        records = db.get_folder_file_records(result.folder_id)
        self.assertEqual(set(records), {"after.png"})
        self.assertEqual(records["after.png"]["id"], image_id)
        self.assertEqual(reconciled.deleted, 0)
        self.assertEqual(reconciled.processed, 0)
        asset = library.get_assets(
            collection="album", album_id=album["id"]
        )["assets"][0]
        self.assertEqual(asset["id"], image_id)
        self.assertEqual(asset["file_name"], "after.png")
        self.assertTrue(asset["favorite"])
        self.assertEqual(asset["note"], "Survives rename")


class LibraryApiTest(LibraryTestCase):
    def test_page_album_bulk_and_index_removal_have_distinct_semantics(self) -> None:
        physical = self.make_image("kept-on-disk.png")
        result = self.index()
        image_id = db.get_folder_image_ids(result.folder_id)[0]
        client = app.test_client()

        page = client.get("/library")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'id="asset-grid"', page.data)

        created = client.post("/api/albums", json={"name": "API album"})
        self.assertEqual(created.status_code, 201)
        album_id = created.get_json()["album"]["id"]
        added = client.post(
            f"/api/albums/{album_id}/assets", json={"asset_ids": [image_id]}
        )
        self.assertEqual(added.get_json()["affected"], 1)
        favorited = client.post(
            "/api/library/assets/bulk",
            json={"asset_ids": [image_id], "action": "favorite"},
        )
        self.assertEqual(favorited.status_code, 200)
        self.assertEqual(
            client.get("/api/library/assets?collection=favorites").get_json()["total"],
            1,
        )

        removed_from_album = client.delete(
            f"/api/albums/{album_id}/assets", json={"asset_ids": [image_id]}
        )
        self.assertEqual(removed_from_album.get_json()["affected"], 1)
        self.assertIsNotNone(db.get_image_path(image_id))
        self.assertTrue(physical.is_file())

        removed_from_index = client.post(
            "/api/library/assets/bulk",
            json={"asset_ids": [image_id], "action": "remove_from_index"},
        )
        self.assertEqual(removed_from_index.status_code, 200)
        self.assertIsNone(db.get_image_path(image_id))
        self.assertTrue(physical.is_file())

    def test_library_ui_explains_virtual_and_physical_deletion(self) -> None:
        root = Path(__file__).parents[1]
        template = (root / "app" / "templates" / "library.html").read_text(
            encoding="utf-8"
        )
        script = (root / "app" / "static" / "js" / "library.js").read_text(
            encoding="utf-8"
        )
        styles = (
            root / "app" / "static" / "css" / "features" / "library.css"
        ).read_text(encoding="utf-8")
        viewer = (root / "app" / "templates" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("Virtual organization", template)
        self.assertIn("Physical files will remain on disk", script)
        self.assertIn("may be indexed again", script)
        self.assertIn("Only the virtual album will be deleted", script)
        self.assertIn(".library-body [hidden]", styles)
        self.assertIn("overflow-y: auto", styles)
        self.assertIn("background-position: right 11px center", styles)
        self.assertIn("padding-right: 34px", styles)
        self.assertIn('href="/library"', viewer)


class LibraryMigrationTest(unittest.TestCase):
    def test_existing_database_is_extended_before_new_indexes_are_created(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "legacy.db"
            conn = sqlite3.connect(path)
            conn.executescript(
                """
                CREATE TABLE folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
                    rel_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size INTEGER DEFAULT 0,
                    file_mtime REAL DEFAULT 0,
                    format TEXT,
                    width INTEGER DEFAULT 0,
                    height INTEGER DEFAULT 0,
                    mode TEXT,
                    error TEXT,
                    metadata_json TEXT,
                    thumbnail_b64 TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(folder_id, rel_path)
                );
                """
            )
            conn.close()
            old_path = db.get_db_path()
            try:
                db.set_db_path(path)
                db.init_db()
                connection = db.get_conn()
                try:
                    columns = {
                        row["name"]
                        for row in connection.execute("PRAGMA table_info(images)").fetchall()
                    }
                finally:
                    connection.close()
                self.assertTrue(
                    {"content_fingerprint", "is_favorite", "rating", "note", "indexed_at"}
                    <= columns
                )
                self.assertEqual(library.list_albums(), [])
            finally:
                db.set_db_path(old_path)


if __name__ == "__main__":
    unittest.main()
