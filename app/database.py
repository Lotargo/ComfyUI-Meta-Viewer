from __future__ import annotations

import json
import hashlib
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .paths import build_runtime_paths, normalize_path, portable_filename
from .schemas import (
    AssetInsertRow,
    FolderInfo,
    ImageDetail,
    ImageInsertRow,
    ImageListItem,
    ImageMetadata,
    ImagesResponse,
)

_DB_PATH: str | None = None
_connection_condition = threading.Condition()
_active_connections = 0
_maintenance_owner: int | None = None


class DatabaseMaintenanceError(RuntimeError):
    """Raised when the index is temporarily unavailable for maintenance."""


class _TrackedConnection(sqlite3.Connection):
    _cmv_counted = False

    def close(self) -> None:
        counted = self._cmv_counted
        try:
            super().close()
        finally:
            if counted:
                self._cmv_counted = False
                _release_connection()


def _release_connection() -> None:
    global _active_connections
    with _connection_condition:
        _active_connections -= 1
        _connection_condition.notify_all()


@contextmanager
def database_maintenance(timeout: float = 10.0):
    """Block new connections and wait until all current connections are closed."""
    global _maintenance_owner
    owner = threading.get_ident()
    deadline = time.monotonic() + timeout
    with _connection_condition:
        if _maintenance_owner is not None:
            raise DatabaseMaintenanceError("Database maintenance is already running")
        _maintenance_owner = owner
        while _active_connections:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _maintenance_owner = None
                _connection_condition.notify_all()
                raise DatabaseMaintenanceError(
                    f"Timed out waiting for {_active_connections} database connection(s)"
                )
            _connection_condition.wait(remaining)
    try:
        yield
    finally:
        with _connection_condition:
            _maintenance_owner = None
            _connection_condition.notify_all()


def get_db_path() -> str:
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = str(build_runtime_paths().database)
    return _DB_PATH


def set_db_path(path: str | Path) -> None:
    global _DB_PATH
    _DB_PATH = str(normalize_path(path))


def get_conn() -> sqlite3.Connection:
    global _active_connections
    with _connection_condition:
        if (
            _maintenance_owner is not None
            and _maintenance_owner != threading.get_ident()
        ):
            raise DatabaseMaintenanceError("Database reset is in progress")
        _active_connections += 1

    try:
        conn = sqlite3.connect(get_db_path(), factory=_TrackedConnection)
        conn._cmv_counted = True
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    except Exception:
        if "conn" in locals():
            conn.close()
        else:
            _release_connection()
        raise


