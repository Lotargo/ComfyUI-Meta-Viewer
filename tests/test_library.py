from __future__ import annotations

import json
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
    def test_viewer_images_endpoint_filters_an_album(self) -> None:
        self.make_image("album-member.png")
        self.make_image("outside-album.png", "blue")
        result = self.index()
        image_ids = db.get_folder_image_ids(result.folder_id)
        album = library.create_album("Viewer album")
        library.add_assets_to_album(album["id"], [image_ids[0]])
        client = app.test_client()

        response = client.get(f"/api/images?album_id={album['id']}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["images"][0]["id"], image_ids[0])

        conflict = client.get(
            f"/api/images?folder_id={result.folder_id}&album_id={album['id']}"
        )
        self.assertEqual(conflict.status_code, 400)

    def test_viewer_images_endpoint_filters_exact_ratings(self) -> None:
        self.make_image("three-stars.png")
        self.make_image("five-stars.png", "blue")
        self.make_image("unrated.png", "red")
        result = self.index()
        records = db.get_folder_file_records(result.folder_id)
        client = app.test_client()
        rated_update = client.patch(
            f"/api/library/assets/{records['three-stars.png']['id']}",
            json={"rating": 3},
        )
        self.assertEqual(rated_update.status_code, 200)
        self.assertEqual(rated_update.get_json()["asset"]["rating"], 3)
        library.update_asset(int(records["five-stars.png"]["id"]), rating=5)

        rated = client.get(
            f"/api/images?folder_id={result.folder_id}&rating=3"
        )
        self.assertEqual(rated.status_code, 200)
        self.assertEqual(rated.get_json()["total"], 1)
        self.assertEqual(rated.get_json()["images"][0]["file_name"], "three-stars.png")
        self.assertEqual(rated.get_json()["images"][0]["rating"], 3)

        unrated = client.get("/api/images?rating=0")
        self.assertEqual(unrated.status_code, 200)
        self.assertEqual(unrated.get_json()["total"], 1)
        self.assertEqual(unrated.get_json()["images"][0]["file_name"], "unrated.png")

        detail = client.get(
            f"/api/images/{records['five-stars.png']['id']}"
        )
        self.assertEqual(detail.get_json()["rating"], 5)
        self.assertEqual(client.get("/api/images?rating=6").status_code, 400)
        self.assertEqual(client.get("/api/images?rating=stars").status_code, 400)

    def test_asset_rename_moves_the_file_and_preserves_virtual_metadata(self) -> None:
        original = self.make_image("before.png")
        collision = self.make_image("occupied.png", "blue")
        result = self.index()
        records = db.get_folder_file_records(result.folder_id)
        image_id = int(records["before.png"]["id"])
        album = library.create_album("Renamed files")
        library.add_assets_to_album(album["id"], [image_id])
        library.update_asset(image_id, favorite=True, note="Keep me")
        client = app.test_client()

        response = client.patch(
            f"/api/library/assets/{image_id}",
            json={"file_name": "after"},
        )

        self.assertEqual(response.status_code, 200)
        asset = response.get_json()["asset"]
        self.assertEqual(asset["id"], image_id)
        self.assertEqual(asset["file_name"], "after.png")
        self.assertFalse(original.exists())
        self.assertTrue((self.source / "after.png").is_file())
        self.assertTrue(asset["favorite"])
        self.assertEqual(asset["note"], "Keep me")
        self.assertEqual(asset["album_ids"], [album["id"]])

        conflict = client.patch(
            f"/api/library/assets/{image_id}",
            json={"file_name": "occupied.png"},
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertTrue((self.source / "after.png").is_file())
        self.assertTrue(collision.is_file())

        invalid = client.patch(
            f"/api/library/assets/{image_id}",
            json={"file_name": "nested/name"},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_uploaded_asset_can_be_renamed_without_changing_its_data(self) -> None:
        original_data = self.make_image("upload-source.png").read_bytes()
        image_id, _folder_id = db.insert_upload_image(
            "uploaded.png",
            original_data,
            True,
        )
        client = app.test_client()

        response = client.patch(
            f"/api/library/assets/{image_id}",
            json={"file_name": "stored-copy"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["asset"]["file_name"], "stored-copy.png")
        self.assertEqual(db.get_image_original_data(image_id), original_data)

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
        viewer_sidebar = (
            root / "app" / "static" / "js" / "features" / "sidebar.js"
        ).read_text(encoding="utf-8")
        self.assertIn("Virtual organization", template)
        self.assertIn("Physical files will remain on disk", script)
        self.assertIn("may be indexed again", script)
        self.assertIn("Only the virtual album will be deleted", script)
        self.assertIn(".library-body [hidden]", styles)
        self.assertIn("overflow-y: auto", styles)
        self.assertIn("background-position: right 11px center", styles)
        self.assertIn("padding-right: 34px", styles)
        self.assertIn('id="infinite-scroll-sentinel"', template)
        self.assertIn('id="library-model-filter"', template)
        self.assertIn('id="btn-library-guide"', template)
        self.assertIn('id="library-guide-dialog"', template)
        self.assertIn("Keyboard navigation", template)
        self.assertIn("Clear a selection in place", template)
        self.assertIn("with nothing selected, return to the start", template)
        self.assertNotIn("library-keyboard-hint", template)
        self.assertIn("new IntersectionObserver", script)
        self.assertIn("dom.guideDialog.showModal()", script)
        self.assertIn("library-preview-visible", script)
        self.assertIn("const storedSidebarCollapsed", script)
        self.assertIn("writeStoredPreference(storageKeys.sidebarCollapsed", script)
        self.assertNotIn("library-sidebar-explicitly-collapsed", script)
        self.assertIn("beginPointerAssetDrag", script)
        self.assertIn("addEventListener('pointerdown'", script)
        self.assertIn(
            "state.selectMode && state.selected.has(session.assetId)", script
        )
        self.assertIn(
            "dragSelectedGroup ? selectedIds() : [session.assetId]", script
        )
        self.assertIn("function activateAssetSelection", script)
        self.assertIn("state.lastGridClick?.assetId === assetId", script)
        self.assertNotIn("window.open(asset.original_url", script)
        self.assertIn("function clearGridSelection", script)
        self.assertIn("clearGridSelection({ exitSelectMode: true })", script)
        self.assertIn("else if (state.selected.size > 0)", script)
        self.assertIn("function captureLibraryScroll", script)
        self.assertIn("addContainer(document.scrollingElement)", script)
        self.assertIn("function preserveVisibleCardPosition", script)
        self.assertIn("new EventSource('/api/folders/events')", script)
        self.assertIn(
            "refreshAssets({ reconcile: true, preserveScroll: true })", script
        )
        self.assertIn("function reconcileAssetCards", script)
        self.assertIn("event.stopImmediatePropagation()", script)
        self.assertIn("{ capture: true }", script)
        self.assertIn("dom.btnLibraryGuide.focus({ preventScroll: true })", script)
        self.assertIn("static_version('js/library.js')", template)
        self.assertIn("static_version('css/features/library.css')", template)
        self.assertIn("event.key.toLowerCase() === 'f'", script)
        self.assertIn(".sidebar-album-card.drag-over", styles)
        self.assertIn(".library-guide-dialog", styles)
        self.assertIn(".guide-close svg { display: block; }", styles)
        self.assertIn('id="close-library-guide" class="guide-close"', template)
        self.assertIn('viewBox="0 0 24 24" width="16" height="16"', template)
        self.assertIn(
            ".library-guide-dialog {\n    position: fixed;\n    top: 50%;\n    left: 50%;\n    transform: translate(-50%, -50%);",
            styles,
        )
        self.assertIn('class="album-sidebar-list"', template)
        self.assertIn('id="tab-albums"', viewer)
        self.assertIn('id="panel-albums"', viewer)
        self.assertIn('id="viewer-album-list"', viewer)
        self.assertIn('title="Details view"', viewer)
        self.assertIn("function renderAlbumsList", viewer_sidebar)
        self.assertIn("contentChangedSourceIds", viewer_sidebar)
        self.assertIn("preserveCount: true", viewer_sidebar)
        self.assertIn("function reconcileSidebarItems", viewer_sidebar)
        self.assertIn("loadAlbumImages(album.id, album.name)", viewer_sidebar)
        self.assertIn('draggable="false"', viewer_sidebar)
        sidebar_styles = (
            root / "app" / "static" / "css" / "layout" / "sidebar.css"
        ).read_text(encoding="utf-8")
        header_styles = (
            root / "app" / "static" / "css" / "components" / "header.css"
        ).read_text(encoding="utf-8")
        self.assertIn(".viewer-album-stack", sidebar_styles)
        self.assertIn("aspect-ratio: 4 / 5", sidebar_styles)
        self.assertIn('href="/library"', viewer)
        self.assertIn('class="app-switcher-link active" href="/"', viewer)
        self.assertIn('class="app-switcher-link active" href="/library"', template)
        self.assertIn('class="library-filter-primary"', template)
        self.assertIn('class="library-filter-secondary"', template)
        self.assertIn('class="library-filter-selects"', template)
        self.assertIn('class="library-view-actions"', template)
        self.assertIn('class="header-preview-action active"', template)
        self.assertIn("Preview image", template)
        self.assertIn('id="preview-actions" class="preview-actions"', template)
        self.assertIn('class="preview-action"', template)
        self.assertIn("@container library-toolbar", styles)
        self.assertIn("@container preview-panel", styles)
        self.assertIn("@media (hover: hover) and (pointer: fine)", styles)
        self.assertIn(".library-preview-panel:hover .preview-actions", styles)
        self.assertIn(".header-preview-action.active", styles)
        self.assertIn(".preview-action.copied", styles)
        self.assertIn("top: calc(var(--header-height) + 14px)", styles)
        self.assertIn("showPreviewCopyFeedback", script)
        self.assertIn(".global-header", header_styles)
        self.assertIn(".app-switcher-link.active", header_styles)
        context_menu = (
            root / "app" / "static" / "js" / "components" / "image-context-menu.js"
        ).read_text(encoding="utf-8")
        context_menu_styles = (
            root / "app" / "static" / "css" / "components" / "image-context-menu.css"
        ).read_text(encoding="utf-8")
        cutout_script = (
            root / "app" / "static" / "js" / "features" / "cutout.js"
        ).read_text(encoding="utf-8")
        lightbox_script = (
            root / "app" / "static" / "js" / "lightbox.js"
        ).read_text(encoding="utf-8")
        self.assertIn("showImageContextMenu", script)
        self.assertIn("addEventListener('contextmenu'", script)
        self.assertIn("Show in folder", context_menu)
        self.assertIn("Download image", context_menu)
        self.assertIn("Copy image", context_menu)
        self.assertIn("Copy file path", context_menu)
        self.assertIn("Rename file…", context_menu)
        self.assertIn("Set rating", context_menu)
        self.assertIn("Clear rating", context_menu)
        self.assertIn("Copy positive prompt", context_menu)
        self.assertIn("Copy negative prompt", context_menu)
        self.assertIn("Copy workflow", context_menu)
        self.assertIn("image-context-menu--submenu", context_menu)
        self.assertIn("Add to album", script)
        self.assertIn("Add to favorites", script)
        self.assertIn("Edit details", script)
        self.assertIn("Remove from index", script)
        self.assertIn("Delete uploaded asset", script)
        self.assertIn("Create transparent PNG", lightbox_script)
        self.assertIn("activeImageResolver", cutout_script)
        self.assertIn("initCutoutEvents({ getActiveImage: getDetailForLightbox })", lightbox_script)
        self.assertIn("setAttribute('role', 'menu')", context_menu)
        self.assertIn(".image-context-menu__item:not(:disabled):focus-visible", context_menu_styles)
        self.assertIn(".image-context-menu__item--danger", context_menu_styles)
        self.assertIn("static_version('css/components/image-context-menu.css')", template)
        self.assertIn("static_version('css/components/image-context-menu.css')", viewer)
        self.assertIn('id="viewer-rating-filter-btn"', viewer)
        self.assertIn('data-viewer-rating="0"', viewer)
        self.assertIn('data-viewer-rating="5"', viewer)

    def test_live_source_updates_preserve_viewer_and_library_content(self) -> None:
        root = Path(__file__).parents[1]
        api_script = (root / "app" / "static" / "js" / "api.js").read_text(
            encoding="utf-8"
        )
        gallery_script = (
            root / "app" / "static" / "js" / "gallery.js"
        ).read_text(encoding="utf-8")
        library_script = (
            root / "app" / "static" / "js" / "library.js"
        ).read_text(encoding="utf-8")
        lightbox_script = (
            root / "app" / "static" / "js" / "lightbox.js"
        ).read_text(encoding="utf-8")

        self.assertIn("render && !preserveCount", api_script)
        self.assertIn("renderGallery({ reconcile: reconcileGallery })", api_script)
        self.assertIn("function reconcileGalleryCards", gallery_script)
        self.assertIn("data-image-id=", gallery_script)
        self.assertIn("function reconcileAssetCards", library_script)
        self.assertIn("initLibrarySourceEvents()", library_script)
        self.assertIn("syncLightboxAfterCollectionChange", lightbox_script)

    def test_smart_metadata_filters_are_combined_on_the_backend(self) -> None:
        for name, color in (
            ("flux.png", "red"),
            ("pony.png", "blue"),
            ("sdxl.png", "green"),
        ):
            self.make_image(name, color)
        result = self.index()
        records = db.get_folder_file_records(result.folder_id)

        metadata_by_name = {
            "flux.png": {
                "prompt_parameters": {"model": "flux1-dev.safetensors"},
                "workflow": {"workflow_nodes": {"Sampler": [
                    {"class_type": "FluxGuidance", "inputs": {}}
                ]}},
            },
            "pony.png": {
                "prompt_parameters": {"model": "pony_v6XL.safetensors"},
                "workflow": {"workflow_nodes": {"Post Processing": [
                    {"class_type": "PonyDetailer", "inputs": {}}
                ]}},
            },
            "sdxl.png": {
                "prompt_parameters": {"model": "juggernautXL.safetensors"},
                "workflow": {"workflow_nodes": {"Sampler": [
                    {"class_type": "SDXLRefiner", "inputs": {}}
                ]}},
            },
        }
        sizes = {
            "flux.png": (1280, 768),
            "pony.png": (768, 1280),
            "sdxl.png": (1024, 1024),
        }
        conn = db.get_conn()
        try:
            for name, metadata in metadata_by_name.items():
                width, height = sizes[name]
                conn.execute(
                    "UPDATE images SET width = ?, height = ?, metadata_json = ? WHERE id = ?",
                    (width, height, json.dumps(metadata), records[name]["id"]),
                )
            conn.commit()
        finally:
            conn.close()

        self.assertEqual(
            library.get_assets(model_family="flux")["assets"][0]["file_name"],
            "flux.png",
        )
        self.assertEqual(
            library.get_assets(model_family="pony")["assets"][0]["file_name"],
            "pony.png",
        )
        sdxl_assets = library.get_assets(model_family="sdxl")
        self.assertEqual(sdxl_assets["total"], 1)
        self.assertEqual(sdxl_assets["assets"][0]["file_name"], "sdxl.png")
        self.assertEqual(
            library.get_assets(orientation="portrait")["assets"][0]["file_name"],
            "pony.png",
        )
        self.assertEqual(
            library.get_assets(node_type="SDXLRefiner")["assets"][0]["file_name"],
            "sdxl.png",
        )

        filter_options = library.list_metadata_filters()
        self.assertEqual(
            set(filter_options["node_types"]),
            {"FluxGuidance", "PonyDetailer", "SDXLRefiner"},
        )

        client = app.test_client()
        combined = client.get(
            "/api/library/assets?model_family=flux&orientation=landscape&node_type=FluxGuidance"
        )
        self.assertEqual(combined.status_code, 200)
        self.assertEqual(combined.get_json()["total"], 1)
        self.assertIn("metadata_filters", client.get("/api/library").get_json())
        self.assertEqual(
            client.get("/api/library/assets?orientation=diagonal").status_code,
            400,
        )


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
