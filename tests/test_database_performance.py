from __future__ import annotations

import time
import pytest
from pathlib import Path
from app import database as db


@pytest.fixture
def temp_db(tmp_path: Path):
    old_db_path = db.get_db_path()
    db_file = tmp_path / "test_perf.db"
    db.set_db_path(db_file)
    db.init_db()
    yield db_file
    db.set_db_path(old_db_path)


def test_composite_indexes_exist(temp_db):
    """Verify that all new performance composite indexes are created on DB init."""
    conn = db.get_conn()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        index_names = {r["name"] for r in rows}

        expected_indexes = {
            "idx_images_mtime_id",
            "idx_images_media_mtime_id",
            "idx_images_folder_media_mtime_id",
            "idx_images_rating_media_mtime",
            "idx_album_images_album_image",
            "idx_album_images_album_pos",
            "idx_images_indexed_at",
            "idx_images_pending_processing",
        }
        for expected in expected_indexes:
            assert expected in index_names, f"Missing expected index: {expected}"
    finally:
        conn.close()


def test_explain_query_plan_uses_indexes(temp_db):
    """Verify EXPLAIN QUERY PLAN confirms index scan usage without temp B-Tree sorts."""
    folder_id = db.upsert_folder("C:/test_perf_folder")
    conn = db.get_conn()
    try:
        # Populate dummy data
        conn.executemany(
            """INSERT INTO images (folder_id, rel_path, file_name, file_mtime, media_type)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (folder_id, f"file_{i}.jpg", f"file_{i}.jpg", 1000.0 + i, "image")
                for i in range(50)
            ],
        )
        conn.commit()

        # Run EXPLAIN QUERY PLAN on the deferred join subquery
        plan_rows = conn.execute(
            """EXPLAIN QUERY PLAN
               SELECT i2.id FROM images i2
               JOIN folders f2 ON f2.id = i2.folder_id
               WHERE f2.enabled = 1 AND i2.media_type IN ('image')
               ORDER BY i2.file_mtime DESC, i2.id DESC LIMIT 50 OFFSET 0"""
        ).fetchall()

        plan_text = " ".join(r["detail"] for r in plan_rows).lower()
        # Verify index scan is mentioned and no temp B-tree is created for sorting
        assert "idx_images_media_mtime_id" in plan_text or "idx_images_mtime_id" in plan_text or "using index" in plan_text
        assert "use temp b-tree for order by" not in plan_text
    finally:
        conn.close()


def test_deferred_join_correctness_and_ordering(temp_db):
    """Verify that get_images_page returns items in exact descending order of mtime."""
    folder_id = db.upsert_folder("C:/test_correctness_folder")
    conn = db.get_conn()
    try:
        records = [
            (folder_id, f"img_{i}.png", f"img_{i}.png", 100.0 + i, "image")
            for i in range(30)
        ]
        conn.executemany(
            "INSERT INTO images (folder_id, rel_path, file_name, file_mtime, media_type) VALUES (?, ?, ?, ?, ?)",
            records,
        )
        conn.commit()

        page1 = db.get_images_page(folder_id, page=1, per_page=10, sort_by="date", sort_dir="desc")
        assert len(page1.images) == 10
        assert page1.total == 30
        assert page1.images[0].file_name == "img_29.png"
        assert page1.images[9].file_name == "img_20.png"

        page2 = db.get_images_page(folder_id, page=2, per_page=10, sort_by="date", sort_dir="desc")
        assert len(page2.images) == 10
        assert page2.images[0].file_name == "img_19.png"
        assert page2.images[9].file_name == "img_10.png"
    finally:
        conn.close()


def test_keyset_cursor_pagination(temp_db):
    """Verify cursor pagination (cursor_mtime, cursor_id) returns consecutive items without offset."""
    folder_id = db.upsert_folder("C:/test_cursor_folder")
    conn = db.get_conn()
    try:
        # Create records with duplicate mtimes to test tie-breaking by ID
        records = [
            (folder_id, f"file_{i}.jpg", f"file_{i}.jpg", 500.0 + (i // 2), "image")
            for i in range(20)
        ]
        conn.executemany(
            "INSERT INTO images (folder_id, rel_path, file_name, file_mtime, media_type) VALUES (?, ?, ?, ?, ?)",
            records,
        )
        conn.commit()

        page1 = db.get_images_page(folder_id, page=1, per_page=5, sort_by="date", sort_dir="desc")
        assert len(page1.images) == 5

        # Fetch mtime and ID of last item in page 1
        last_item_id = page1.images[-1].id
        last_item_mtime = conn.execute("SELECT file_mtime FROM images WHERE id = ?", (last_item_id,)).fetchone()["file_mtime"]

        # Fetch page 2 using cursor
        page2_cursor = db.get_images_page(
            folder_id,
            page=1,
            per_page=5,
            sort_by="date",
            sort_dir="desc",
            cursor_mtime=last_item_mtime,
            cursor_id=last_item_id,
        )

        assert len(page2_cursor.images) == 5
        # Ensure no overlap between page 1 and page 2
        page1_ids = {img.id for img in page1.images}
        page2_ids = {img.id for img in page2_cursor.images}
        assert page1_ids.isdisjoint(page2_ids)
    finally:
        conn.close()


def test_large_offset_performance_benchmark(temp_db):
    """Verify that deep pagination (e.g. 5,000 items offset) executes sub-second."""
    folder_id = db.upsert_folder("C:/test_benchmark_folder")
    conn = db.get_conn()
    try:
        # Insert 3,000 rows
        records = [
            (folder_id, f"bench_{i}.png", f"bench_{i}.png", 1000.0 + i, "image")
            for i in range(3000)
        ]
        conn.executemany(
            "INSERT INTO images (folder_id, rel_path, file_name, file_mtime, media_type) VALUES (?, ?, ?, ?, ?)",
            records,
        )
        conn.commit()

        t0 = time.monotonic()
        res = db.get_images_page(folder_id=None, page=50, per_page=50, sort_by="date", sort_dir="desc")
        elapsed_ms = (time.monotonic() - t0) * 1000.0

        assert len(res.images) == 50
        assert res.total == 3000
        # Deep pagination query must execute in < 200 ms
        assert elapsed_ms < 200.0, f"Query took too long: {elapsed_ms:.2f} ms"
    finally:
        conn.close()


def test_batch_generation_stability_with_identical_mtimes(temp_db):
    """Verify that multiple items with identical mtime sort consistently by ID in descending order."""
    folder_id = db.upsert_folder("C:/test_batch_folder")
    conn = db.get_conn()
    try:
        # Simulate a batch of 6 images generated in the same second
        records = [
            (folder_id, f"batch_000{i}.png", f"batch_000{i}.png", 1500.0, "image")
            for i in range(1, 7)
        ]
        conn.executemany(
            "INSERT INTO images (folder_id, rel_path, file_name, file_mtime, media_type) VALUES (?, ?, ?, ?, ?)",
            records,
        )
        conn.commit()

        # In DESC order (newest first), the latest created item (highest ID) should come first
        res = db.get_images_page(folder_id, page=1, per_page=10, sort_by="date", sort_dir="desc")
        assert len(res.images) == 6
        file_names = [img.file_name for img in res.images]
        assert file_names == [
            "batch_0006.png",
            "batch_0005.png",
            "batch_0004.png",
            "batch_0003.png",
            "batch_0002.png",
            "batch_0001.png",
        ]

        # In ASC order (oldest first), the earliest created item (lowest ID) should come first
        res_asc = db.get_images_page(folder_id, page=1, per_page=10, sort_by="date", sort_dir="asc")
        file_names_asc = [img.file_name for img in res_asc.images]
        assert file_names_asc == [
            "batch_0001.png",
            "batch_0002.png",
            "batch_0003.png",
            "batch_0004.png",
            "batch_0005.png",
            "batch_0006.png",
        ]
    finally:
        conn.close()


def test_case_insensitive_name_sorting(temp_db):
    """Verify that name sorting is case-insensitive (COLLATE NOCASE)."""
    folder_id = db.upsert_folder("C:/test_nocase_folder")
    conn = db.get_conn()
    try:
        records = [
            (folder_id, "b.png", "b.png", 100.0, "image"),
            (folder_id, "A.png", "A.png", 100.0, "image"),
            (folder_id, "c.png", "c.png", 100.0, "image"),
            (folder_id, "B2.png", "B2.png", 100.0, "image"),
        ]
        conn.executemany(
            "INSERT INTO images (folder_id, rel_path, file_name, file_mtime, media_type) VALUES (?, ?, ?, ?, ?)",
            records,
        )
        conn.commit()

        res_asc = db.get_images_page(folder_id, page=1, per_page=10, sort_by="name", sort_dir="asc")
        names_asc = [img.file_name for img in res_asc.images]
        assert names_asc == ["A.png", "b.png", "B2.png", "c.png"]

        res_desc = db.get_images_page(folder_id, page=1, per_page=10, sort_by="name", sort_dir="desc")
        names_desc = [img.file_name for img in res_desc.images]
        assert names_desc == ["c.png", "B2.png", "b.png", "A.png"]
    finally:
        conn.close()