def init_db() -> None:
    Path(get_db_path()).parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'idle',
                enabled INTEGER NOT NULL DEFAULT 1,
                recursive INTEGER NOT NULL DEFAULT 0,
                source_status TEXT NOT NULL DEFAULT 'available',
                last_error TEXT,
                revision INTEGER NOT NULL DEFAULT 0,
                scanned_at TEXT DEFAULT (datetime('now')),
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
                rel_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                file_mtime REAL DEFAULT 0,
                media_type TEXT NOT NULL DEFAULT 'image',
                mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                format TEXT,
                width INTEGER DEFAULT 0,
                height INTEGER DEFAULT 0,
                mode TEXT,
                duration REAL,
                frame_rate REAL,
                codec TEXT,
                error TEXT,
                metadata_json TEXT,
                ai_annotations_json TEXT,
                preview_status TEXT NOT NULL DEFAULT 'pending',
                preview_error TEXT,
                thumbnail_b64 TEXT,
                original_data BLOB,
                content_fingerprint TEXT,
                is_favorite INTEGER NOT NULL DEFAULT 0,
                rating INTEGER,
                note TEXT NOT NULL DEFAULT '',
                indexed_at TEXT DEFAULT (datetime('now')),
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(folder_id, rel_path)
            );

            CREATE TABLE IF NOT EXISTS albums (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                cover_image_id INTEGER REFERENCES images(id) ON DELETE SET NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS album_images (
                album_id INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
                image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
                position INTEGER NOT NULL DEFAULT 0,
                added_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (album_id, image_id)
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                name_key TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS image_tags (
                image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
                tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (image_id, tag_id)
            );

            CREATE INDEX IF NOT EXISTS idx_images_folder ON images(folder_id);
            CREATE INDEX IF NOT EXISTS idx_images_folder_mtime ON images(folder_id, file_mtime);
            CREATE INDEX IF NOT EXISTS idx_album_images_image ON album_images(image_id);
            CREATE INDEX IF NOT EXISTS idx_image_tags_tag ON image_tags(tag_id);
        """)
        migrations = (
            "ALTER TABLE images ADD COLUMN original_data BLOB",
            "ALTER TABLE folders ADD COLUMN status TEXT NOT NULL DEFAULT 'idle'",
            "ALTER TABLE folders ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE folders ADD COLUMN recursive INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE folders ADD COLUMN source_status TEXT NOT NULL DEFAULT 'available'",
            "ALTER TABLE folders ADD COLUMN last_error TEXT",
            "ALTER TABLE folders ADD COLUMN revision INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE images ADD COLUMN content_fingerprint TEXT",
            "ALTER TABLE images ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE images ADD COLUMN rating INTEGER",
            "ALTER TABLE images ADD COLUMN note TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE images ADD COLUMN indexed_at TEXT",
            "ALTER TABLE images ADD COLUMN media_type TEXT NOT NULL DEFAULT 'image'",
            "ALTER TABLE images ADD COLUMN mime_type TEXT NOT NULL DEFAULT 'application/octet-stream'",
            "ALTER TABLE images ADD COLUMN duration REAL",
            "ALTER TABLE images ADD COLUMN frame_rate REAL",
            "ALTER TABLE images ADD COLUMN codec TEXT",
            "ALTER TABLE images ADD COLUMN ai_annotations_json TEXT",
            "ALTER TABLE images ADD COLUMN preview_status TEXT NOT NULL DEFAULT 'pending'",
            "ALTER TABLE images ADD COLUMN preview_error TEXT",
        )
        for migration in migrations:
            try:
                conn.execute(migration)
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
        conn.execute(
            "UPDATE images SET indexed_at = COALESCE(indexed_at, created_at, datetime('now'))"
        )
        conn.execute(
            """UPDATE images SET
                media_type = COALESCE(NULLIF(media_type, ''), 'image'),
                mime_type = CASE
                    WHEN LOWER(file_name) LIKE '%.png' THEN 'image/png'
                    WHEN LOWER(file_name) LIKE '%.jpg' THEN 'image/jpeg'
                    WHEN LOWER(file_name) LIKE '%.jpeg' THEN 'image/jpeg'
                    WHEN LOWER(file_name) LIKE '%.webp' THEN 'image/webp'
                    WHEN LOWER(file_name) LIKE '%.bmp' THEN 'image/bmp'
                    WHEN LOWER(file_name) LIKE '%.tiff' THEN 'image/tiff'
                    ELSE COALESCE(NULLIF(mime_type, ''), 'application/octet-stream')
                END,
                preview_status = CASE
                    WHEN preview_status = 'pending' AND (metadata_json IS NOT NULL OR error IS NOT NULL)
                    THEN 'ready'
                    ELSE COALESCE(NULLIF(preview_status, ''), 'pending')
                END"""
        )
        conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_images_favorite ON images(is_favorite);
            CREATE INDEX IF NOT EXISTS idx_images_fingerprint ON images(content_fingerprint);
            CREATE INDEX IF NOT EXISTS idx_images_media_type ON images(media_type);
        """)
        conn.commit()
    finally:
        conn.close()


def upsert_folder(path: str) -> int:
    conn = get_conn()
    try:
        name = Path(path).name or path
        cur = conn.execute(
            "INSERT INTO folders (path, name) VALUES (?, ?) ON CONFLICT(path) DO UPDATE SET scanned_at=datetime('now') RETURNING id",
            (path, name),
        )
        row = cur.fetchone()
        folder_id = row["id"]
        conn.commit()
        return folder_id
    finally:
        conn.close()


def upsert_source(
    path: str,
    *,
    name: str | None = None,
    enabled: bool = True,
    recursive: bool = False,
    source_status: str | None = None,
) -> int:
    """Create or update a physical source without discarding its indexed assets."""
    conn = get_conn()
    try:
        source_name = (name or "").strip() or Path(path).name or path
        state = source_status or ("available" if enabled else "disabled")
        cur = conn.execute(
            """INSERT INTO folders
                (path, name, enabled, recursive, source_status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                name=excluded.name,
                enabled=excluded.enabled,
                recursive=excluded.recursive,
                source_status=CASE
                    WHEN excluded.enabled = 0 THEN 'disabled'
                    WHEN folders.source_status = 'disabled' THEN 'reconnecting'
                    ELSE folders.source_status
                END
            RETURNING id""",
            (path, source_name, int(enabled), int(recursive), state),
        )
        folder_id = int(cur.fetchone()["id"])
        conn.commit()
        return folder_id
    finally:
        conn.close()


def get_folder_mtimes(folder_id: int) -> dict[str, float]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT rel_path, file_mtime FROM images WHERE folder_id = ?", (folder_id,)
        ).fetchall()
        return {r["rel_path"]: r["file_mtime"] for r in rows}
    finally:
        conn.close()


def get_folder_file_stats(folder_id: int) -> dict[str, tuple[int, float]]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT rel_path, file_size, file_mtime FROM images WHERE folder_id = ?",
            (folder_id,),
        ).fetchall()
        return {
            str(row["rel_path"]): (int(row["file_size"]), float(row["file_mtime"]))
            for row in rows
        }
    finally:
        conn.close()


def get_folder_file_records(folder_id: int) -> dict[str, dict[str, Any]]:
    """Return the identity fields needed to reconcile a physical source."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT id, rel_path, file_size, file_mtime, content_fingerprint,
                media_type, mime_type
            FROM images WHERE folder_id = ?""",
            (folder_id,),
        ).fetchall()
        return {str(row["rel_path"]): dict(row) for row in rows}
    finally:
        conn.close()


def update_image_fingerprints(fingerprints: list[tuple[int, str]]) -> None:
    if not fingerprints:
        return
    conn = get_conn()
    try:
        conn.executemany(
            "UPDATE images SET content_fingerprint = ? WHERE id = ?",
            [(fingerprint, image_id) for image_id, fingerprint in fingerprints],
        )
        conn.commit()
    finally:
        conn.close()


