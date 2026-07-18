from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from app import database as db
from app.extractor import extract_metadata_from_bytes, has_generation_metadata
from app.main import app
from app.schemas import ImageInsertRow


def make_png(*, with_metadata: bool = True) -> bytes:
    buffer = io.BytesIO()
    png_info = PngInfo()
    if with_metadata:
        png_info.add_text(
            "parameters",
            "test prompt\nNegative prompt: test negative\n"
            "Steps: 20, Sampler: Euler, CFG scale: 7, Seed: 1, Size: 8x8",
        )
    Image.new("RGB", (8, 8), color="red").save(
        buffer,
        format="PNG",
        pnginfo=png_info,
    )
    return buffer.getvalue()


def make_itxt_png() -> bytes:
    buffer = io.BytesIO()
    png_info = PngInfo()
    png_info.add_itxt("workflow", '{"nodes": []}')
    Image.new("RGB", (8, 8), color="blue").save(
        buffer,
        format="PNG",
        pnginfo=png_info,
    )
    return buffer.getvalue()


def make_exif_image(
    image_format: str,
    *,
    with_metadata: bool = True,
    unicode_comment: bool = False,
) -> bytes:
    buffer = io.BytesIO()
    exif = Image.Exif()
    exif[270] = "Test image"
    if with_metadata:
        parameters = (
            f"{'тестовый промпт' if unicode_comment else 'test prompt'}\n"
            "Negative prompt: test negative\n"
            "Steps: 24, Sampler: Euler, CFG scale: 6, Seed: 42, Size: 8x8"
        )
        if unicode_comment:
            exif[37510] = b"UNICODE\x00" + parameters.encode("utf-16-le")
        else:
            exif[37510] = b"ASCII\x00\x00\x00" + parameters.encode("utf-8")
    Image.new("RGB", (8, 8), color="green").save(
        buffer,
        format=image_format,
        exif=exif,
    )
    return buffer.getvalue()


def make_xmp_image(image_format: str) -> bytes:
    buffer = io.BytesIO()
    xmp = (
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description xmlns:sd="https://example.test/stable-diffusion/1.0/" '
        b'sd:parameters="xmp prompt&#10;Negative prompt: xmp negative&#10;'
        b'Steps: 18, Sampler: DPM++ 2M, CFG scale: 5, Seed: 7, Size: 8x8"/>'
        b'</rdf:RDF></x:xmpmeta>'
    )
    Image.new("RGB", (8, 8), color="purple").save(
        buffer,
        format=image_format,
        xmp=xmp,
    )
    return buffer.getvalue()


def make_large_jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4200, 200), color="orange").save(
        buffer,
        format="JPEG",
        quality=90,
    )
    return buffer.getvalue()


class LazyUploadTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = db.get_db_path()
        self.db_path = Path(self.temp_dir.name) / "meta.db"
        self.preview_dir = Path(self.temp_dir.name) / "previews"
        db.set_db_path(self.db_path)
        db.init_db()
        app.config.update(
            TESTING=True,
            THUMBNAIL_FOLDER=str(Path(self.temp_dir.name) / "thumbnails"),
            PREVIEW_FOLDER=str(self.preview_dir),
            CUTOUT_FOLDER=str(Path(self.temp_dir.name) / "cutouts"),
            CONFIG_FILE=str(Path(self.temp_dir.name) / "config.json"),
            UPLOAD_FOLDER=str(Path(self.temp_dir.name) / "uploads"),
        )
        self.client = app.test_client()

    def tearDown(self) -> None:
        db.set_db_path(self.old_db_path)
        self.temp_dir.cleanup()

    def fetch_upload_rows(self) -> list[sqlite3.Row]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(
                """SELECT i.id, i.rel_path, i.file_name, i.format, i.metadata_json,
                    i.thumbnail_b64, i.original_data, f.path AS folder_path
                FROM images i
                JOIN folders f ON f.id = i.folder_id
                ORDER BY i.id"""
            ).fetchall()
        finally:
            conn.close()

    def test_upload_stores_originals_and_defers_metadata(self) -> None:
        png_data = make_png()
        response = self.client.post(
            "/api/upload",
            data={
                "files": [
                    (io.BytesIO(png_data), "sample.png"),
                    (io.BytesIO(png_data), "sample.png"),
                ],
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], 2)

        rows = self.fetch_upload_rows()
        self.assertEqual([row["rel_path"] for row in rows], ["sample.png", "sample_1.png"])
        self.assertTrue(all(row["file_name"] == "sample.png" for row in rows))
        self.assertTrue(all(row["format"] is None for row in rows))
        self.assertTrue(all(row["metadata_json"] is None for row in rows))
        self.assertTrue(all(row["thumbnail_b64"] is None for row in rows))
        self.assertTrue(all(bytes(row["original_data"]) == png_data for row in rows))

        thumbnail_response = self.client.get(f"/api/thumbnail/{rows[1]['id']}")
        self.assertEqual(thumbnail_response.status_code, 200)
        self.assertIsNone(self.fetch_upload_rows()[1]["metadata_json"])

        detail_response = self.client.get(f"/api/images/{rows[0]['id']}")
        self.assertEqual(detail_response.status_code, 200)
        detail = detail_response.get_json()
        self.assertEqual(detail["format"], "PNG")
        self.assertEqual(detail["size"], [8, 8])
        self.assertIsNotNone(detail["prompt_parameters"])

        processed_rows = self.fetch_upload_rows()
        self.assertIsNotNone(processed_rows[0]["metadata_json"])
        self.assertIsNone(processed_rows[1]["metadata_json"])

        original_response = self.client.get(f"/api/original/{rows[1]['id']}")
        self.assertEqual(original_response.status_code, 200)
        self.assertEqual(original_response.content_type, "image/png")
        self.assertEqual(original_response.content_length, len(png_data))
        self.assertEqual(original_response.headers["Content-Disposition"], "inline")
        self.assertEqual(original_response.data, png_data)
        original_response.close()
        self.assertIsNone(self.fetch_upload_rows()[1]["metadata_json"])

    def test_upload_probe_splits_files_without_full_indexing(self) -> None:
        metadata_png = make_png()
        plain_png = make_png(with_metadata=False)
        response = self.client.post(
            "/api/upload",
            data={
                "files": [
                    (io.BytesIO(metadata_png), "metadata.png"),
                    (io.BytesIO(plain_png), "plain.png"),
                ],
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["count"], 2)
        rows = {row["file_name"]: row for row in self.fetch_upload_rows()}
        self.assertEqual(rows["metadata.png"]["folder_path"], "__uploads__")
        self.assertEqual(rows["plain.png"]["folder_path"], "__uploads_no_metadata__")
        self.assertIsNone(rows["metadata.png"]["metadata_json"])
        self.assertIsNone(rows["plain.png"]["metadata_json"])

    def test_probe_and_lazy_parser_support_itxt_markers(self) -> None:
        png_data = make_itxt_png()

        self.assertTrue(has_generation_metadata(png_data, "workflow.png"))
        metadata = extract_metadata_from_bytes(png_data, "workflow.png")
        self.assertEqual(metadata.workflow_ui_json, {"nodes": []})

    def test_probe_and_lazy_parser_support_jpeg_and_webp_exif(self) -> None:
        images = {
            "metadata.jpg": make_exif_image("JPEG"),
            "plain.jpg": make_exif_image("JPEG", with_metadata=False),
            "metadata.webp": make_exif_image("WEBP", unicode_comment=True),
            "plain.webp": make_exif_image("WEBP", with_metadata=False),
        }

        self.assertTrue(has_generation_metadata(images["metadata.jpg"], "metadata.jpg"))
        self.assertFalse(has_generation_metadata(images["plain.jpg"], "plain.jpg"))
        self.assertTrue(has_generation_metadata(images["metadata.webp"], "metadata.webp"))
        self.assertFalse(has_generation_metadata(images["plain.webp"], "plain.webp"))

        response = self.client.post(
            "/api/upload",
            data={
                "files": [
                    (io.BytesIO(data), file_name)
                    for file_name, data in images.items()
                ],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)

        rows = {row["file_name"]: row for row in self.fetch_upload_rows()}
        self.assertEqual(rows["metadata.jpg"]["folder_path"], "__uploads__")
        self.assertEqual(rows["metadata.webp"]["folder_path"], "__uploads__")
        self.assertEqual(rows["plain.jpg"]["folder_path"], "__uploads_no_metadata__")
        self.assertEqual(rows["plain.webp"]["folder_path"], "__uploads_no_metadata__")
        self.assertTrue(all(row["metadata_json"] is None for row in rows.values()))

        for file_name, expected_format, expected_prompt in (
            ("metadata.jpg", "JPEG", "test prompt"),
            ("metadata.webp", "WEBP", "тестовый промпт"),
        ):
            detail_response = self.client.get(f"/api/images/{rows[file_name]['id']}")
            self.assertEqual(detail_response.status_code, 200)
            detail = detail_response.get_json()
            self.assertEqual(detail["format"], expected_format)
            self.assertEqual(
                detail["prompt_parameters"]["positive_prompt"],
                expected_prompt,
            )
            self.assertEqual(
                detail["prompt_parameters"]["generation_settings"]["Seed"],
                42,
            )

    def test_probe_and_lazy_parser_support_jpeg_and_webp_xmp(self) -> None:
        for file_name, image_format in (("xmp.jpeg", "JPEG"), ("xmp.webp", "WEBP")):
            with self.subTest(file_name=file_name):
                image_data = make_xmp_image(image_format)
                self.assertTrue(has_generation_metadata(image_data, file_name))

                metadata = extract_metadata_from_bytes(image_data, file_name)
                self.assertEqual(
                    metadata.prompt_parameters["positive_prompt"],
                    "xmp prompt",
                )
                self.assertEqual(
                    metadata.prompt_parameters["generation_settings"]["Seed"],
                    7,
                )

    def test_preview_is_bounded_cached_and_keeps_metadata_lazy(self) -> None:
        image_data = make_large_jpeg()
        upload_response = self.client.post(
            "/api/upload",
            data={"files": [(io.BytesIO(image_data), "large.jpg")]},
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_response.status_code, 200)
        image_id = upload_response.get_json()["images"][0]["id"]

        preview_response = self.client.get(f"/api/preview/{image_id}")
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview_response.content_type, "image/jpeg")
        preview_data = preview_response.get_data()
        preview_response.close()
        with Image.open(io.BytesIO(preview_data)) as preview:
            self.assertEqual(max(preview.size), 4096)

        rows = self.fetch_upload_rows()
        self.assertIsNone(rows[0]["metadata_json"])
        self.assertEqual(len(list(self.preview_dir.iterdir())), 1)

        cached_response = self.client.get(f"/api/preview/{image_id}")
        self.assertEqual(cached_response.status_code, 200)
        cached_data = cached_response.get_data()
        cached_response.close()
        self.assertEqual(cached_data, preview_data)

    def test_local_original_uses_range_capable_file_response(self) -> None:
        source_dir = Path(self.temp_dir.name) / "source"
        source_dir.mkdir()
        source_path = source_dir / "local.png"
        source_data = make_png(with_metadata=False)
        source_path.write_bytes(source_data)
        stat = source_path.stat()

        folder_id = db.upsert_folder(str(source_dir))
        db.insert_images(
            folder_id,
            [
                ImageInsertRow(
                    rel_path=source_path.name,
                    file_name=source_path.name,
                    file_size=stat.st_size,
                    file_mtime=stat.st_mtime,
                )
            ],
        )
        image_id = db.get_images_page(folder_id).images[0].id

        response = self.client.get(
            f"/api/original/{image_id}",
            headers={"Range": "bytes=0-15"},
        )
        self.assertEqual(response.status_code, 206)
        response_data = response.get_data()
        self.assertEqual(response_data, source_data[:16])
        self.assertEqual(response.headers["Accept-Ranges"], "bytes")
        response.close()

    def test_open_files_control_is_removed(self) -> None:
        response = self.client.get("/")
        html = response.get_data(as_text=True)

        self.assertNotIn("Open Files", html)
        self.assertNotIn('id="file-input"', html)
        self.assertIn("Add files", html)
        self.assertIn('id="add-file-input"', html)
        self.assertIn('data-header-menu-trigger', html)
        self.assertIn('class="viewer-context-toolbar"', html)
        self.assertIn('id="lb-view-original"', html)
        self.assertIn('class="folder-list view-list"', html)

    def test_folders_default_to_list_view(self) -> None:
        js_dir = Path(__file__).parents[1] / "app" / "static" / "js"
        state_path = js_dir / "state.js"
        preferences_path = js_dir / "preferences.js"
        source = state_path.read_text(encoding="utf-8")
        preferences_source = preferences_path.read_text(encoding="utf-8")

        self.assertIn("export let foldersViewMode = 'list';", source)
        self.assertIn("export let albumsViewMode = 'list';", source)
        self.assertIn("setFoldersViewMode(defaults.layout.foldersViewMode);", source)
        self.assertIn("setAlbumsViewMode(defaults.layout.albumsViewMode);", source)
        self.assertIn("foldersViewMode: 'list'", preferences_source)
        self.assertIn("albumsViewMode: 'list'", preferences_source)


if __name__ == "__main__":
    unittest.main()
