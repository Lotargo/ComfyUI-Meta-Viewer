"""Tests for the AI skills loader."""
from __future__ import annotations

import unittest

from app.ai.skills import load_skill


class AISkillsTest(unittest.TestCase):
    """Verify that load_skill returns the full text for each family."""

    def test_load_flux(self) -> None:
        text = load_skill("flux")
        # Core structural markers
        self.assertIn("Flux", text)
        self.assertIn("STEP 1", text)
        self.assertIn("STEP 2", text)
        self.assertIn("COMMON MISTAKES", text)
        self.assertIn("SELF-CHECK", text)
        self.assertIn("positive_prompt", text)
        # Flux-specific: no negative prompt
        self.assertIn('negative_prompt": ""', text)

    def test_load_sdxl(self) -> None:
        text = load_skill("sdxl")
        self.assertIn("SDXL", text)
        self.assertIn("SCENE GRAPH", text)
        self.assertIn("LAYER 1", text)
        self.assertIn("SURGICAL", text)
        self.assertIn("COMMON MISTAKES", text)
        self.assertIn("SELF-CHECK", text)
        self.assertIn("positive_prompt", text)
        self.assertIn("negative_prompt", text)

    def test_load_pony(self) -> None:
        text = load_skill("pony")
        self.assertIn("Pony", text)
        self.assertIn("score_9", text)
        self.assertIn("source_anime", text)
        self.assertIn("rating_safe", text)
        self.assertIn("Danbooru", text)
        self.assertIn("COMMON MISTAKES", text)
        self.assertIn("SELF-CHECK", text)

    def test_invalid_family(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_skill("nonexistent_family")


if __name__ == "__main__":
    unittest.main()