def rename_asset_record(
    asset_id: int,
    *,
    rel_path: str,
    file_name: str,
    file_size: int,
    file_mtime: float,
    content_fingerprint: str,
    media_type: str,
    mime_type: str,
) -> None:
    """Move an indexed identity to a new relative path without losing virtual links."""
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE images SET rel_path = ?, file_name = ?, file_size = ?,
                file_mtime = ?, content_fingerprint = ?, media_type = ?, mime_type = ?
            WHERE id = ?""",
            (
                rel_path,
                file_name,
                file_size,
                file_mtime,
                content_fingerprint,
                media_type,
                mime_type,
                asset_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def rename_image_record(image_id: int, **fields: Any) -> None:
    """Compatibility wrapper for the former image-only reconciliation API."""
    rename_asset_record(image_id, **fields)


def insert_assets(folder_id: int, assets: list[AssetInsertRow]) -> None:
    if not assets:
        return
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        for asset in assets:
            conn.execute(
                """INSERT INTO images (folder_id, rel_path, file_name, file_size, file_mtime,
                    media_type, mime_type, format, width, height, mode, duration,
                    frame_rate, codec, error, metadata_json, thumbnail_b64,
                    content_fingerprint, preview_status, preview_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(folder_id, rel_path) DO UPDATE SET
                    file_name=excluded.file_name,
                    file_size=excluded.file_size, file_mtime=excluded.file_mtime,
                    media_type=excluded.media_type, mime_type=excluded.mime_type,
                    format=excluded.format, width=excluded.width, height=excluded.height,
                    mode=excluded.mode, duration=excluded.duration,
                    frame_rate=excluded.frame_rate, codec=excluded.codec,
                    error=excluded.error,
                    metadata_json=excluded.metadata_json, thumbnail_b64=excluded.thumbnail_b64,
                    ai_annotations_json=NULL,
                    content_fingerprint=excluded.content_fingerprint,
                    preview_status=excluded.preview_status,
                    preview_error=excluded.preview_error,
                    created_at=datetime('now')""",
                (
                    folder_id,
                    asset.rel_path,
                    asset.file_name,
                    asset.file_size,
                    asset.file_mtime,
                    asset.media_type,
                    asset.mime_type,
                    asset.format,
                    asset.width,
                    asset.height,
                    asset.mode,
                    asset.duration,
                    asset.frame_rate,
                    asset.codec,
                    asset.error,
                    asset.metadata_json,
                    asset.thumbnail_b64,
                    asset.content_fingerprint,
                    asset.preview_status,
                    asset.preview_error,
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_images(folder_id: int, images: list[ImageInsertRow]) -> None:
    """Compatibility wrapper for the former image-only index API."""
    insert_assets(folder_id, list(images))


def get_folders() -> list[FolderInfo]:
    conn = get_conn()
    try:
        # Keep image_count for the image viewer while exposing unified asset counts.
        rows = conn.execute(
            """SELECT f.id, f.path, f.name, f.scanned_at, f.created_at, f.status,
               f.enabled, f.recursive, f.source_status, f.last_error, f.revision,
               COUNT(CASE WHEN i.media_type = 'image' THEN 1 END) AS image_count,
               COUNT(i.id) AS asset_count,
               COUNT(CASE WHEN i.media_type = 'video' THEN 1 END) AS video_count,
               COUNT(CASE WHEN i.media_type = 'image' AND (i.metadata_json IS NOT NULL OR i.error IS NOT NULL) THEN 1 END) AS processed_count,
               COUNT(CASE WHEN i.id IS NOT NULL AND (i.metadata_json IS NOT NULL OR i.error IS NOT NULL) THEN 1 END) AS processed_asset_count
            FROM folders f LEFT JOIN images i ON i.folder_id = f.id
            GROUP BY f.id ORDER BY f.scanned_at DESC"""
        ).fetchall()
        folders_list = [FolderInfo.model_validate(dict(r)) for r in rows]
        return folders_list
    finally:
        conn.close()


def get_indexed_folder_paths() -> list[str]:
    conn = get_conn()
    try:
        rows = conn.execute("SELECT path FROM folders ORDER BY id").fetchall()
        return [str(row["path"]) for row in rows]
    finally:
        conn.close()


def get_source_records() -> list[dict[str, Any]]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT id, path, name, status, enabled, recursive, source_status,
                last_error, revision, scanned_at
            FROM folders
            WHERE path NOT LIKE '__uploads%'
            ORDER BY id"""
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_folder_record(folder_id: int) -> dict[str, Any] | None:
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT id, path, name, status, enabled, recursive, source_status,
                last_error, revision, scanned_at
            FROM folders WHERE id = ?""",
            (folder_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_folder_path(folder_id: int) -> str | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT path FROM folders WHERE id = ?",
            (folder_id,),
        ).fetchone()
        return str(row["path"]) if row else None
    finally:
        conn.close()


def update_folder_status(folder_id: int, status: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE folders SET status = ? WHERE id = ?",
            (status, folder_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_source_settings(
    folder_id: int,
    *,
    name: str | None = None,
    enabled: bool | None = None,
    recursive: bool | None = None,
) -> None:
    assignments: list[str] = []
    values: list[Any] = []
    if name is not None:
        assignments.append("name = ?")
        values.append(name)
    if enabled is not None:
        assignments.append("enabled = ?")
        values.append(int(enabled))
        assignments.append("source_status = ?")
        values.append("reconnecting" if enabled else "disabled")
        assignments.append("status = ?")
        values.append("processing" if enabled else "paused")
    if recursive is not None:
        assignments.append("recursive = ?")
        values.append(int(recursive))
    if not assignments:
        return

    conn = get_conn()
    try:
        values.append(folder_id)
        conn.execute(
            f"UPDATE folders SET {', '.join(assignments)} WHERE id = ?",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def update_source_state(
    folder_id: int,
    source_status: str,
    error: str | None = None,
) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE folders SET source_status = ?, last_error = ? WHERE id = ?",
            (source_status, error, folder_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_folder_scanned(folder_id: int, *, changed: bool) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE folders
            SET scanned_at = datetime('now'),
                revision = revision + ?
            WHERE id = ?""",
            (int(changed), folder_id),
        )
        conn.commit()
    finally:
        conn.close()


