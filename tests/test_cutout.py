from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.cutout import clear_cutout, get_cutout_path


class CutoutTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cutout_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_get_cutout_path(self) -> None:
        # Test get_cutout_path with Path directory
        path = get_cutout_path(self.cutout_dir, 42)
        self.assertEqual(path, self.cutout_dir / "42.png")

        # Test get_cutout_path with str directory
        path_str = get_cutout_path(str(self.cutout_dir), 100)
        self.assertEqual(path_str, self.cutout_dir / "100.png")

    def test_clear_cutout_not_exist(self) -> None:
        # If the file does not exist, it should return False
        result = clear_cutout(self.cutout_dir, 42)
        self.assertFalse(result)

    def test_clear_cutout_exist_path_dir(self) -> None:
        # Create a dummy cutout file
        cutout_file = self.cutout_dir / "42.png"
        cutout_file.write_bytes(b"dummy image data")
        self.assertTrue(cutout_file.exists())

        # If the file exists, clear_cutout should delete it and return True
        result = clear_cutout(self.cutout_dir, 42)
        self.assertTrue(result)
        self.assertFalse(cutout_file.exists())

    def test_clear_cutout_exist_str_dir(self) -> None:
        # Create a dummy cutout file
        cutout_file = self.cutout_dir / "100.png"
        cutout_file.write_bytes(b"dummy image data")
        self.assertTrue(cutout_file.exists())

        # Test with string directory path
        result = clear_cutout(str(self.cutout_dir), 100)
        self.assertTrue(result)
        self.assertFalse(cutout_file.exists())


if __name__ == "__main__":
    unittest.main()
