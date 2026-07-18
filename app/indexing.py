from __future__ import annotations

import os
import hashlib
from dataclasses import dataclass
from pathlib import Path

from . import database as db
from .cutout import clear_cutout
from .media import (
    SUPPORTED_MEDIA_EXTENSIONS,
    media_type_for_path,
    mime_type_for_path,
)
from .preview import clear_preview_cache
from .schemas import AssetInsertRow


@dataclass(frozen=True)
class ScannedFile:
    path: Path
    rel_path: str
    size: int
    mtime: float
    mtime_ns: int
    media_type: str
    mime_type: str


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


def content_fingerprint(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return a stable content identity without loading the whole asset into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def scan_source_directory(folder_path: Path, *, recursive: bool) -> SourceSnapshot:
    """Read a source without writing to it and retain per-entry access failures."""
    if not folder_path.is_dir():
        raise FileNotFoundError(f"Source directory is unavailable: {folder_path}")

    files: dict[str, ScannedFile] = {}
    errors: list[str] = []

    def add_file(path: Path) -> None:
        if path.suffix.lower() not in SUPPORTED_MEDIA_EXTENSIONS:
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
            media_type=media_type_for_path(path) or "image",
            mime_type=mime_type_for_path(path),
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
    old_records = db.get_folder_file_records(folder_id)
    forced = force_rel_paths or set()

    fingerprints: dict[str, str] = {}
    for rel_path, file in current.files.items():
        previous = old_records.get(rel_path)
        unchanged = (
            previous is not None
            and int(previous["file_size"]) == file.size
            and abs(float(previous["file_mtime"]) - file.mtime) < 0.001
            and rel_path not in forced
        )
        if unchanged and previous.get("content_fingerprint"):
            fingerprints[rel_path] = str(previous["content_fingerprint"])
            continue
        try:
            fingerprints[rel_path] = content_fingerprint(file.path)
        except OSError as exc:
            fingerprints[rel_path] = ""
            current = SourceSnapshot(
                root=current.root,
                recursive=current.recursive,
                files=current.files,
                errors=(*current.errors, f"{file.path}: {exc}"),
            )

    # Backfill identities for unchanged records once so later renames can retain IDs.
    fingerprint_backfill: list[tuple[int, str]] = []
    for rel_path, fingerprint in fingerprints.items():
        previous = old_records.get(rel_path)
        if previous is not None and fingerprint and not previous.get("content_fingerprint"):
            fingerprint_backfill.append((int(previous["id"]), fingerprint))
            previous["content_fingerprint"] = fingerprint
    db.update_image_fingerprints(fingerprint_backfill)

    deleted_files = [
        rel_path for rel_path in old_records if rel_path not in current.files
    ]
    new_files = [
        rel_path for rel_path in current.files if rel_path not in old_records
    ]

    # A unique content match is treated as a rename and updates the existing row.
    # Album, favorite, rating, tag, and note relations therefore stay attached.
    old_by_identity: dict[tuple[int, str, str], list[str]] = {}
    new_by_identity: dict[tuple[int, str, str], list[str]] = {}
    for rel_path in deleted_files:
        record = old_records[rel_path]
        fingerprint = record.get("content_fingerprint")
        if fingerprint:
            old_by_identity.setdefault(
                (
                    int(record["file_size"]),
                    str(fingerprint),
                    str(record.get("media_type") or "image"),
                ), []
            ).append(rel_path)
    for rel_path in new_files:
        fingerprint = fingerprints.get(rel_path)
        if fingerprint:
            new_by_identity.setdefault(
                (
                    current.files[rel_path].size,
                    fingerprint,
                    current.files[rel_path].media_type,
                ), []
            ).append(rel_path)

    renamed_old: set[str] = set()
    renamed_new: set[str] = set()
    for identity, old_paths in old_by_identity.items():
        new_paths = new_by_identity.get(identity, [])
        if len(old_paths) != 1 or len(new_paths) != 1:
            continue
        old_path = old_paths[0]
        new_path = new_paths[0]
        file = current.files[new_path]
        db.rename_asset_record(
            int(old_records[old_path]["id"]),
            rel_path=new_path,
            file_name=file.path.name,
            file_size=file.size,
            file_mtime=file.mtime,
            content_fingerprint=fingerprints[new_path],
            media_type=file.media_type,
            mime_type=file.mime_type,
        )
        renamed_old.add(old_path)
        renamed_new.add(new_path)

    deleted_ids: list[int] = []
    if not current.errors:
        deleted_files = [path for path in deleted_files if path not in renamed_old]
        deleted_ids = db.get_image_ids_by_rel_paths(folder_id, deleted_files)
        db.delete_images_by_ids(deleted_ids)
        for image_id in deleted_ids:
            (thumbnail_dir / f"{image_id}.jpg").unlink(missing_ok=True)
            clear_cutout(cutout_dir, image_id)
            clear_preview_cache(preview_dir, image_id)

    new_assets: list[AssetInsertRow] = []
    cached_count = 0
    for rel_path, file in current.files.items():
        if rel_path in renamed_new:
            cached_count += 1
            continue
        previous = old_records.get(rel_path)
        unchanged = (
            previous is not None
            and int(previous["file_size"]) == file.size
            and abs(float(previous["file_mtime"]) - file.mtime) < 0.001
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

        new_assets.append(AssetInsertRow(
            rel_path=rel_path,
            file_name=file.path.name,
            file_size=file.size,
            file_mtime=file.mtime,
            media_type=file.media_type,
            mime_type=file.mime_type,
            format=None,
            width=0,
            height=0,
            mode=None,
            error=None,
            metadata_json=None,
            content_fingerprint=fingerprints.get(rel_path) or None,
        ))

    db.insert_assets(folder_id, new_assets)
    folder = db.get_folder_record(folder_id)
    if folder is None or folder["status"] != "paused":
        has_pending = bool(new_assets) or db.folder_has_unprocessed_images(folder_id)
        db.update_folder_status(folder_id, "processing" if has_pending else "completed")
    changed = bool(new_assets or deleted_ids or renamed_new)
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
        processed=len(new_assets),
        deleted=len(deleted_ids),
        errors=current.errors,
    )
