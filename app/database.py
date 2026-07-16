from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .schemas import FolderInfo, ImageDetail, ImageInsertRow, ImageListItem, ImageMetadata, ImagesResponse

_DB_PATH: str | None = None


def get_db_path() -> str:
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = str(Path("cache") / "meta.db")
    return _DB_PATH


def set_db_path(path: str | Path) -> None:
    global _DB_PATH
    _DB_PATH = str(path)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'idle',
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
            format TEXT,
            width INTEGER DEFAULT 0,
            height INTEGER DEFAULT 0,
            mode TEXT,
            error TEXT,
            metadata_json TEXT,
            thumbnail_b64 TEXT,
            original_data BLOB,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(folder_id, rel_path)
        );

        CREATE INDEX IF NOT EXISTS idx_images_folder ON images(folder_id);
        CREATE INDEX IF NOT EXISTS idx_images_folder_mtime ON images(folder_id, file_mtime);
    """)
    try:
        conn.execute("ALTER TABLE images ADD COLUMN original_data BLOB")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE folders ADD COLUMN status TEXT NOT NULL DEFAULT 'idle'")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def clear_db() -> None:
    conn = get_conn()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("DROP TABLE IF EXISTS images")
        conn.execute("DROP TABLE IF EXISTS folders")
        conn.execute("DROP TABLE IF EXISTS sessions")
        conn.commit()
    finally:
        conn.close()
    init_db()



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


def get_folder_mtimes(folder_id: int) -> dict[str, float]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT rel_path, file_mtime FROM images WHERE folder_id = ?", (folder_id,)
        ).fetchall()
        return {r["rel_path"]: r["file_mtime"] for r in rows}
    finally:
        conn.close()


def insert_images(folder_id: int, images: list[ImageInsertRow]) -> None:
    if not images:
        return
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        for img in images:
            conn.execute(
                """INSERT INTO images (folder_id, rel_path, file_name, file_size, file_mtime,
                    format, width, height, mode, error, metadata_json, thumbnail_b64)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(folder_id, rel_path) DO UPDATE SET
                    file_size=excluded.file_size, file_mtime=excluded.file_mtime,
                    format=excluded.format, width=excluded.width, height=excluded.height,
                    mode=excluded.mode, error=excluded.error,
                    metadata_json=excluded.metadata_json, thumbnail_b64=excluded.thumbnail_b64,
                    created_at=datetime('now')""",
                (
                    folder_id,
                    img.rel_path,
                    img.file_name,
                    img.file_size,
                    img.file_mtime,
                    img.format,
                    img.width,
                    img.height,
                    img.mode,
                    img.error,
                    img.metadata_json,
                    img.thumbnail_b64,
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_folders() -> list[FolderInfo]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT f.id, f.path, f.name, f.scanned_at, f.status, COUNT(i.id) AS image_count,
               SUM(CASE WHEN i.metadata_json IS NOT NULL OR i.error IS NOT NULL THEN 1 ELSE 0 END) AS processed_count
            FROM folders f LEFT JOIN images i ON i.folder_id = f.id
            GROUP BY f.id ORDER BY f.scanned_at DESC"""
        ).fetchall()
        return [FolderInfo.model_validate(dict(r)) for r in rows]
    finally:
        conn.close()


