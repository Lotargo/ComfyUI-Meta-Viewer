from __future__ import annotations

import json
import sys
import threading
import traceback
from contextlib import closing
from pathlib import Path

from PIL import Image

from . import database as db
from .extractor import extract_metadata, make_thumbnail_bytes
from .media import (
    MediaToolUnavailableError,
    VideoProcessingError,
    make_video_thumbnail,
    probe_video,
)
from .paths import build_runtime_paths, normalize_path

# Disable PIL limit globally
Image.MAX_IMAGE_PIXELS = None

_worker_thread: threading.Thread | None = None
_worker_lock = threading.Lock()
_stop_event = threading.Event()
_thumbnail_dir = build_runtime_paths().thumbnails


def start_worker(thumbnail_dir: str | Path | None = None):
    global _worker_thread, _thumbnail_dir
    with _worker_lock:
        if thumbnail_dir is not None:
            _thumbnail_dir = normalize_path(thumbnail_dir)
        if _worker_thread is None or not _worker_thread.is_alive():
            _stop_event.clear()
            _worker_thread = threading.Thread(
                target=_worker_loop, daemon=True, name="MetaViewerWorker"
            )
            _worker_thread.start()


def stop_worker(*, wait: bool = False, timeout: float = 10.0) -> bool:
    _stop_event.set()
    with _worker_lock:
        worker = _worker_thread
    if wait and worker is not None and worker is not threading.current_thread():
        worker.join(timeout)
    return worker is None or not worker.is_alive()


def _next_asset() -> dict | None:
    with closing(db.get_conn()) as conn:
        row = conn.execute(
            """SELECT i.id, i.rel_path, i.file_name, i.media_type, i.mime_type,
                f.path AS folder_path, i.folder_id, f.source_status
            FROM images i
            JOIN folders f ON f.id = i.folder_id
            WHERE f.status = 'processing'
              AND f.enabled = 1
              AND f.source_status IN ('available', 'partially_available')
              AND i.metadata_json IS NULL
              AND i.error IS NULL
            ORDER BY i.id ASC
            LIMIT 1"""
        ).fetchone()
        if row:
            return dict(row)

        processing_folders = conn.execute(
            "SELECT id FROM folders WHERE status = 'processing'"
        ).fetchall()
        for folder in processing_folders:
            folder_id = int(folder["id"])
            unprocessed = conn.execute(
                """SELECT COUNT(*) AS c FROM images
                WHERE folder_id = ? AND metadata_json IS NULL AND error IS NULL""",
                (folder_id,),
            ).fetchone()
            if unprocessed and unprocessed["c"] == 0:
                conn.execute(
                    "UPDATE folders SET status = 'completed' WHERE id = ?",
                    (folder_id,),
                )
        conn.commit()

    return None


def _next_image() -> dict | None:
    """Compatibility wrapper for the former image-only worker queue."""
    return _next_asset()


def _record_error(image_id: int, message: str) -> None:
    with closing(db.get_conn()) as conn:
        conn.execute(
            "UPDATE images SET error = ? WHERE id = ?",
            (message, image_id),
        )
        conn.commit()


def _process_video(asset_id: int, abs_path: Path) -> None:
    format_name = abs_path.suffix.lower().lstrip(".") or None
    width = 0
    height = 0
    pixel_format = None
    duration = None
    frame_rate = None
    codec = None
    try:
        probe = probe_video(abs_path)
        format_name = probe.format or format_name
        width = probe.width
        height = probe.height
        pixel_format = probe.pixel_format
        duration = probe.duration
        frame_rate = probe.frame_rate
        codec = probe.codec
        technical_metadata = probe.metadata
    except MediaToolUnavailableError as exc:
        technical_metadata = {
            "source": "ffprobe",
            "status": "unavailable",
            "error": str(exc),
        }
    except VideoProcessingError as exc:
        technical_metadata = {
            "source": "ffprobe",
            "status": "error",
            "error": str(exc),
        }

    preview_status = "ready"
    preview_error = None
    try:
        thumb_data = make_video_thumbnail(abs_path, duration=duration)
        _thumbnail_dir.mkdir(parents=True, exist_ok=True)
        (_thumbnail_dir / f"{asset_id}.jpg").write_bytes(thumb_data)
    except MediaToolUnavailableError as exc:
        preview_status = "unavailable"
        preview_error = str(exc)
    except VideoProcessingError as exc:
        preview_status = "error"
        preview_error = str(exc)

    metadata = {
        "file": abs_path.name,
        "path": str(abs_path),
        "media_type": "video",
        "technical_metadata": technical_metadata,
    }
    with closing(db.get_conn()) as conn:
        conn.execute(
            """UPDATE images SET format = ?, width = ?, height = ?, mode = ?,
                duration = ?, frame_rate = ?, codec = ?, error = NULL,
                metadata_json = ?, preview_status = ?, preview_error = ?,
                created_at = datetime('now')
            WHERE id = ?""",
            (
                format_name,
                width,
                height,
                pixel_format,
                duration,
                frame_rate,
                codec,
                json.dumps(metadata, ensure_ascii=False),
                preview_status,
                preview_error,
                asset_id,
            ),
        )
        conn.commit()


def _worker_loop():
    print("[Worker] Background processing loop started", flush=True)
    while not _stop_event.is_set():
        try:
            row = _next_asset()
            if not row:
                _stop_event.wait(1.0)
                continue

            img_id = row["id"]
            rel_path = row["rel_path"]
            folder_path = row["folder_path"]

            # Uploaded assets are already processed by the import path.
            if folder_path in ("__uploads__", "__uploads_no_metadata__"):
                continue

            abs_path = Path(folder_path) / rel_path
            if abs_path.is_file():
                try:
                    if row["media_type"] == "video":
                        _process_video(img_id, abs_path)
                    else:
                        meta = extract_metadata(abs_path)
                        thumb_data = make_thumbnail_bytes(abs_path)
                        preview_status = "ready" if thumb_data else "error"
                        preview_error = None if thumb_data else "Image preview generation failed"

                        # Publish processed DB state after the cache file is ready.
                        if thumb_data:
                            _thumbnail_dir.mkdir(parents=True, exist_ok=True)
                            (_thumbnail_dir / f"{img_id}.jpg").write_bytes(thumb_data)

                        with closing(db.get_conn()) as conn:
                            conn.execute(
                                """UPDATE images SET format = ?, width = ?, height = ?,
                                    mode = ?, error = ?, metadata_json = ?,
                                    preview_status = ?, preview_error = ?,
                                    created_at = datetime('now')
                                WHERE id = ?""",
                                (
                                    meta.format,
                                    meta.size[0] if meta.size else 0,
                                    meta.size[1] if meta.size else 0,
                                    meta.mode,
                                    meta.error,
                                    meta.model_dump_json(),
                                    preview_status,
                                    preview_error,
                                    img_id,
                                ),
                            )
                            conn.commit()
                except Exception as e:
                    err_str = str(e) + "\n" + traceback.format_exc()
                    _record_error(img_id, err_str)
            else:
                if not Path(folder_path).is_dir():
                    db.update_source_state(
                        row["folder_id"],
                        "unavailable",
                        f"Source directory is unavailable: {folder_path}",
                    )
                    _stop_event.wait(1.0)
                else:
                    _record_error(img_id, f"File not found: {abs_path}")

            # Small sleep to prevent tight loop CPU starvation
            _stop_event.wait(0.01)

        except Exception as e:
            print(f"[Worker Error] Loop error: {e}", file=sys.stderr, flush=True)
            traceback.print_exc()
            _stop_event.wait(2.0)
