"""Durable background job queue worker (no broker: single local instance).

Crash safety comes from three rules, not from logs:

1. Visible state changes only via atomic commits (rows + tombstones + job
   land together); files are touched only in the background.
2. Every handler is idempotent: replaying it after a crash repeats only
   safe effects (missing files / caches are already-gone, not errors).
3. Jobs left 'running' by a dead process are reset to 'pending' on startup
   and picked up again — nothing rots, nothing needs manual repair.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable

from send2trash import send2trash

from . import database as db
from .cutout import clear_cutout
from .paths import build_runtime_paths
from .preview import clear_preview_cache

logger = logging.getLogger(__name__)

JOB_POLL_INTERVAL = 1.0

_worker_thread: threading.Thread | None = None
_worker_lock = threading.Lock()
_stop_event = threading.Event()


class _StopRequested(RuntimeError):
    pass


def start_job_worker() -> None:
    global _worker_thread
    with _worker_lock:
        if _worker_thread is None or not _worker_thread.is_alive():
            _stop_event.clear()
            _worker_thread = threading.Thread(
                target=_worker_loop, daemon=True, name="MetaViewerJobWorker"
            )
            _worker_thread.start()


def stop_job_worker(*, wait: bool = False, timeout: float = 10.0) -> bool:
    _stop_event.set()
    with _worker_lock:
        worker = _worker_thread
    if wait and worker is not None and worker is not threading.current_thread():
        worker.join(timeout)
    return worker is None or not worker.is_alive()


def _handle_trash_assets(payload: dict[str, Any]) -> None:
    image_ids = [int(value) for value in payload.get("image_ids", [])]
    tombstones = db.get_tombstones_by_image_ids(image_ids)
    if len(tombstones) != len(image_ids):
        missing = sorted(
            set(image_ids) - {int(item["image_id"]) for item in tombstones}
        )
        logger.warning(
            "trash_assets: no tombstones for image ids %s;"
            " rows were likely removed by another path — skipping them",
            missing,
        )
    paths = build_runtime_paths()
    done_ids: list[int] = []
    for index, tomb in enumerate(tombstones):
        # Honor shutdown only inside the worker thread: direct
        # process_pending_job callers (tests, scripts) run to completion.
        if (
            index % 25 == 0
            and _stop_event.is_set()
            and threading.current_thread() is _worker_thread
        ):
            raise _StopRequested()
        if tomb.get("has_local_file") and tomb.get("folder_path"):
            abs_path = Path(str(tomb["folder_path"])) / str(tomb["rel_path"])
            if abs_path.is_file():
                try:
                    send2trash(str(abs_path))
                except Exception as exc:
                    raise RuntimeError(
                        f"Could not move {abs_path.name} to the system trash"
                    ) from exc
            # Missing file = already-gone end state: not an error (idempotent).
        image_id = int(tomb["image_id"])
        (paths.thumbnails / f"{image_id}.jpg").unlink(missing_ok=True)
        clear_cutout(paths.cutouts, image_id)
        clear_preview_cache(paths.previews, image_id)
        done_ids.append(int(tomb["id"]))
    db.delete_tombstones(done_ids)


_HANDLERS: dict[str, Callable[[dict[str, Any]], None]] = {
    "trash_assets": _handle_trash_assets,
}


def process_pending_job() -> bool:
    """Claim and run a single job. Returns True when work was done."""
    job = db.claim_next_job()
    if job is None:
        return False
    handler = _HANDLERS.get(job["op"])
    try:
        if handler is None:
            raise RuntimeError(f"Unknown job op: {job['op']}")
        handler(job["payload"])
    except _StopRequested:
        # Leave the job 'running': the next startup resets and resumes it.
        raise
    except Exception as exc:
        status = db.fail_job(job["id"], f"{type(exc).__name__}: {exc}")
        logger.warning(
            "job %s (%s) failed on attempt %s -> %s: %s",
            job["id"],
            job["op"],
            job["attempts"],
            status,
            exc,
        )
        return True
    db.complete_job(job["id"])
    return True


def _worker_loop() -> None:
    try:
        resumed = db.reset_stuck_jobs()
    except Exception as exc:
        logger.warning("job worker: startup resume failed: %s", exc)
    else:
        if resumed:
            logger.warning(
                "job worker: resumed %s interrupted job(s) after restart", resumed
            )
    while not _stop_event.is_set():
        try:
            if process_pending_job():
                continue
        except _StopRequested:
            break
        except db.DatabaseMaintenanceError:
            time.sleep(5.0)
            continue
        except Exception as exc:  # never let the loop die silently
            logger.exception("job worker loop error: %s", exc)
            time.sleep(5.0)
            continue
        time.sleep(JOB_POLL_INTERVAL)
