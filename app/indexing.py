from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import database as db
from .cutout import clear_cutout
from .extractor import SUPPORTED
from .preview import clear_preview_cache
from .schemas import ImageInsertRow


@dataclass(frozen=True)
class ScannedFile:
    path: Path
    rel_path: str
    size: int
    mtime: float
    mtime_ns: int


@dataclass(frozen=True)
class SourceSnapshot:
    root: Path
    recursive: bool
    files: dict[str, ScannedFile]
    errors: tuple[str, ...] = ()

    @property
    def signature(self) -> dict[str, tuple[int, int]]:
        return {
            rel_path: (item.size, item.mtime_ns)
            for rel_path, item in self.files.items()
        }


@dataclass(frozen=True)
class IndexResult:
    folder_id: int
    cached: int
    processed: int
    deleted: int = 0
    errors: tuple[str, ...] = ()


def scan_source_directory(folder_path: Path, *, recursive: bool) -> SourceSnapshot:
    """Read a source without writing to it and retain per-entry access failures."""
    if not folder_path.is_dir():
        raise FileNotFoundError(f"Source directory is unavailable: {folder_path}")

    files: dict[str, ScannedFile] = {}
    errors: list[str] = []

    def add_file(path: Path) -> None:
        if path.suffix.lower() not in SUPPORTED:
            return
        try:
            stat = path.stat()
        except OSError as exc:
            errors.append(f"{path}: {exc}")
            return
        rel_path = path.relative_to(folder_path).as_posix()
        files[rel_path] = ScannedFile(
            path=path,
            rel_path=rel_path,
            size=stat.st_size,
            mtime=stat.st_mtime,
            mtime_ns=stat.st_mtime_ns,
        )

    if recursive:
        def record_walk_error(exc: OSError) -> None:
            errors.append(str(exc))

        for root, _directories, names in os.walk(
            folder_path,
            topdown=True,
            onerror=record_walk_error,
            followlinks=False,
        ):
            root_path = Path(root)
            for name in names:
                add_file(root_path / name)
    else:
        try:
            with os.scandir(folder_path) as entries:
                for entry in entries:
                    try:
                        if entry.is_file():
                            add_file(Path(entry.path))
                    except OSError as exc:
                        errors.append(f"{entry.path}: {exc}")
        except OSError as exc:
            raise FileNotFoundError(
                f"Source directory is unavailable: {folder_path}: {exc}"
            ) from exc

    return SourceSnapshot(
        root=folder_path,
        recursive=recursive,
        files=dict(sorted(files.items())),
        errors=tuple(errors),
    )


def index_source_directory(
    folder_path: Path,
    *,
    thumbnail_dir: Path,
    cutout_dir: Path,
    preview_dir: Path,
    name: str | None = None,
    recursive: bool = False,
    snapshot: SourceSnapshot | None = None,
    force_rel_paths: set[str] | None = None,
) -> IndexResult:
    """Reconcile one physical source without changing files inside it."""
    current = snapshot or scan_source_directory(folder_path, recursive=recursive)
    if current.root != folder_path or current.recursive != recursive:
        raise ValueError("Source snapshot does not match the reconciliation request")

    folder_id = db.upsert_source(
        str(folder_path),
        name=name,
        enabled=True,
        recursive=recursive,
    )
    old_stats = db.get_folder_file_stats(folder_id)
    forced = force_rel_paths or set()

    deleted_ids: list[int] = []
    if not current.errors:
        deleted_files = [
            rel_path for rel_path in old_stats if rel_path not in current.files
        ]
        deleted_ids = db.get_image_ids_by_rel_paths(folder_id, deleted_files)
        db.delete_images_by_ids(deleted_ids)
        for image_id in deleted_ids:
            (thumbnail_dir / f"{image_id}.jpg").unlink(missing_ok=True)
            clear_cutout(cutout_dir, image_id)
            clear_preview_cache(preview_dir, image_id)

    new_images: list[ImageInsertRow] = []
    cached_count = 0
    for rel_path, file in current.files.items():
        previous = old_stats.get(rel_path)
        unchanged = (
            previous is not None
            and previous[0] == file.size
            and abs(previous[1] - file.mtime) < 0.001
            and rel_path not in forced
        )
        if unchanged:
            cached_count += 1
            continue

        if previous is not None:
            image_ids = db.get_image_ids_by_rel_paths(folder_id, [rel_path])
            for image_id in image_ids:
                (thumbnail_dir / f"{image_id}.jpg").unlink(missing_ok=True)
                clear_cutout(cutout_dir, image_id)
                clear_preview_cache(preview_dir, image_id)

        new_images.append(ImageInsertRow(
            rel_path=rel_path,
            file_name=file.path.name,
            file_size=file.size,
            file_mtime=file.mtime,
            format=None,
            width=0,
            height=0,
            mode=None,
            error=None,
            metadata_json=None,
        ))

    db.insert_images(folder_id, new_images)
    folder = db.get_folder_record(folder_id)
    if folder is None or folder["status"] != "paused":
        has_pending = bool(new_images) or db.folder_has_unprocessed_images(folder_id)
        db.update_folder_status(folder_id, "processing" if has_pending else "completed")
    changed = bool(new_images or deleted_ids)
    db.mark_folder_scanned(folder_id, changed=changed)
    if current.errors:
        db.update_source_state(
            folder_id,
            "partially_available",
            "\n".join(current.errors[:20]),
        )
    else:
        db.update_source_state(folder_id, "available")

    return IndexResult(
        folder_id=folder_id,
        cached=cached_count,
        processed=len(new_images),
        deleted=len(deleted_ids),
        errors=current.errors,
    )
