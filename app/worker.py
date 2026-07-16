from __future__ import annotations

import sys
import threading
import time
import traceback
from pathlib import Path

from PIL import Image

from . import database as db
from .extractor import extract_metadata, make_thumbnail_bytes

# Disable PIL limit globally
Image.MAX_IMAGE_PIXELS = None

_worker_thread: threading.Thread | None = None
_worker_lock = threading.Lock()
_should_stop = False


def start_worker():
    global _worker_thread, _should_stop
    with _worker_lock:
        _should_stop = False
        if _worker_thread is None or not _worker_thread.is_alive():
            _worker_thread = threading.Thread(
                target=_worker_loop, daemon=True, name="MetaViewerWorker"
            )
            _worker_thread.start()


def stop_worker():
    global _should_stop
    _should_stop = True


def _worker_loop():
    print("[Worker] Background processing loop started", flush=True)
    while not _should_stop:
        try:
            conn = db.get_conn()
            # 1. Find the next unprocessed image in a folder marked as 'processing'
            row = conn.execute(
                """SELECT i.id, i.rel_path, f.path AS folder_path, i.folder_id
                FROM images i
                JOIN folders f ON f.id = i.folder_id
                WHERE f.status = 'processing'
                  AND i.metadata_json IS NULL
                  AND i.error IS NULL
                ORDER BY i.id ASC
                LIMIT 1"""
            ).fetchone()

            if not row:
                # No images to process. Let's see if there are any folders marked as 'processing'
                # that are actually done.
                processing_folders = conn.execute(
                    "SELECT id FROM folders WHERE status = 'processing'"
                ).fetchall()
                for f_row in processing_folders:
                    fid = f_row["id"]
                    unprocessed = conn.execute(
                        "SELECT COUNT(*) AS c FROM images WHERE folder_id = ? AND metadata_json IS NULL AND error IS NULL",
                        (fid,),
                    ).fetchone()
                    if unprocessed and unprocessed["c"] == 0:
                        conn.execute(
                            "UPDATE folders SET status = 'completed' WHERE id = ?",
                            (fid,),
                        )
                        conn.commit()
                        conn.close()
                        # Split folder into metadata / no-metadata siblings
                        db.split_folder_by_metadata(fid)
                        conn = db.get_conn()
                conn.close()
                time.sleep(1.0)
                continue

            img_id = row["id"]
            rel_path = row["rel_path"]
            folder_path = row["folder_path"]
            conn.close()

            # 2. Process the image
            if folder_path in ("__uploads__", "__uploads_no_metadata__"):
                # Uploaded images are already processed, skip
                continue

            abs_path = Path(folder_path) / rel_path
            if abs_path.is_file():
                try:
                    # Extract metadata
                    meta = extract_metadata(abs_path)

                    # Generate thumbnail bytes
                    thumb_data = make_thumbnail_bytes(abs_path)

                    # Save to DB
                    conn = db.get_conn()
                    conn.execute(
                        """UPDATE images SET
                            format = ?, width = ?, height = ?, mode = ?, error = ?, metadata_json = ?,
                            created_at = datetime('now')
                        WHERE id = ?""",
                        (
                            meta.format,
                            meta.size[0] if meta.size else 0,
                            meta.size[1] if meta.size else 0,
                            meta.mode,
                            meta.error,
                            meta.model_dump_json(),
                            img_id,
                        ),
                    )
                    conn.commit()

                    # Save thumbnail file
                    if thumb_data:
                        thumb_dir = Path("cache/thumbnails")
                        thumb_dir.mkdir(parents=True, exist_ok=True)
                        (thumb_dir / f"{img_id}.jpg").write_bytes(thumb_data)
                except Exception as e:
                    err_str = str(e) + "\n" + traceback.format_exc()
                    conn = db.get_conn()
                    conn.execute(
                        "UPDATE images SET error = ? WHERE id = ?",
                        (err_str, img_id),
                    )
                    conn.commit()
                finally:
                    conn.close()
            else:
                # File not found
                err_str = f"File not found: {abs_path}"
                conn = db.get_conn()
                conn.execute(
                    "UPDATE images SET error = ? WHERE id = ?",
                    (err_str, img_id),
                )
                conn.commit()
                conn.close()

            # Small sleep to prevent tight loop CPU starvation
            time.sleep(0.01)

        except Exception as e:
            print(f"[Worker Error] Loop error: {e}", file=sys.stderr, flush=True)
            traceback.print_exc()
            time.sleep(2.0)
