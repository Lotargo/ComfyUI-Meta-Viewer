from __future__ import annotations

import threading
from pathlib import Path

from . import database as db
from .extractor import (
    make_display_preview_from_bytes,
    make_display_preview_from_path,
)

PREVIEW_MAX_SIZE = 4096
PREVIEW_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
}

_generation_lock = threading.Lock()


class PreviewBusyError(RuntimeError):
    """Another large preview is currently being generated."""


def _source_version(source: dict) -> str:
    modified_ms = int(float(source.get("file_mtime") or 0) * 1000)
    file_size = int(source.get("file_size") or 0)
    return f"{modified_ms}-{file_size}-{PREVIEW_MAX_SIZE}"


def _preview_stem(image_id: int, source: dict) -> str:
    return f"{image_id}-{_source_version(source)}"


def _find_cached_preview(
    preview_dir: Path,
    image_id: int,
    source: dict,
) -> Path | None:
    stem = _preview_stem(image_id, source)
    for suffix in PREVIEW_MIME_TYPES:
        candidate = preview_dir / f"{stem}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def _remove_stale_previews(preview_dir: Path, image_id: int, keep: Path) -> None:
    for candidate in preview_dir.glob(f"{image_id}-*"):
        if candidate != keep and candidate.is_file():
            candidate.unlink(missing_ok=True)


def get_or_create_preview(
    image_id: int,
    preview_folder: str | Path,
) -> Path:
    source = db.get_image_source_info(image_id)
    if not source:
        raise FileNotFoundError("Image not found")

    preview_dir = Path(preview_folder).resolve()
    cached = _find_cached_preview(preview_dir, image_id, source)
    if cached:
        return cached

    if not _generation_lock.acquire(blocking=False):
        raise PreviewBusyError("Preview generator is busy")

    try:
        cached = _find_cached_preview(preview_dir, image_id, source)
        if cached:
            return cached

        if source["has_original_data"]:
            original = db.get_image_original_data(image_id)
            if original is None:
                raise FileNotFoundError("Database original not found")
            generated = make_display_preview_from_bytes(original, PREVIEW_MAX_SIZE)
        else:
            source_path = Path(source["path"])
            if not source_path.is_file():
                raise FileNotFoundError("Image source not found")
            generated = make_display_preview_from_path(source_path, PREVIEW_MAX_SIZE)

        if generated is None:
            raise RuntimeError("Preview generation failed")
        preview_data, extension = generated

        preview_dir.mkdir(parents=True, exist_ok=True)
        target = preview_dir / f"{_preview_stem(image_id, source)}.{extension}"
        temporary = target.with_suffix(f"{target.suffix}.tmp")
        temporary.write_bytes(preview_data)
        temporary.replace(target)
        _remove_stale_previews(preview_dir, image_id, target)
        return target
    finally:
        _generation_lock.release()


def preview_mimetype(path: Path) -> str:
    return PREVIEW_MIME_TYPES.get(path.suffix.lower(), "application/octet-stream")


def clear_preview_cache(
    preview_folder: str | Path,
    image_id: int | None = None,
) -> int:
    preview_dir = Path(preview_folder)
    if not preview_dir.is_dir():
        return 0

    pattern = f"{image_id}-*" if image_id is not None else "*"
    deleted = 0
    for candidate in preview_dir.glob(pattern):
        if not candidate.is_file():
            continue
        try:
            candidate.unlink()
            deleted += 1
        except OSError:
            pass
    return deleted
