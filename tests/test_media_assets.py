from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import database as db
from app import library
from app import worker
from app.indexing import index_source_directory
from app.main import app
from app.media import (
    MediaToolUnavailableError,
    VideoProbeResult,
    make_video_thumbnail,
    probe_video,
)
from app.paths import build_runtime_paths


class VideoToolTest(unittest.TestCase):
    def test_ffprobe_json_is_normalized_to_video_metadata(self) -> None:
        payload = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "codec_long_name": "H.264",
                "profile": "High",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "avg_frame_rate": "30000/1001",
                "bit_rate": "2400000",
                "tags": {"title": "Main"},
            }],
            "format": {
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                "duration": "12.5",
                "tags": {"comment": "embedded"},
            },
        }
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(payload), stderr=""
        )
        with patch("app.media.subprocess.run", return_value=completed) as run:
            result = probe_video("clip.mp4", ffprobe_path="ffprobe-test")

        self.assertEqual(result.format, "mov")
        self.assertEqual((result.width, result.height), (1920, 1080))
        self.assertAlmostEqual(result.frame_rate or 0, 29.970, places=3)
        self.assertEqual(result.duration, 12.5)
        self.assertEqual(result.codec, "h264")
        self.assertEqual(result.metadata["format_tags"]["comment"], "embedded")
        command = run.call_args.args[0]
        self.assertIn("-show_streams", command)
        self.assertIn("-show_format", command)

    def test_ffmpeg_thumbnail_is_read_from_stdout(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"jpeg-preview", stderr=b""
        )
        with patch("app.media.subprocess.run", return_value=completed) as run:
            preview = make_video_thumbnail(
                "clip.mp4", duration=20, ffmpeg_path="ffmpeg-test"
            )

        self.assertEqual(preview, b"jpeg-preview")
        command = run.call_args.args[0]
        self.assertIn("-frames:v", command)
        self.assertEqual(command[-1], "pipe:1")