def folder_has_unprocessed_images(folder_id: int) -> bool:
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT 1 FROM images
            WHERE folder_id = ? AND metadata_json IS NULL AND error IS NULL
            LIMIT 1""",
            (folder_id,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def consolidate_legacy_source(path: str) -> None:
    """Merge the former '<source> (no metadata)' pseudo-folder into its source."""
    derived_path = f"{path} (no metadata)"
    conn = get_conn()
    try:
        source = conn.execute(
            "SELECT id FROM folders WHERE path = ?",
            (path,),
        ).fetchone()
        derived = conn.execute(
            "SELECT id FROM folders WHERE path = ?",
            (derived_path,),
        ).fetchone()
        if not source or not derived or source["id"] == derived["id"]:
            return

        source_id = int(source["id"])
        derived_id = int(derived["id"])
        conn.execute("BEGIN")
        conn.execute(
            """DELETE FROM images
            WHERE folder_id = ? AND rel_path IN (
                SELECT rel_path FROM images WHERE folder_id = ?
            )""",
            (derived_id, source_id),
        )
        conn.execute(
            "UPDATE images SET folder_id = ? WHERE folder_id = ?",
            (source_id, derived_id),
        )
        conn.execute("DELETE FROM folders WHERE id = ?", (derived_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def split_folder_by_metadata(folder_id: int) -> None:
    """After worker finishes a folder, split images into metadata / no-metadata sibling folders.

    Rules:
    - If the folder contains both metadata and no-metadata images, create a sibling
      '<name> (no metadata)' folder and move the no-metadata images there.
    - If the folder contains ONLY no-metadata images, rename it to '<name> (no metadata)'.
    - If the folder contains ONLY metadata images, do nothing.
    - Skip uploads folders.
    """
    conn = get_conn()
    try:
        folder_row = conn.execute(
            "SELECT id, path, name FROM folders WHERE id = ?", (folder_id,)
        ).fetchone()
        if not folder_row:
            return

        folder_path = folder_row["path"]
        folder_name = folder_row["name"]

        # Skip uploads folders and already-split '(no metadata)' folders
        if folder_path in ("__uploads__", "__uploads_no_metadata__"):
            return
        if folder_name.endswith("(no metadata)"):
            return

        no_meta_cond = (
            "(error IS NOT NULL OR "
            "(metadata_json IS NOT NULL "
            "AND json_extract(metadata_json, '$.prompt_parameters') IS NULL "
            "AND json_extract(metadata_json, '$.workflow') IS NULL))"
        )
        has_meta_cond = (
            "(error IS NULL AND "
            "(metadata_json IS NULL "
            "OR json_extract(metadata_json, '$.prompt_parameters') IS NOT NULL "
            "OR json_extract(metadata_json, '$.workflow') IS NOT NULL))"
        )

        count_no_meta = conn.execute(
            f"SELECT COUNT(*) AS c FROM images WHERE folder_id = ? AND {no_meta_cond}",
            (folder_id,),
        ).fetchone()["c"]

        if count_no_meta == 0:
            # All images have metadata — nothing to do
            return

        count_has_meta = conn.execute(
            f"SELECT COUNT(*) AS c FROM images WHERE folder_id = ? AND {has_meta_cond}",
            (folder_id,),
        ).fetchone()["c"]

        if count_has_meta == 0:
            # ALL images lack metadata — rename the folder itself
            new_name = f"{folder_name} (no metadata)"
            new_path = f"{folder_path} (no metadata)"
            conn.execute(
                "UPDATE folders SET name = ?, path = ? WHERE id = ?",
                (new_name, new_path, folder_id),
            )
            conn.commit()
            return

        # Mixed: create sibling folder and move no-metadata images there
        no_meta_path = f"{folder_path} (no metadata)"
        no_meta_name = f"{folder_name} (no metadata)"

        # Upsert the sibling folder
        cur = conn.execute(
            "INSERT INTO folders (path, name, status, scanned_at) "
            "VALUES (?, ?, 'completed', datetime('now')) "
            "ON CONFLICT(path) DO UPDATE SET scanned_at=datetime('now'), status='completed' "
            "RETURNING id",
            (no_meta_path, no_meta_name),
        )
        no_meta_folder_id = cur.fetchone()["id"]

        # Move no-metadata images to the sibling folder
        conn.execute(
            f"UPDATE images SET folder_id = ? WHERE folder_id = ? AND {no_meta_cond}",
            (no_meta_folder_id, folder_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_image_ids_by_rel_paths(folder_id: int, rel_paths: list[str]) -> list[int]:
    if not rel_paths:
        return []
    conn = get_conn()
    try:
        ids = []
        for i in range(0, len(rel_paths), 500):
            chunk = rel_paths[i : i + 500]
            placeholders = ",".join("?" for _ in chunk)
            rows = conn.execute(
                f"SELECT id FROM images WHERE folder_id = ? AND rel_path IN ({placeholders})",
                [folder_id] + chunk,
            ).fetchall()
            ids.extend(r["id"] for r in rows)
        return ids
    finally:
        conn.close()


def get_folder_asset_ids(folder_id: int) -> list[int]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id FROM images WHERE folder_id = ?",
            (folder_id,),
        ).fetchall()
        return [int(row["id"]) for row in rows]
    finally:
        conn.close()


def get_folder_image_ids(folder_id: int) -> list[int]:
    """Compatibility wrapper returning all indexed asset IDs for a source."""
    return get_folder_asset_ids(folder_id)


def delete_images_by_ids(image_ids: list[int]) -> None:
    if not image_ids:
        return
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        for i in range(0, len(image_ids), 500):
            chunk = image_ids[i : i + 500]
            placeholders = ",".join("?" for _ in chunk)
            conn.execute(
                f"DELETE FROM images WHERE id IN ({placeholders})",
                chunk,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _update_image_metadata(
    conn: sqlite3.Connection,
    image_id: int,
    metadata: ImageMetadata,
) -> None:
    conn.execute(
        """UPDATE images SET
            format = ?, width = ?, height = ?, mode = ?, error = ?, metadata_json = ?,
            created_at = datetime('now')
        WHERE id = ?""",
        (
            metadata.format,
            metadata.size[0] if metadata.size else 0,
            metadata.size[1] if metadata.size else 0,
            metadata.mode,
            metadata.error,
            metadata.model_dump_json(),
            image_id,
        ),
    )


def update_video_metadata(
    asset_id: int,
    *,
    format: str | None,
    width: int,
    height: int,
    mode: str | None,
    duration: float | None,
    frame_rate: float | None,
    codec: str | None,
    metadata: dict[str, Any],
) -> None:
    """Persist technical metadata that came from the original video."""
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE images SET format = ?, width = ?, height = ?, mode = ?,
                duration = ?, frame_rate = ?, codec = ?, metadata_json = ?,
                created_at = datetime('now')
            WHERE id = ? AND media_type = 'video'""",
            (
                format,
                width,
                height,
                mode,
                duration,
                frame_rate,
                codec,
                json.dumps(metadata, ensure_ascii=False),
                asset_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_asset_preview_status(
    asset_id: int,
    status: str,
    error: str | None = None,
) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE images SET preview_status = ?, preview_error = ? WHERE id = ?",
            (status, error, asset_id),
        )
        conn.commit()
    finally:
        conn.close()


