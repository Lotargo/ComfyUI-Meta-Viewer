from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app import database as db


class TestDatabasePaths(unittest.TestCase):
    def setUp(self) -> None:
        # Save the original _DB_PATH value so we can restore it after each test
        self.original_db_path = db._DB_PATH

    def tearDown(self) -> None:
        # Restore the original _DB_PATH value to avoid affecting other tests
        db._DB_PATH = self.original_db_path

    def test_get_db_path_initializes_when_none(self) -> None:
        db._DB_PATH = None

        # We patch build_runtime_paths to return a mock database path
        mock_database_path = Path("/mock/dir/meta.db")
        mock_paths = MagicMock()
        mock_paths.database = mock_database_path

        with patch("app.database.build_runtime_paths", return_value=mock_paths) as mock_build:
            path = db.get_db_path()

            mock_build.assert_called_once()
            self.assertEqual(path, str(mock_database_path))
            self.assertEqual(db._DB_PATH, str(mock_database_path))

    def test_get_db_path_returns_cached_value(self) -> None:
        db._DB_PATH = "/cached/path/meta.db"

        with patch("app.database.build_runtime_paths") as mock_build:
            path = db.get_db_path()

            mock_build.assert_not_called()
            self.assertEqual(path, "/cached/path/meta.db")

    def test_set_db_path_with_string(self) -> None:
        db._DB_PATH = None

        db.set_db_path("/custom/path/meta.db")

        self.assertEqual(db._DB_PATH, str(Path("/custom/path/meta.db").resolve()))

    def test_set_db_path_with_path_object(self) -> None:
        db._DB_PATH = None
        path_obj = Path("/custom/path/another_meta.db")

        db.set_db_path(path_obj)

        self.assertEqual(db._DB_PATH, str(path_obj.resolve()))