def update_folder_status(folder_id: int, status: str) -> None:
    conn = get_conn()
    try:
        conn.execute("UPDATE folders SET status = ? WHERE id = ?", (status, folder_id))
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
                            image_id,
                        ),
                    )
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
    folder_id: int | None, page: int = 1, per_page: int = 50
) -> ImagesResponse:
    conn = get_conn()
    try:
        if folder_id is not None:
            total_row = conn.execute(
                "SELECT COUNT(*) AS c FROM images WHERE folder_id = ?", (folder_id,)
            ).fetchone()
        else:
            total_row = conn.execute("SELECT COUNT(*) AS c FROM images").fetchone()
        total = total_row["c"] if total_row else 0
        offset = (page - 1) * per_page
        if folder_id is not None:
            rows = conn.execute(
                """SELECT id, file_name, format, width, height, mode, error, metadata_json
                FROM images WHERE folder_id = ?
                ORDER BY file_name LIMIT ? OFFSET ?""",
                (folder_id, per_page, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, file_name, format, width, height, mode, error, metadata_json
                FROM images
                ORDER BY file_name LIMIT ? OFFSET ?""",
                (per_page, offset),
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
                format=d.get("format"),
                size=[w, h] if w and h else None,
                mode=d.get("mode"),
                error=d.get("error"),
                prompt_parameters=prompt_parameters,
            ))
        return ImagesResponse(images=images, total=total, page=page, per_page=per_page)
    finally:
        conn.close()


def get_image_path(image_id: int) -> str | None:
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT f.path, i.rel_path FROM images i
            JOIN folders f ON f.id = i.folder_id
            WHERE i.id = ?""",
            (image_id,),
        ).fetchone()
        if row:
            return str(Path(row["path"]) / row["rel_path"])
        return None
    finally:
        conn.close()


def get_image_detail(image_id: int) -> ImageDetail | None:
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT i.*, f.path AS folder_path
            FROM images i
            JOIN folders f ON f.id = i.folder_id
            WHERE i.id = ?""",
            (image_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("metadata_json") is None and d.get("error") is None:
            img_id = d["id"]
            rel_path = d["rel_path"]
            folder_path = d["folder_path"]
            if folder_path != "__uploads__":
                abs_path = Path(folder_path) / rel_path
                if abs_path.is_file():
                    try:
                        from .extractor import extract_metadata
                        meta = extract_metadata(abs_path)
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
                else:
                    err_str = f"File not found: {abs_path}"
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

        w, h = d.get("width"), d.get("height")
        return ImageDetail(
            id=d.get("id"),
            file_name=d.get("file_name", ""),
            format=merged.get("format") or d.get("format"),
            size=[w, h] if w and h else merged.get("size"),
            mode=merged.get("mode") or d.get("mode"),
            error=d.get("error"),
            prompt_parameters=merged.get("prompt_parameters"),
            workflow=merged.get("workflow"),
            exif=merged.get("exif"),
            raw_chunks=merged.get("raw_chunks"),
            raw_parameters=merged.get("raw_parameters"),
            raw_params=merged.get("raw_parameters"),
        )
    finally:
        conn.close()


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
        images_row = conn.execute("SELECT COUNT(*) AS c FROM images").fetchone()
        uploads_row = conn.execute(
            "SELECT COUNT(*) AS c FROM images WHERE original_data IS NOT NULL"
        ).fetchone()
        return {
            "db_path": get_db_path(),
            "folders": folders_row["c"] if folders_row else 0,
            "images": images_row["c"] if images_row else 0,
            "uploads": uploads_row["c"] if uploads_row else 0,
        }
    finally:
        conn.close()


def insert_upload_image(
    file_name: str,
    original_data: bytes,
    metadata: ImageMetadata,
    thumbnail_b64: str,
) -> tuple[int, int]:
    conn = get_conn()
    try:
        folder_row = conn.execute(
            "SELECT id FROM folders WHERE path = '__uploads__'"
        ).fetchone()
        if not folder_row:
            conn.execute(
                "INSERT INTO folders (path, name) VALUES ('__uploads__', 'Uploads')"
            )
            folder_row = conn.execute(
                "SELECT id FROM folders WHERE path = '__uploads__'"
            ).fetchone()
        folder_id = folder_row["id"]

        cur = conn.execute(
            """INSERT INTO images (folder_id, rel_path, file_name, file_size,
                format, width, height, mode, error, metadata_json, thumbnail_b64, original_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id""",
            (
                folder_id,
                file_name,
                file_name,
                len(original_data),
                metadata.format,
                metadata.size[0] if metadata.size else 0,
                metadata.size[1] if metadata.size else 0,
                metadata.mode,
                metadata.error,
                metadata.model_dump_json(),
                thumbnail_b64,
                original_data,
            ),
        )
        row = cur.fetchone()
        image_id = row["id"]
        conn.commit()
        return image_id, folder_id
    except sqlite3.IntegrityError:
        conn.rollback()
        try:
            # Query for the existing image's ID using a new cursor
            row = conn.execute(
                "SELECT id FROM images WHERE folder_id = ? AND rel_path = ?",
                (folder_id, file_name)
            ).fetchone()
            if row:
                return row["id"], folder_id
        except Exception:
            pass
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_image_original_data(image_id: int) -> bytes | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT original_data FROM images WHERE id = ?", (image_id,)
        ).fetchone()
        if row and row["original_data"]:
            return bytes(row["original_data"])
        return None
    finally:
        conn.close()


def get_image_format(image_id: int) -> str | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT format FROM images WHERE id = ?", (image_id,)
        ).fetchone()
        if row:
            return row["format"]
        return None
    finally:
        conn.close()


