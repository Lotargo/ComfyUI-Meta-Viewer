from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app import database as db


class SQLInjectionPreventionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = db.get_db_path()
        self.db_path = Path(self.temp_dir.name) / "meta.db"
        db.set_db_path(self.db_path)
        db.init_db()

    def tearDown(self) -> None:
        db.set_db_path(self.old_db_path)
        self.temp_dir.cleanup()

    def test_get_images_page_rejects_sql_injection_in_sort_by(self) -> None:
        # A normal call with a valid sort_by and sort_dir should not raise anything
        try:
            db.get_images_page(folder_id=None, sort_by="date", sort_dir="asc")
        except Exception as e:
            self.fail(f"get_images_page raised unexpected exception with valid params: {e}")

        # Try SQL injection in sort_dir
        with self.assertRaises(ValueError):
            db.get_images_page(folder_id=None, sort_by="date", sort_dir="desc; DROP TABLE images;--")

        with self.assertRaises(ValueError):
            db.get_images_page(folder_id=None, sort_by="date", sort_dir="UNION SELECT 1, 2, 3")

    def test_get_images_page_rejects_unmapped_columns_directly(self) -> None:
        # If we directly pass a non-whitelisted sort_column or sort_dir, we can verify that ValueError is correctly raised.
        with self.assertRaises(ValueError) as ctx:
            db.get_images_page(folder_id=None, sort_by="invalid_column", sort_dir="desc")
        self.assertIn("Invalid sort_by parameter", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            db.get_images_page(folder_id=None, sort_by="date", sort_dir="invalid_dir")
        self.assertIn("Invalid sort_dir parameter", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