def ensure_image_processed(image_id: int, img_path: str) -> None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT metadata_json, error FROM images WHERE id = ?", (image_id,)
        ).fetchone()
        if row and row["metadata_json"] is None and row["error"] is None:
            # Process it
            from .extractor import extract_metadata
            abs_path = Path(img_path)
            if abs_path.is_file():
                try:
                    meta = extract_metadata(abs_path)
                    _update_image_metadata(conn, image_id, meta)
                    conn.commit()
                except Exception as e:
                    import traceback
                    err_str = str(e) + "\n" + traceback.format_exc()
                    conn.execute(
                        "UPDATE images SET error = ? WHERE id = ?",
                        (err_str, image_id),
                    )
                    conn.commit()
            else:
                err_str = f"File not found: {abs_path}"
                conn.execute(
                    "UPDATE images SET error = ? WHERE id = ?",
                    (err_str, image_id),
                )
                conn.commit()
    finally:
        conn.close()


def get_images_page(
    folder_id: int | None,
    page: int = 1,
    per_page: int = 50,
    sort_by: str = "date",
    sort_dir: str = "desc",
    album_id: int | None = None,
    rating: int | None = None,
    media_types: tuple[str, ...] = ("image",),
) -> ImagesResponse:
    if rating is not None and rating not in range(6):
        raise ValueError("rating must be between 0 and 5")
    normalized_media_types = tuple(dict.fromkeys(media_types))
    if not normalized_media_types or any(
        media_type not in ("image", "video")
        for media_type in normalized_media_types
    ):
        raise ValueError("media_types must contain image and/or video")

    conn = get_conn()
    try:
        rating_clause = "" if rating is None else " AND COALESCE(i.rating, 0) = ?"
        rating_params: tuple[int, ...] = () if rating is None else (rating,)
        media_placeholders = ", ".join("?" for _ in normalized_media_types)
        media_clause = f" AND i.media_type IN ({media_placeholders})"
        if album_id is not None:
            total_row = conn.execute(
                f"""SELECT COUNT(*) AS c FROM images i
                JOIN folders f ON f.id = i.folder_id
                JOIN album_images ai ON ai.image_id = i.id
                WHERE ai.album_id = ? AND f.enabled = 1
                  {media_clause}{rating_clause}""",
                (album_id, *normalized_media_types, *rating_params),
            ).fetchone()
        elif folder_id is not None:
            total_row = conn.execute(
                f"""SELECT COUNT(*) AS c FROM images i
                JOIN folders f ON f.id = i.folder_id
                WHERE i.folder_id = ? AND f.enabled = 1
                  {media_clause}{rating_clause}""",
                (folder_id, *normalized_media_types, *rating_params),
            ).fetchone()
        else:
            total_row = conn.execute(
                f"""SELECT COUNT(*) AS c FROM images i
                JOIN folders f ON f.id = i.folder_id
                WHERE f.enabled = 1{media_clause}{rating_clause}""",
                (*normalized_media_types, *rating_params),
            ).fetchone()

        total = total_row["c"] if total_row else 0
        offset = (page - 1) * per_page

        # Map sorting key to column names safely
        sort_by_map = {
            "name": "i.file_name",
            "date": "i.file_mtime",
            "size": "i.file_size",
            "type": "i.format",
        }
        sort_column = sort_by_map.get(sort_by, "i.file_name")
        direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

        # Determine secondary sort order for stability
        if sort_column == "i.file_name":
            order_clause = f"ORDER BY i.file_name {direction}"
        else:
            order_clause = f"ORDER BY {sort_column} {direction}, i.file_name ASC"

        if album_id is not None:
            rows = conn.execute(
                f"""SELECT i.id, i.file_name, i.media_type, i.mime_type,
                    i.format, i.width, i.height, i.mode,
                    i.duration, i.frame_rate, i.codec, i.preview_status,
                    i.preview_error, i.error, i.metadata_json, i.rating,
                    i.original_data IS NULL AS has_local_file
                FROM images i
                JOIN folders f ON f.id = i.folder_id
                JOIN album_images ai ON ai.image_id = i.id
                WHERE ai.album_id = ? AND f.enabled = 1
                  {media_clause}{rating_clause}
                {order_clause} LIMIT ? OFFSET ?""",
                (
                    album_id,
                    *normalized_media_types,
                    *rating_params,
                    per_page,
                    offset,
                ),
            ).fetchall()
        elif folder_id is not None:
            rows = conn.execute(
                f"""SELECT i.id, i.file_name, i.media_type, i.mime_type,
                    i.format, i.width, i.height, i.mode,
                    i.duration, i.frame_rate, i.codec, i.preview_status,
                    i.preview_error, i.error, i.metadata_json, i.rating,
                    i.original_data IS NULL AS has_local_file
                FROM images i JOIN folders f ON f.id = i.folder_id
                WHERE i.folder_id = ? AND f.enabled = 1
                  {media_clause}{rating_clause}
                {order_clause} LIMIT ? OFFSET ?""",
                (
                    folder_id,
                    *normalized_media_types,
                    *rating_params,
                    per_page,
                    offset,
                ),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""SELECT i.id, i.file_name, i.media_type, i.mime_type,
                    i.format, i.width, i.height, i.mode,
                    i.duration, i.frame_rate, i.codec, i.preview_status,
                    i.preview_error, i.error, i.metadata_json, i.rating,
                    i.original_data IS NULL AS has_local_file
                FROM images i JOIN folders f ON f.id = i.folder_id
                WHERE f.enabled = 1{media_clause}{rating_clause}
                {order_clause} LIMIT ? OFFSET ?""",
                (*normalized_media_types, *rating_params, per_page, offset),
            ).fetchall()
        images = []
        for r in rows:
            d = dict(r)
            w, h = d.get("width"), d.get("height")
            meta_json = d.get("metadata_json")
            prompt_parameters = None
            if meta_json:
                try:
                    meta_data = json.loads(meta_json)
                    prompt_parameters = meta_data.get("prompt_parameters")
                except (json.JSONDecodeError, TypeError):
                    pass
            images.append(ImageListItem(
                id=d.get("id"),
                file_name=d.get("file_name", ""),
                media_type=d.get("media_type") or "image",
                mime_type=d.get("mime_type") or "application/octet-stream",
                format=d.get("format"),
                size=[w, h] if w and h else None,
                mode=d.get("mode"),
                duration=d.get("duration"),
                frame_rate=d.get("frame_rate"),
                codec=d.get("codec"),
                preview_status=d.get("preview_status"),
                preview_error=d.get("preview_error"),
                error=d.get("error"),
                has_local_file=bool(d.get("has_local_file")),
                rating=d.get("rating"),
                prompt_parameters=prompt_parameters,
            ))
        return ImagesResponse(images=images, total=total, page=page, per_page=per_page)
    finally:
        conn.close()


def get_asset_path(asset_id: int) -> str | None:
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT f.path, i.rel_path FROM images i
            JOIN folders f ON f.id = i.folder_id
            WHERE i.id = ?""",
            (asset_id,),
        ).fetchone()
        if row:
            return str(Path(row["path"]) / row["rel_path"])
        return None
    finally:
        conn.close()


