from __future__ import annotations

import sqlite3
from typing import Any, Iterable

from . import database as db


SYSTEM_COLLECTIONS = (
    {"id": "all", "name": "All assets"},
    {"id": "favorites", "name": "Favorites"},
    {"id": "without_metadata", "name": "Without metadata"},
    {"id": "recently_added", "name": "Recently added"},
    {"id": "unavailable", "name": "Unavailable"},
    {"id": "images", "name": "Images"},
    {"id": "videos", "name": "Videos"},
    {"id": "not_rated", "name": "Not rated"},
)

_SYSTEM_IDS = {item["id"] for item in SYSTEM_COLLECTIONS}
_VIDEO_SUFFIXES = ("mp4", "webm", "mov", "m4v", "mkv", "avi")


class LibraryError(RuntimeError):
    pass


class LibraryNotFoundError(LibraryError):
    pass


class LibraryConflictError(LibraryError):
    pass


def _clean_name(name: str) -> str:
    clean = " ".join(name.split())
    if not clean:
        raise LibraryError("Album name cannot be empty")
    return clean


def list_albums() -> list[dict[str, Any]]:
    conn = db.get_conn()
    try:
        rows = conn.execute(
            """SELECT a.id, a.name, a.cover_image_id, a.created_at, a.updated_at,
                COUNT(ai.image_id) AS asset_count,
                COALESCE(
                    a.cover_image_id,
                    (SELECT first_ai.image_id FROM album_images first_ai
                     WHERE first_ai.album_id = a.id
                     ORDER BY first_ai.position, first_ai.added_at, first_ai.image_id
                     LIMIT 1)
                ) AS display_cover_image_id
            FROM albums a
            LEFT JOIN album_images ai ON ai.album_id = a.id
            GROUP BY a.id
            ORDER BY a.name COLLATE NOCASE"""
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def create_album(name: str) -> dict[str, Any]:
    conn = db.get_conn()
    try:
        clean = _clean_name(name)
        try:
            cur = conn.execute(
                "INSERT INTO albums (name) VALUES (?) RETURNING id",
                (clean,),
            )
        except sqlite3.IntegrityError as exc:
            raise LibraryConflictError(f'Album "{clean}" already exists') from exc
        album_id = int(cur.fetchone()["id"])
        conn.commit()
    finally:
        conn.close()
    return next(album for album in list_albums() if album["id"] == album_id)


def update_album(
    album_id: int,
    *,
    name: str | None = None,
    cover_image_id: int | None = None,
    clear_cover: bool = False,
) -> dict[str, Any]:
    conn = db.get_conn()
    try:
        album = conn.execute(
            "SELECT id FROM albums WHERE id = ?", (album_id,)
        ).fetchone()
        if album is None:
            raise LibraryNotFoundError("Album not found")

        assignments = ["updated_at = datetime('now')"]
        values: list[Any] = []
        if name is not None:
            assignments.append("name = ?")
            values.append(_clean_name(name))
        if clear_cover:
            assignments.append("cover_image_id = NULL")
        elif cover_image_id is not None:
            member = conn.execute(
                "SELECT 1 FROM album_images WHERE album_id = ? AND image_id = ?",
                (album_id, cover_image_id),
            ).fetchone()
            if member is None:
                raise LibraryError("Album cover must be one of its assets")
            assignments.append("cover_image_id = ?")
            values.append(cover_image_id)

        values.append(album_id)
        try:
            conn.execute(
                f"UPDATE albums SET {', '.join(assignments)} WHERE id = ?",
                values,
            )
        except sqlite3.IntegrityError as exc:
            raise LibraryConflictError("An album with that name already exists") from exc
        conn.commit()
    finally:
        conn.close()
    return next(album for album in list_albums() if album["id"] == album_id)


def delete_album(album_id: int) -> bool:
    conn = db.get_conn()
    try:
        cur = conn.execute("DELETE FROM albums WHERE id = ?", (album_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def _unique_asset_ids(asset_ids: Iterable[int]) -> list[int]:
    return list(dict.fromkeys(int(asset_id) for asset_id in asset_ids))


def _existing_asset_ids(conn: sqlite3.Connection, asset_ids: list[int]) -> list[int]:
    if not asset_ids:
        return []
    found: list[int] = []
    for start in range(0, len(asset_ids), 500):
        chunk = asset_ids[start : start + 500]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT id FROM images WHERE id IN ({placeholders})", chunk
        ).fetchall()
        found.extend(int(row["id"]) for row in rows)
    return found


def add_assets_to_album(album_id: int, asset_ids: Iterable[int]) -> int:
    ids = _unique_asset_ids(asset_ids)
    conn = db.get_conn()
    try:
        if conn.execute(
            "SELECT 1 FROM albums WHERE id = ?", (album_id,)
        ).fetchone() is None:
            raise LibraryNotFoundError("Album not found")
        existing = _existing_asset_ids(conn, ids)
        if len(existing) != len(ids):
            raise LibraryNotFoundError("One or more assets were not found")
        start_position = int(
            conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 AS position FROM album_images WHERE album_id = ?",
                (album_id,),
            ).fetchone()["position"]
        )
        before = conn.total_changes
        conn.executemany(
            """INSERT OR IGNORE INTO album_images (album_id, image_id, position)
            VALUES (?, ?, ?)""",
            [
                (album_id, asset_id, start_position + offset)
                for offset, asset_id in enumerate(ids)
            ],
        )
        changed = conn.total_changes - before
        conn.execute(
            "UPDATE albums SET updated_at = datetime('now') WHERE id = ?",
            (album_id,),
        )
        conn.commit()
        return changed
    finally:
        conn.close()


def remove_assets_from_album(album_id: int, asset_ids: Iterable[int]) -> int:
    ids = _unique_asset_ids(asset_ids)
    conn = db.get_conn()
    try:
        if conn.execute(
            "SELECT 1 FROM albums WHERE id = ?", (album_id,)
        ).fetchone() is None:
            raise LibraryNotFoundError("Album not found")
        removed = 0
        for start in range(0, len(ids), 500):
            chunk = ids[start : start + 500]
            placeholders = ",".join("?" for _ in chunk)
            cur = conn.execute(
                f"DELETE FROM album_images WHERE album_id = ? AND image_id IN ({placeholders})",
                [album_id, *chunk],
            )
            removed += cur.rowcount
        conn.execute(
            """UPDATE albums SET cover_image_id = NULL, updated_at = datetime('now')
            WHERE id = ? AND cover_image_id NOT IN (
                SELECT image_id FROM album_images WHERE album_id = ?
            )""",
            (album_id, album_id),
        )
        conn.commit()
        return removed
    finally:
        conn.close()


def update_asset(
    asset_id: int,
    *,
    favorite: bool | None = None,
    rating: int | None = None,
    note: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    conn = db.get_conn()
    try:
        if conn.execute(
            "SELECT 1 FROM images WHERE id = ?", (asset_id,)
        ).fetchone() is None:
            raise LibraryNotFoundError("Asset not found")

        assignments: list[str] = []
        values: list[Any] = []
        if favorite is not None:
            assignments.append("is_favorite = ?")
            values.append(int(favorite))
        if rating is not None:
            assignments.append("rating = ?")
            values.append(rating or None)
        if note is not None:
            assignments.append("note = ?")
            values.append(note.strip())
        if assignments:
            values.append(asset_id)
            conn.execute(
                f"UPDATE images SET {', '.join(assignments)} WHERE id = ?", values
            )

        if tags is not None:
            clean_tags: dict[str, str] = {}
            for tag in tags:
                clean = " ".join(tag.split())[:80]
                if clean:
                    clean_tags.setdefault(clean.casefold(), clean)
            conn.execute("DELETE FROM image_tags WHERE image_id = ?", (asset_id,))
            for name_key, name in clean_tags.items():
                conn.execute(
                    """INSERT INTO tags (name, name_key) VALUES (?, ?)
                    ON CONFLICT(name_key) DO NOTHING""",
                    (name, name_key),
                )
                tag_id = conn.execute(
                    "SELECT id FROM tags WHERE name_key = ?", (name_key,)
                ).fetchone()["id"]
                conn.execute(
                    "INSERT INTO image_tags (image_id, tag_id) VALUES (?, ?)",
                    (asset_id, tag_id),
                )
            conn.execute(
                "DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM image_tags)"
            )
        conn.commit()
    finally:
        conn.close()

    page = get_assets(asset_id=asset_id, per_page=1)
    if not page["assets"]:
        raise LibraryNotFoundError("Asset not found")
    return page["assets"][0]


def bulk_action(
    asset_ids: Iterable[int],
    action: str,
    *,
    album_id: int | None = None,
    rating: int | None = None,
) -> dict[str, Any]:
    ids = _unique_asset_ids(asset_ids)
    if action == "add_to_album":
        if album_id is None:
            raise LibraryError("album_id is required")
        return {"affected": add_assets_to_album(album_id, ids), "removed_ids": []}
    if action == "remove_from_album":
        if album_id is None:
            raise LibraryError("album_id is required")
        return {"affected": remove_assets_from_album(album_id, ids), "removed_ids": []}

    conn = db.get_conn()
    try:
        existing = _existing_asset_ids(conn, ids)
        if len(existing) != len(ids):
            raise LibraryNotFoundError("One or more assets were not found")
        placeholders = ",".join("?" for _ in ids)
        if action in ("favorite", "unfavorite"):
            cur = conn.execute(
                f"UPDATE images SET is_favorite = ? WHERE id IN ({placeholders})",
                [int(action == "favorite"), *ids],
            )
            removed_ids: list[int] = []
        elif action == "set_rating":
            if rating is None:
                raise LibraryError("rating is required")
            cur = conn.execute(
                f"UPDATE images SET rating = ? WHERE id IN ({placeholders})",
                [rating or None, *ids],
            )
            removed_ids = []
        elif action == "remove_from_index":
            cur = conn.execute(
                f"DELETE FROM images WHERE id IN ({placeholders})", ids
            )
            removed_ids = ids
        else:
            raise LibraryError("Unsupported bulk action")
        conn.commit()
        return {"affected": cur.rowcount, "removed_ids": removed_ids}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_assets(
    *,
    collection: str = "all",
    album_id: int | None = None,
    page: int = 1,
    per_page: int = 80,
    sort_by: str = "date",
    sort_dir: str = "desc",
    query: str = "",
    source_id: int | None = None,
    tag: str | None = None,
    asset_id: int | None = None,
) -> dict[str, Any]:
    if collection not in _SYSTEM_IDS and collection != "album":
        raise LibraryError("Unknown collection")
    if collection == "album" and album_id is None:
        raise LibraryError("album_id is required for an album collection")

    page = max(1, page)
    per_page = min(200, max(1, per_page))
    conditions: list[str] = []
    params: list[Any] = []

    if asset_id is not None:
        conditions.append("i.id = ?")
        params.append(asset_id)
    if collection == "favorites":
        conditions.append("i.is_favorite = 1")
    elif collection == "without_metadata":
        conditions.append(
            """(i.error IS NOT NULL OR (
                i.metadata_json IS NOT NULL
                AND json_extract(i.metadata_json, '$.prompt_parameters') IS NULL
                AND json_extract(i.metadata_json, '$.workflow') IS NULL
            ))"""
        )
    elif collection == "recently_added":
        conditions.append(
            "datetime(i.indexed_at) >= datetime('now', '-30 days')"
        )
    elif collection == "unavailable":
        conditions.append(
            """i.original_data IS NULL AND (
                f.enabled = 0 OR f.source_status IN ('disabled', 'unavailable', 'reconnecting', 'error')
            )"""
        )
    elif collection == "videos":
        placeholders = ",".join("?" for _ in _VIDEO_SUFFIXES)
        conditions.append(
            f"LOWER(COALESCE(i.format, substr(i.file_name, instr(i.file_name, '.') + 1))) IN ({placeholders})"
        )
        params.extend(_VIDEO_SUFFIXES)
    elif collection == "images":
        placeholders = ",".join("?" for _ in _VIDEO_SUFFIXES)
        conditions.append(
            f"LOWER(COALESCE(i.format, substr(i.file_name, instr(i.file_name, '.') + 1))) NOT IN ({placeholders})"
        )
        params.extend(_VIDEO_SUFFIXES)
    elif collection == "not_rated":
        conditions.append("COALESCE(i.rating, 0) = 0")
    elif collection == "album":
        conditions.append(
            "EXISTS (SELECT 1 FROM album_images selected_ai WHERE selected_ai.album_id = ? AND selected_ai.image_id = i.id)"
        )
        params.append(album_id)

    if source_id is not None:
        conditions.append("i.folder_id = ?")
        params.append(source_id)
    if query.strip():
        needle = f"%{query.strip().casefold()}%"
        conditions.append(
            """(LOWER(i.file_name) LIKE ? OR LOWER(i.note) LIKE ? OR EXISTS (
                SELECT 1 FROM image_tags search_it
                JOIN tags search_t ON search_t.id = search_it.tag_id
                WHERE search_it.image_id = i.id AND search_t.name_key LIKE ?
            ))"""
        )
        params.extend((needle, needle, needle))
    if tag:
        conditions.append(
            """EXISTS (SELECT 1 FROM image_tags filter_it
                JOIN tags filter_t ON filter_t.id = filter_it.tag_id
                WHERE filter_it.image_id = i.id AND filter_t.name_key = ?)"""
        )
        params.append(tag.casefold())

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    sort_columns = {
        "name": "i.file_name COLLATE NOCASE",
        "date": "i.file_mtime",
        "added": "i.indexed_at",
        "size": "i.file_size",
        "rating": "COALESCE(i.rating, 0)",
    }
    sort_column = sort_columns.get(sort_by, sort_columns["date"])
    direction = "ASC" if sort_dir.lower() == "asc" else "DESC"
    offset = (page - 1) * per_page

    conn = db.get_conn()
    try:
        total = int(
            conn.execute(
                f"""SELECT COUNT(*) AS count FROM images i
                JOIN folders f ON f.id = i.folder_id{where}""",
                params,
            ).fetchone()["count"]
        )
        rows = conn.execute(
            f"""SELECT i.id, i.folder_id, i.file_name, i.rel_path, i.file_size,
                i.file_mtime, i.format, i.width, i.height, i.error,
                i.metadata_json, i.is_favorite, i.rating, i.note, i.indexed_at,
                i.original_data IS NOT NULL AS has_original_data,
                f.name AS source_name, f.path AS source_path, f.enabled AS source_enabled,
                f.source_status
            FROM images i JOIN folders f ON f.id = i.folder_id{where}
            ORDER BY {sort_column} {direction}, i.id {direction}
            LIMIT ? OFFSET ?""",
            [*params, per_page, offset],
        ).fetchall()
        assets = [dict(row) for row in rows]
        ids = [int(asset["id"]) for asset in assets]
        tags_by_asset: dict[int, list[str]] = {image_id: [] for image_id in ids}
        albums_by_asset: dict[int, list[int]] = {image_id: [] for image_id in ids}
        if ids:
            placeholders = ",".join("?" for _ in ids)
            tag_rows = conn.execute(
                f"""SELECT it.image_id, t.name FROM image_tags it
                JOIN tags t ON t.id = it.tag_id
                WHERE it.image_id IN ({placeholders})
                ORDER BY t.name COLLATE NOCASE""",
                ids,
            ).fetchall()
            for row in tag_rows:
                tags_by_asset[int(row["image_id"])].append(str(row["name"]))
            album_rows = conn.execute(
                f"""SELECT image_id, album_id FROM album_images
                WHERE image_id IN ({placeholders}) ORDER BY album_id""",
                ids,
            ).fetchall()
            for row in album_rows:
                albums_by_asset[int(row["image_id"])].append(int(row["album_id"]))
    finally:
        conn.close()

    for asset in assets:
        image_id = int(asset["id"])
        metadata_json = asset.pop("metadata_json", None)
        asset["favorite"] = bool(asset.pop("is_favorite"))
        asset["source_enabled"] = bool(asset["source_enabled"])
        asset["has_original_data"] = bool(asset["has_original_data"])
        asset["available"] = bool(
            asset["has_original_data"]
            or (
                asset["source_enabled"]
                and asset["source_status"] in ("available", "partially_available")
            )
        )
        asset["has_metadata"] = False
        if metadata_json:
            try:
                import json

                metadata = json.loads(metadata_json)
                asset["has_metadata"] = bool(
                    metadata.get("prompt_parameters") or metadata.get("workflow")
                )
            except (TypeError, ValueError):
                pass
        asset["tags"] = tags_by_asset[image_id]
        asset["album_ids"] = albums_by_asset[image_id]
        asset["thumbnail_url"] = f"/api/thumbnail/{image_id}"
        asset["original_url"] = f"/api/original/{image_id}"

    return {
        "assets": assets,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


def library_summary() -> dict[str, Any]:
    conn = db.get_conn()
    try:
        row = conn.execute(
            """SELECT COUNT(*) AS assets,
                SUM(CASE WHEN is_favorite = 1 THEN 1 ELSE 0 END) AS favorites,
                SUM(CASE WHEN COALESCE(rating, 0) = 0 THEN 1 ELSE 0 END) AS not_rated
            FROM images"""
        ).fetchone()
        unavailable = conn.execute(
            """SELECT COUNT(*) AS count FROM images i JOIN folders f ON f.id = i.folder_id
            WHERE i.original_data IS NULL AND (
                f.enabled = 0 OR f.source_status IN ('disabled', 'unavailable', 'reconnecting', 'error')
            )"""
        ).fetchone()["count"]
        return {
            "assets": int(row["assets"] or 0),
            "favorites": int(row["favorites"] or 0),
            "not_rated": int(row["not_rated"] or 0),
            "unavailable": int(unavailable or 0),
        }
    finally:
        conn.close()
