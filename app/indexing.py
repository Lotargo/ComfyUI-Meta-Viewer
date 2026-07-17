from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import database as db
from .cutout import clear_cutout
from .extractor import SUPPORTED
from .preview import clear_preview_cache
from .schemas import ImageInsertRow


@dataclass(frozen=True)
class IndexResult:
    folder_id: int
    cached: int
    processed: int


def index_source_directory(
    folder_path: Path,
    *,
    thumbnail_dir: Path,
    cutout_dir: Path,
    preview_dir: Path,
) -> IndexResult:
    """Update one source in the disposable index without changing source files."""
    folder_id = db.upsert_folder(str(folder_path))
    old_mtimes = db.get_folder_mtimes(folder_id)

    files = sorted(
        file
        for file in folder_path.iterdir()
        if file.is_file() and file.suffix.lower() in SUPPORTED
    )

    files_set = {file.name for file in files}
    deleted_files = [name for name in old_mtimes if name not in files_set]
    if deleted_files:
        deleted_ids = db.get_image_ids_by_rel_paths(folder_id, deleted_files)
        db.delete_images_by_ids(deleted_ids)
        for image_id in deleted_ids:
            (thumbnail_dir / f"{image_id}.jpg").unlink(missing_ok=True)
            clear_cutout(cutout_dir, image_id)
            clear_preview_cache(preview_dir, image_id)

    new_images: list[ImageInsertRow] = []
    cached_count = 0
    for file in files:
        rel_path = file.name
        stat = file.stat()
        if (
            rel_path in old_mtimes
            and abs(old_mtimes[rel_path] - stat.st_mtime) < 0.001
        ):
            cached_count += 1
            continue
        new_images.append(ImageInsertRow(
            rel_path=rel_path,
            file_name=file.name,
            file_size=stat.st_size,
            file_mtime=stat.st_mtime,
            format=None,
            width=0,
            height=0,
            mode=None,
            error=None,
            metadata_json=None,
        ))

    db.insert_images(folder_id, new_images)
    db.update_folder_status(folder_id, "processing")
    return IndexResult(
        folder_id=folder_id,
        cached=cached_count,
        processed=len(new_images),
    )
