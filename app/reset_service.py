from __future__ import annotations

import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path

from . import database as db
from .config_store import ConfigStore, ConfigStoreError
from .indexing import index_source_directory
from .paths import PathValidationError, RuntimePaths, normalize_existing_directory
from .worker import stop_worker


_reset_lock = threading.Lock()


class ResetOperationError(RuntimeError):
    """Raised when a reset cannot fully remove disposable application data."""

    def __init__(self, failures: list[str]):
        self.failures = failures
        super().__init__("Reset failed: " + "; ".join(failures))


@dataclass
class ResetResult:
    factory_reset: bool
    deleted: list[str] = field(default_factory=list)
    reindexed_sources: list[str] = field(default_factory=list)
    skipped_sources: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": True,
            "factory_reset": self.factory_reset,
            "deleted": self.deleted,
            "reindexed_sources": self.reindexed_sources,
            "skipped_sources": self.skipped_sources,
        }


def database_files(database: Path) -> tuple[Path, Path, Path]:
    return (
        database.with_name(f"{database.name}-wal"),
        database.with_name(f"{database.name}-shm"),
        database,
    )


def _delete_database_files(paths: RuntimePaths, result: ResetResult) -> None:
    sidecars = database_files(paths.database)[:2]
    failures: list[str] = []
    for path in sidecars:
        try:
            if path.exists():
                path.unlink()
                result.deleted.append(str(path))
        except OSError as exc:
            failures.append(f"{path}: {exc}")

    # Keep the main database intact when an open/locked sidecar cannot be removed.
    if failures:
        raise ResetOperationError(failures)

    try:
        if paths.database.exists():
            paths.database.unlink()
            result.deleted.append(str(paths.database))
    except OSError as exc:
        raise ResetOperationError([f"{paths.database}: {exc}"]) from exc


def _clear_cache_directory(directory: Path, result: ResetResult) -> list[str]:
    failures: list[str] = []
    if not directory.exists():
        return failures
    try:
        entries = list(directory.iterdir())
    except OSError as exc:
        return [f"{directory}: {exc}"]

    for entry in entries:
        try:
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            else:
                entry.unlink()
            result.deleted.append(str(entry))
        except OSError as exc:
            failures.append(f"{entry}: {exc}")
    return failures


def reset_application_index(
    paths: RuntimePaths,
    *,
    factory_reset: bool = False,
) -> ResetResult:
    """Physically recreate the index and caches, optionally deleting configuration."""
    if not _reset_lock.acquire(blocking=False):
        raise ResetOperationError(["Another reset is already running"])

    store = ConfigStore(paths.config)
    result = ResetResult(factory_reset=factory_reset)
    try:
        sources = [] if factory_reset else store.sources()
        if not stop_worker(wait=True, timeout=10.0):
            raise ResetOperationError(["Background index worker did not stop"])

        with db.database_maintenance(timeout=10.0):
            _delete_database_files(paths, result)

            noncritical_failures: list[str] = []
            for directory in (paths.thumbnails, paths.previews, paths.cutouts):
                noncritical_failures.extend(_clear_cache_directory(directory, result))

            if factory_reset:
                try:
                    store.delete()
                    result.deleted.append(str(paths.config))
                except ConfigStoreError as exc:
                    noncritical_failures.append(str(exc))

            paths.ensure_directories()
            db.init_db()

            for source in sources:
                folder_id = db.upsert_source(
                    str(source.path),
                    name=source.name,
                    enabled=source.enabled,
                    recursive=source.recursive,
                    source_status=(
                        "reconnecting" if source.enabled else "disabled"
                    ),
                )
                if not source.enabled:
                    continue
                try:
                    source_path = normalize_existing_directory(source.path)
                    index_source_directory(
                        source_path,
                        thumbnail_dir=paths.thumbnails,
                        preview_dir=paths.previews,
                        cutout_dir=paths.cutouts,
                        name=source.name,
                        recursive=source.recursive,
                    )
                    result.reindexed_sources.append(str(source_path))
                except (OSError, PathValidationError) as exc:
                    db.update_source_state(folder_id, "unavailable", str(exc))
                    result.skipped_sources.append({
                        "path": str(source.path),
                        "error": str(exc),
                    })

            if noncritical_failures:
                raise ResetOperationError(noncritical_failures)
        return result
    finally:
        _reset_lock.release()