class UnifiedMediaAssetTest(unittest.TestCase):
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

    def index(self):
        return index_source_directory(
            self.source,
            thumbnail_dir=self.paths.thumbnails,
            preview_dir=self.paths.previews,
            cutout_dir=self.paths.cutouts,
        )

    def make_video(self, name: str = "clip.mp4") -> Path:
        path = self.source / name
        path.write_bytes(b"not-decoded-in-indexing")
        return path

    def make_image(self, name: str = "still.png") -> Path:
        path = self.source / name
        Image.new("RGB", (8, 6), color="green").save(path)
        return path

    def test_images_and_videos_share_sources_albums_and_user_metadata(self) -> None:
        self.make_image()
        self.make_video()
        result = self.index()
        records = db.get_folder_file_records(result.folder_id)
        video_id = int(records["clip.mp4"]["id"])

        folder = next(item for item in db.get_folders() if item.id == result.folder_id)
        self.assertEqual(folder.asset_count, 2)
        self.assertEqual(folder.image_count, 1)
        self.assertEqual(folder.video_count, 1)
        self.assertEqual(library.get_assets(collection="images")["total"], 1)
        videos = library.get_assets(collection="videos")
        self.assertEqual(videos["total"], 1)
        self.assertEqual(videos["assets"][0]["media_type"], "video")
        self.assertEqual(videos["assets"][0]["mime_type"], "video/mp4")

        album = library.create_album("Mixed media")
        library.add_assets_to_album(album["id"], [video_id])
        library.update_asset(video_id, favorite=True, rating=5, note="Keep video")
        connection = db.get_conn()
        try:
            connection.execute(
                "UPDATE images SET ai_annotations_json = ? WHERE id = ?",
                (json.dumps({"reconstructed_prompt": "derived, not embedded"}), video_id),
            )
            connection.commit()
        finally:
            connection.close()
        asset = library.get_assets(
            collection="album", album_id=album["id"]
        )["assets"][0]
        self.assertTrue(asset["favorite"])
        self.assertEqual(asset["user_metadata"]["note"], "Keep video")

        client = app.test_client()
        self.assertEqual(client.get("/api/images").get_json()["total"], 1)
        detail = client.get(f"/api/assets/{video_id}").get_json()
        self.assertEqual(detail["media_type"], "video")
        self.assertTrue(detail["user_metadata"]["favorite"])
        self.assertEqual(
            detail["ai_annotations"]["reconstructed_prompt"],
            "derived, not embedded",
        )
        self.assertIsNone(detail["embedded_metadata"])
        original = client.get(f"/api/original/{video_id}", buffered=True)
        try:
            self.assertEqual(original.content_type, "video/mp4")
            self.assertEqual(original.data, b"not-decoded-in-indexing")
        finally:
            original.close()

    def test_missing_video_tools_do_not_break_image_thumbnails(self) -> None:
        self.make_video()
        self.make_image()
        result = self.index()
        records = db.get_folder_file_records(result.folder_id)
        video_id = int(records["clip.mp4"]["id"])
        image_id = int(records["still.png"]["id"])

        with (
            patch("app.worker.probe_video", side_effect=MediaToolUnavailableError("ffprobe")),
            patch("app.worker.make_video_thumbnail", side_effect=MediaToolUnavailableError("ffmpeg")),
            patch.object(worker, "_thumbnail_dir", self.paths.thumbnails),
        ):
            worker._process_video(video_id, self.source / "clip.mp4")

        asset = library.get_assets(asset_id=video_id)["assets"][0]
        self.assertEqual(asset["preview_status"], "unavailable")
        self.assertIn("ffmpeg", asset["preview_error"])
        detail = db.get_asset_detail(video_id)
        self.assertEqual(
            detail.embedded_metadata["technical_metadata"]["status"],
            "unavailable",
        )
        self.assertIsNone(detail.ai_annotations)

        client = app.test_client()
        with patch(
            "app.main.make_video_thumbnail",
            side_effect=MediaToolUnavailableError("ffmpeg"),
        ):
            unavailable = client.get(f"/api/thumbnail/{video_id}")
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(
            unavailable.get_json()["code"], "video_preview_tool_unavailable"
        )
        self.assertEqual(client.get(f"/api/thumbnail/{image_id}").status_code, 200)

    def test_processed_video_exposes_technical_fields_and_preview(self) -> None:
        self.make_video("movie.webm")
        result = self.index()
        video_id = db.get_folder_asset_ids(result.folder_id)[0]
        probe = VideoProbeResult(
            format="matroska",
            width=1280,
            height=720,
            pixel_format="yuv420p",
            duration=42.25,
            frame_rate=24.0,
            codec="vp9",
            metadata={"source": "ffprobe", "status": "available"},
        )
        with (
            patch("app.worker.probe_video", return_value=probe),
            patch("app.worker.make_video_thumbnail", return_value=b"jpeg"),
            patch.object(worker, "_thumbnail_dir", self.paths.thumbnails),
        ):
            worker._process_video(video_id, self.source / "movie.webm")

        asset = library.get_assets(asset_id=video_id)["assets"][0]
        self.assertEqual(asset["preview_status"], "ready")
        self.assertEqual(asset["duration"], 42.25)
        self.assertEqual(asset["frame_rate"], 24.0)
        self.assertEqual(asset["codec"], "vp9")
        self.assertEqual((asset["width"], asset["height"]), (1280, 720))
        self.assertEqual(
            self.paths.thumbnails.joinpath(f"{video_id}.jpg").read_bytes(),
            b"jpeg",
        )

    def test_uploaded_video_is_stored_probed_and_previewed(self) -> None:
        video_data = b"uploaded-video-original"
        probe = VideoProbeResult(
            format="mov",
            width=1920,
            height=1080,
            pixel_format="yuv420p",
            duration=12.5,
            frame_rate=30.0,
            codec="h264",
            metadata={"source": "ffprobe", "status": "available"},
        )

        def inspect_probe_path(path: str | Path) -> VideoProbeResult:
            self.assertEqual(Path(path).read_bytes(), video_data)
            return probe

        def inspect_preview_path(path: str | Path, **_kwargs) -> bytes:
            self.assertEqual(Path(path).read_bytes(), video_data)
            return b"uploaded-jpeg"

        client = app.test_client()
        with (
            patch("app.main.probe_video", side_effect=inspect_probe_path),
            patch("app.main.make_video_thumbnail", side_effect=inspect_preview_path),
        ):
            response = client.post(
                "/api/upload",
                data={"files": [(io.BytesIO(video_data), "demo.mp4")]},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["assets"], payload["images"])
        uploaded = payload["assets"][0]
        self.assertEqual(uploaded["media_type"], "video")
        self.assertEqual(uploaded["preview_status"], "ready")

        asset_id = uploaded["id"]
        asset = library.get_assets(asset_id=asset_id)["assets"][0]
        self.assertEqual(asset["mime_type"], "video/mp4")
        self.assertEqual(asset["duration"], 12.5)
        self.assertEqual(asset["codec"], "h264")
        self.assertEqual((asset["width"], asset["height"]), (1920, 1080))
        detail = client.get(f"/api/assets/{asset_id}").get_json()
        self.assertEqual(
            detail["embedded_metadata"]["technical_metadata"]["status"],
            "available",
        )
        self.assertEqual(
            self.paths.thumbnails.joinpath(f"{asset_id}.jpg").read_bytes(),
            b"uploaded-jpeg",
        )

        original = client.get(f"/api/original/{asset_id}")
        self.assertEqual(original.content_type, "video/mp4")
        self.assertEqual(original.data, video_data)
        original.close()

        self.paths.thumbnails.joinpath(f"{asset_id}.jpg").unlink()
        with patch(
            "app.main.make_video_thumbnail",
            side_effect=inspect_preview_path,
        ):
            regenerated = client.get(f"/api/thumbnail/{asset_id}")
        self.assertEqual(regenerated.status_code, 200)
        self.assertEqual(regenerated.data, b"uploaded-jpeg")

    def test_uploaded_video_survives_missing_ffmpeg_tools(self) -> None:
        video_data = b"video-without-tools"
        client = app.test_client()
        with (
            patch(
                "app.main.probe_video",
                side_effect=MediaToolUnavailableError("ffprobe"),
            ),
            patch(
                "app.main.make_video_thumbnail",
                side_effect=MediaToolUnavailableError("ffmpeg"),
            ),
        ):
            response = client.post(
                "/api/upload",
                data={"files": [(io.BytesIO(video_data), "offline.webm")]},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        uploaded = response.get_json()["assets"][0]
        self.assertEqual(uploaded["media_type"], "video")
        self.assertEqual(uploaded["preview_status"], "unavailable")
        detail = client.get(f"/api/assets/{uploaded['id']}").get_json()
        self.assertEqual(
            detail["embedded_metadata"]["technical_metadata"]["status"],
            "unavailable",
        )

        with patch(
            "app.main.make_video_thumbnail",
            side_effect=MediaToolUnavailableError("ffmpeg"),
        ):
            thumbnail = client.get(f"/api/thumbnail/{uploaded['id']}")
        self.assertEqual(thumbnail.status_code, 503)
        self.assertEqual(
            thumbnail.get_json()["code"],
            "video_preview_tool_unavailable",
        )


if __name__ == "__main__":
    unittest.main()
