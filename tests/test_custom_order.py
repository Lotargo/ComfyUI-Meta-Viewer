"""Server-side custom (drag-reordered) positions: move/bulk/read/prune."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import database
from app import library as media_library
from app.main import app
from app.schemas import AssetInsertRow


def _make_assets(folder_id: int, names: list[str]) -> list[int]:
    rows = [
        AssetInsertRow(rel_path=name, file_name=name, file_mtime=float(index))
        for index, name in enumerate(names)
    ]
    database.insert_assets(folder_id, rows)
    conn = database.get_conn()
    try:
        ids = [
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM images WHERE folder_id = ? ORDER BY rel_path",
                (folder_id,),
            ).fetchall()
        ]
    finally:
        conn.close()
    by_name = {}
    conn = database.get_conn()
    try:
        for row in conn.execute(
            "SELECT id, file_name FROM images WHERE folder_id = ?", (folder_id,)
        ).fetchall():
            by_name[str(row["file_name"])] = int(row["id"])
    finally:
        conn.close()
    return [by_name[name] for name in names]


class CustomOrderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()
        self.folder_id = database.upsert_source("/tmp/pics", name="pics")
        self.scope = f"folder:{self.folder_id}"
        self.client = app.test_client()

    def tearDown(self) -> None:
        database.set_db_path(self.old_db_path)
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _positions(self) -> dict[int, float]:
        conn = database.get_conn()
        try:
            return {
                int(row["image_id"]): float(row["position"])
                for row in conn.execute(
                    "SELECT image_id, position FROM item_positions WHERE scope = ?",
                    (self.scope,),
                ).fetchall()
            }
        finally:
            conn.close()

    def test_first_drag_materializes_scope_and_midpoint_is_exact(self) -> None:
        a, b, c = _make_assets(self.folder_id, ["a.png", "b.png", "c.png"])
        # Fresh view order is newest-first (id DESC): c, b, a.
        pos = media_library.move_custom_order_item(
            self.scope, a, before_id=c, after_id=b
        )
        stored = self._positions()
        # Whole fresh prefix materialized…
        self.assertEqual(set(stored), {a, b, c})
        # …preserving newest-first relative order…
        self.assertLess(stored[c], stored[b])
        # …and the dragged image sits exactly between its neighbors.
        self.assertGreater(pos, stored[c])
        self.assertLess(pos, stored[b])
        self.assertAlmostEqual(pos, (stored[c] + stored[b]) / 2.0)

    def test_new_images_sort_first_in_custom_view(self) -> None:
        a, b = _make_assets(self.folder_id, ["a.png", "b.png"])
        media_library.move_custom_order_item(self.scope, a, after_id=b)
        new_id = _make_assets(self.folder_id, ["z.png"])[0]
        result = media_library.get_assets(
            collection="all", source_id=self.folder_id, sort_by="custom"
        )
        got = [asset["id"] for asset in result["assets"]]
        self.assertEqual(got[0], new_id)
        page = database.get_images_page(
            self.folder_id, page=1, per_page=50, sort_by="custom"
        )
        self.assertEqual(page.images[0].id, new_id)

    def test_bulk_import_drops_foreign_ids(self) -> None:
        a, b = _make_assets(self.folder_id, ["a.png", "b.png"])
        other_folder = database.upsert_source("/tmp/other", name="other")
        (foreign,) = _make_assets(other_folder, ["x.png"])
        result = media_library.set_custom_order(self.scope, [b, foreign, a])
        self.assertEqual(result, {"applied": 2, "dropped": 1})
        stored = media_library.get_custom_order(self.scope)
        self.assertEqual(stored["image_ids"], [b, a])

    def test_bulk_import_rejects_unknown_ids(self) -> None:
        (a,) = _make_assets(self.folder_id, ["a.png"])
        with self.assertRaises(media_library.LibraryNotFoundError):
            media_library.set_custom_order(self.scope, [a, 999999])

    def test_scope_validation(self) -> None:
        with self.assertRaises(media_library.LibraryError):
            media_library.get_custom_order("nope")
        with self.assertRaises(media_library.LibraryError):
            media_library.get_custom_order("album:1")
        with self.assertRaises(media_library.LibraryNotFoundError):
            media_library.get_custom_order("folder:999999")
        # collection:all is normalized to the single media:all scope.
        self.assertEqual(
            media_library.normalize_custom_scope("collection:all"), "media:all"
        )

    def test_move_validation(self) -> None:
        (a,) = _make_assets(self.folder_id, ["a.png"])
        with self.assertRaises(media_library.LibraryNotFoundError):
            media_library.move_custom_order_item(self.scope, 999999)
        with self.assertRaises(media_library.LibraryError):
            media_library.move_custom_order_item(self.scope, a, before_id=a)
        other_folder = database.upsert_source("/tmp/other", name="other")
        (foreign,) = _make_assets(other_folder, ["x.png"])
        with self.assertRaises(media_library.LibraryError):
            media_library.move_custom_order_item(self.scope, foreign)
        with self.assertRaises(media_library.LibraryError):
            media_library.move_custom_order_item(
                self.scope, a, after_id=foreign
            )

    def test_degenerate_gap_triggers_rebalance(self) -> None:
        a, b, c = _make_assets(self.folder_id, ["a.png", "b.png", "c.png"])
        # Half-ULP gap: the midpoint collapses onto pos_before in float
        # arithmetic, forcing the self-rebalance path.
        conn = database.get_conn()
        try:
            conn.executemany(
                "INSERT INTO item_positions (scope, image_id, position)"
                " VALUES (?, ?, ?)",
                [(self.scope, a, 1.0), (self.scope, b, 1.0 + 2.0**-52), (self.scope, c, 9.0)],
            )
            conn.commit()
        finally:
            conn.close()
        pos = media_library.move_custom_order_item(
            self.scope, c, before_id=a, after_id=b
        )
        stored = self._positions()
        self.assertLess(stored[a], pos)
        self.assertLess(pos, stored[b])
        # Rebalanced to even steps.
        gap = stored[b] - stored[a]
        self.assertAlmostEqual(gap, media_library.CUSTOM_ORDER_STEP)

    def test_positions_cascade_on_image_delete(self) -> None:
        a, b = _make_assets(self.folder_id, ["a.png", "b.png"])
        media_library.move_custom_order_item(self.scope, a, after_id=b)
        self.assertEqual(len(self._positions()), 2)
        database.delete_image(a)
        self.assertEqual(set(self._positions()), {b})

    def test_folder_scope_dropped_on_folder_delete(self) -> None:
        a, _b = _make_assets(self.folder_id, ["a.png", "b.png"])
        media_library.move_custom_order_item(self.scope, a)
        database.delete_folder(self.folder_id)
        conn = database.get_conn()
        try:
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM item_positions WHERE scope = ?",
                (self.scope,),
            ).fetchone()["c"]
        finally:
            conn.close()
        self.assertEqual(int(count), 0)

    def test_move_routes_end_to_end(self) -> None:
        a, b = _make_assets(self.folder_id, ["a.png", "b.png"])
        response = self.client.post(
            "/api/custom-order/move",
            json={"scope": self.scope, "image_id": a, "after_id": b},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["image_id"], a)

        response = self.client.get(
            "/api/library/assets",
            query_string={"source_id": self.folder_id, "sort_by": "custom"},
        )
        self.assertEqual(response.status_code, 200)
        got = [asset["id"] for asset in response.get_json()["assets"]]
        self.assertLess(got.index(a), got.index(b))

        response = self.client.get(
            "/api/images",
            query_string={
                "folder_id": self.folder_id,
                "sort_by": "custom",
                "media_type": "image",
            },
        )
        self.assertEqual(response.status_code, 200)
        got = [item["id"] for item in response.get_json()["images"]]
        self.assertLess(got.index(a), got.index(b))

        response = self.client.post(
            "/api/custom-order/move",
            json={"scope": self.scope, "image_id": 999999},
        )
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            "/api/custom-order/move", json={"scope": "bogus", "image_id": a}
        )
        self.assertEqual(response.status_code, 400)

    def test_bulk_route_migrates_local_storage_order(self) -> None:
        a, b, c = _make_assets(self.folder_id, ["a.png", "b.png", "c.png"])
        response = self.client.put(
            "/api/custom-order",
            json={"scope": self.scope, "ordered_ids": [c, a, b]},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(
            (payload["applied"], payload["dropped"]), (3, 0)
        )
        response = self.client.get(
            "/api/custom-order", query_string={"scope": self.scope}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["image_ids"], [c, a, b])


if __name__ == "__main__":
    unittest.main()