def get_image_path(image_id: int) -> str | None:
    """Compatibility wrapper for callers using the image ID terminology."""
    return get_asset_path(image_id)


def get_asset_source_info(asset_id: int) -> dict[str, Any] | None:
    """Return source metadata without loading an uploaded BLOB into memory."""
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT i.id, i.rel_path, i.file_name, i.file_size, i.file_mtime,
                i.media_type, i.mime_type, i.format, i.duration, i.preview_status,
                i.preview_error, i.original_data IS NOT NULL AS has_original_data,
                f.path AS folder_path
            FROM images i
            JOIN folders f ON f.id = i.folder_id
            WHERE i.id = ?""",
            (asset_id,),
        ).fetchone()
        if not row:
            return None

        source = dict(row)
        source["path"] = None
        if not source["has_original_data"]:
            source["path"] = str(
                Path(source["folder_path"]) / source["rel_path"]
            )
        return source
    finally:
        conn.close()


def get_image_source_info(image_id: int) -> dict[str, Any] | None:
    """Compatibility wrapper for the former image-only source lookup."""
    return get_asset_source_info(image_id)


def iter_asset_original_data(
    asset_id: int,
    chunk_size: int = 1024 * 1024,
):
    """Stream an SQLite BLOB without materializing the full value as bytes."""
    conn = get_conn()
    try:
        with conn.blobopen(
            "images",
            "original_data",
            asset_id,
            readonly=True,
        ) as blob:
            while True:
                chunk = blob.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    finally:
        conn.close()


def iter_image_original_data(
    image_id: int,
    chunk_size: int = 1024 * 1024,
):
    """Compatibility wrapper for uploaded image BLOB streaming."""
    yield from iter_asset_original_data(image_id, chunk_size)


def get_asset_detail(asset_id: int) -> ImageDetail | None:
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT i.id, i.folder_id, i.rel_path, i.file_name, i.media_type,
                i.mime_type, i.format, i.width, i.height, i.mode, i.duration,
                i.frame_rate, i.codec, i.error, i.metadata_json,
                i.ai_annotations_json, i.preview_status, i.preview_error,
                i.is_favorite, i.rating, i.note,
                i.original_data IS NOT NULL AS has_original_data,
                i.original_data IS NULL AS has_local_file,
                f.path AS folder_path
            FROM images i
            JOIN folders f ON f.id = i.folder_id
            WHERE i.id = ?""",
            (asset_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        if (
            d.get("media_type") == "image"
            and d.get("metadata_json") is None
            and d.get("error") is None
        ):
            img_id = d["id"]
            try:
                if d.get("has_original_data"):
                    original_row = conn.execute(
                        "SELECT original_data FROM images WHERE id = ?",
                        (img_id,),
                    ).fetchone()
                    if not original_row or original_row["original_data"] is None:
                        raise FileNotFoundError("Database original not found")
                    from .extractor import extract_metadata_from_bytes
                    meta = extract_metadata_from_bytes(
                        bytes(original_row["original_data"]),
                        d["file_name"],
                    )
                else:
                    abs_path = Path(d["folder_path"]) / d["rel_path"]
                    if not abs_path.is_file():
                        raise FileNotFoundError(f"File not found: {abs_path}")
                    from .extractor import extract_metadata
                    meta = extract_metadata(abs_path)

                _update_image_metadata(conn, img_id, meta)
                conn.commit()
                d["format"] = meta.format
                d["width"] = meta.size[0] if meta.size else 0
                d["height"] = meta.size[1] if meta.size else 0
                d["mode"] = meta.mode
                d["error"] = meta.error
                d["metadata_json"] = meta.model_dump_json()
            except Exception as e:
                import traceback
                err_str = str(e) + "\n" + traceback.format_exc()
                conn.execute(
                    "UPDATE images SET error = ? WHERE id = ?",
                    (err_str, img_id),
                )
                conn.commit()
                d["error"] = err_str

        meta_json = d.pop("metadata_json", None)
        merged: dict[str, Any] = {}
        if meta_json:
            try:
                merged = json.loads(meta_json)
            except (json.JSONDecodeError, TypeError):
                pass

        ai_json = d.pop("ai_annotations_json", None)
        ai_annotations: dict[str, Any] | None = None
        if ai_json:
            try:
                parsed_ai = json.loads(ai_json)
                if isinstance(parsed_ai, dict):
                    ai_annotations = parsed_ai
            except (json.JSONDecodeError, TypeError):
                pass

        tag_rows = conn.execute(
            """SELECT t.name FROM image_tags it
            JOIN tags t ON t.id = it.tag_id
            WHERE it.image_id = ? ORDER BY t.name COLLATE NOCASE""",
            (d["id"],),
        ).fetchall()
        user_metadata = {
            "favorite": bool(d.get("is_favorite")),
            "rating": d.get("rating"),
            "note": d.get("note") or "",
            "tags": [str(row["name"]) for row in tag_rows],
        }

        w, h = d.get("width"), d.get("height")
        return ImageDetail(
            id=d.get("id"),
            file_name=d.get("file_name", ""),
            media_type=d.get("media_type") or "image",
            mime_type=d.get("mime_type") or "application/octet-stream",
            format=merged.get("format") or d.get("format"),
            size=[w, h] if w and h else merged.get("size"),
            mode=merged.get("mode") or d.get("mode"),
            duration=d.get("duration"),
            frame_rate=d.get("frame_rate"),
            codec=d.get("codec"),
            preview_status=d.get("preview_status"),
            preview_error=d.get("preview_error"),
            error=d.get("error"),
            prompt_parameters=merged.get("prompt_parameters"),
            workflow=merged.get("workflow"),
            workflow_ui_json=merged.get("workflow_ui_json"),
            exif=merged.get("exif"),
            raw_chunks=merged.get("raw_chunks"),
            raw_parameters=merged.get("raw_parameters"),
            raw_params=merged.get("raw_parameters"),
            folder_id=d.get("folder_id"),
            has_local_file=bool(d.get("has_local_file")),
            rating=d.get("rating"),
            embedded_metadata=merged or None,
            user_metadata=user_metadata,
            ai_annotations=ai_annotations,
        )
    finally:
        conn.close()


def get_image_detail(image_id: int) -> ImageDetail | None:
    """Compatibility wrapper for the existing image detail endpoint."""
    return get_asset_detail(image_id)


def delete_folder(folder_id: int) -> None:
    conn = get_conn()
    try:
        conn.execute("DELETE FROM images WHERE folder_id = ?", (folder_id,))
        conn.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_image(image_id: int) -> bool:
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM images WHERE id = ?", (image_id,))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_diagnostics() -> dict[str, Any]:
    conn = get_conn()
    try:
        folders_row = conn.execute("SELECT COUNT(*) AS c FROM folders").fetchone()
        assets_row = conn.execute(
            """SELECT COUNT(*) AS assets,
                SUM(CASE WHEN media_type = 'image' THEN 1 ELSE 0 END) AS images,
                SUM(CASE WHEN media_type = 'video' THEN 1 ELSE 0 END) AS videos
            FROM images"""
        ).fetchone()
        uploads_row = conn.execute(
            "SELECT COUNT(*) AS c FROM images WHERE original_data IS NOT NULL"
        ).fetchone()
        return {
            "db_path": get_db_path(),
            "folders": folders_row["c"] if folders_row else 0,
            "assets": int(assets_row["assets"] or 0) if assets_row else 0,
            "images": int(assets_row["images"] or 0) if assets_row else 0,
            "videos": int(assets_row["videos"] or 0) if assets_row else 0,
            "uploads": uploads_row["c"] if uploads_row else 0,
        }
    finally:
        conn.close()


def insert_upload_asset(
    file_name: str,
    original_data: bytes,
    *,
    media_type: str,
    has_generation_metadata: bool = False,
    format_name: str | None = None,
    width: int = 0,
    height: int = 0,
    mode: str | None = None,
    duration: float | None = None,
    frame_rate: float | None = None,
    codec: str | None = None,
    embedded_metadata: dict[str, Any] | None = None,
    preview_status: str = "pending",
    preview_error: str | None = None,
) -> tuple[int, int]:
    if media_type not in ("image", "video"):
        raise ValueError(f"Unsupported media type: {media_type}")

    conn = get_conn()
    try:
        has_embedded_metadata = media_type == "video" or has_generation_metadata
        folder_path = "__uploads__" if has_embedded_metadata else "__uploads_no_metadata__"
        folder_name = "Uploads" if has_embedded_metadata else "Uploads (no metadata)"

        folder_row = conn.execute(
            "SELECT id FROM folders WHERE path = ?", (folder_path,)
        ).fetchone()
        if not folder_row:
            conn.execute(
                "INSERT INTO folders (path, name) VALUES (?, ?)", (folder_path, folder_name)
            )
            folder_row = conn.execute(
                "SELECT id FROM folders WHERE path = ?", (folder_path,)
            ).fetchone()
        folder_id = folder_row["id"]

        safe_name = portable_filename(file_name)
        from .media import mime_type_for_path

        mime_type = mime_type_for_path(safe_name)
        stem = Path(safe_name).stem
        suffix = Path(safe_name).suffix
        counter = 0
        while True:
            rel_path = safe_name if counter == 0 else f"{stem}_{counter}{suffix}"
            try:
                cur = conn.execute(
                    """INSERT INTO images (
                        folder_id, rel_path, file_name, file_size, file_mtime,
                        media_type, mime_type, format, width, height, mode,
                        duration, frame_rate, codec, metadata_json,
                        preview_status, preview_error, original_data, content_fingerprint
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING id""",
                    (
                        folder_id,
                        rel_path,
                        safe_name,
                        len(original_data),
                        time.time(),
                        media_type,
                        mime_type,
                        format_name,
                        width,
                        height,
                        mode,
                        duration,
                        frame_rate,
                        codec,
                        json.dumps(embedded_metadata, ensure_ascii=False)
                        if embedded_metadata is not None
                        else None,
                        preview_status,
                        preview_error,
                        original_data,
                        hashlib.sha256(original_data).hexdigest(),
                    ),
                )
                break
            except sqlite3.IntegrityError as exc:
                if "images.folder_id, images.rel_path" not in str(exc):
                    raise
                counter += 1

        row = cur.fetchone()
        image_id = row["id"]
        conn.commit()
        return image_id, folder_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_upload_image(
    file_name: str,
    original_data: bytes,
    has_metadata: bool,
) -> tuple[int, int]:
    """Compatibility wrapper for the former image-only upload path."""
    return insert_upload_asset(
        file_name,
        original_data,
        media_type="image",
        has_generation_metadata=has_metadata,
    )


def get_asset_original_data(asset_id: int) -> bytes | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT original_data FROM images WHERE id = ?", (asset_id,)
        ).fetchone()
        if row and row["original_data"]:
            return bytes(row["original_data"])
        return None
    finally:
        conn.close()


def get_image_original_data(image_id: int) -> bytes | None:
    """Compatibility wrapper for callers using image terminology."""
    return get_asset_original_data(image_id)


def get_image_format(image_id: int) -> str | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT format, file_name FROM images WHERE id = ?", (image_id,)
        ).fetchone()
        if row:
            if row["format"]:
                return row["format"]
            suffix = Path(row["file_name"]).suffix.lower().lstrip(".")
            return suffix or None
        return None
    finally:
        conn.close()
