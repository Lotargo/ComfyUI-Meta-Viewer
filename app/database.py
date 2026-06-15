from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

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
    conn.commit()
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


def get_folder_mtimes(folder_id: int) -> dict[str, float]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT rel_path, file_mtime FROM images WHERE folder_id = ?", (folder_id,)
        ).fetchall()
        return {r["rel_path"]: r["file_mtime"] for r in rows}
    finally:
        conn.close()


def insert_images(folder_id: int, images: list[dict[str, Any]]) -> None:
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
                    img.get("rel_path", ""),
                    img.get("file_name", ""),
                    img.get("file_size", 0),
                    img.get("file_mtime", 0),
                    img.get("format"),
                    img.get("width", 0),
                    img.get("height", 0),
                    img.get("mode"),
                    img.get("error"),
                    img.get("metadata_json"),
                    img.get("thumbnail_b64"),
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_folders() -> list[dict[str, Any]]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT f.id, f.path, f.name, f.scanned_at, COUNT(i.id) AS image_count
            FROM folders f LEFT JOIN images i ON i.folder_id = f.id
            GROUP BY f.id ORDER BY f.scanned_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_images_page(
    folder_id: int, page: int = 1, per_page: int = 50
) -> dict[str, Any]:
    conn = get_conn()
    try:
        total_row = conn.execute(
            "SELECT COUNT(*) AS c FROM images WHERE folder_id = ?", (folder_id,)
        ).fetchone()
        total = total_row["c"] if total_row else 0
        offset = (page - 1) * per_page
        rows = conn.execute(
            """SELECT id, file_name, format, width, height, error
            FROM images WHERE folder_id = ?
            ORDER BY file_name LIMIT ? OFFSET ?""",
            (folder_id, per_page, offset),
        ).fetchall()
        images = []
        for r in rows:
            d = dict(r)
            if d.get("width") and d.get("height"):
                d["size"] = [d["width"], d["height"]]
            images.append(d)
        return {"images": images, "total": total, "page": page, "per_page": per_page}
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


def get_image_detail(image_id: int) -> dict[str, Any] | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        meta_json = d.pop("metadata_json", None)
        if meta_json:
            try:
                meta = json.loads(meta_json)
                d.update(meta)
            except (json.JSONDecodeError, TypeError):
                pass
        d.pop("folder_id", None)
        d.pop("rel_path", None)
        d.pop("file_size", None)
        d.pop("file_mtime", None)
        d.pop("created_at", None)
        d.pop("thumbnail_b64", None)
        d.pop("original_data", None)
        if d.get("width") and d.get("height"):
            d["size"] = [d.pop("width"), d.pop("height")]
        return d
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


def insert_upload_image(
    file_name: str,
    original_data: bytes,
    metadata: dict[str, Any],
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
                metadata.get("format"),
                metadata.get("size", [0, 0])[0] if metadata.get("size") else 0,
                metadata.get("size", [0, 0])[1] if metadata.get("size") else 0,
                metadata.get("mode"),
                metadata.get("error"),
                json.dumps(metadata, default=str),
                thumbnail_b64,
                original_data,
            ),
        )
        row = cur.fetchone()
        image_id = row["id"]
        conn.commit()
        return image_id, folder_id
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
