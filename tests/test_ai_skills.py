"""Tests for the AI skills loader and researched family distinctions."""
from __future__ import annotations

import unittest

from app.ai.skills import load_skill


class AISkillsTest(unittest.TestCase):
    """Verify that load_skill returns complete, family-specific instructions."""

    def test_load_flux(self) -> None:
        text = load_skill("flux")

        self.assertIn("Flux", text)
        self.assertIn("STEP 1", text)
        self.assertIn("STEP 2", text)
        self.assertIn("COMMON MISTAKES", text)
        self.assertIn("SELF-CHECK", text)
        self.assertIn("positive_prompt", text)

        # FLUX / Chroma keep the negative prompt empty by default.
        self.assertIn('negative_prompt": ""', text)

        # Z-Image must not inherit FLUX runtime rules unconditionally.
        self.assertIn("full Z-Image", text)
        self.assertIn("Z-Image-Turbo", text)
        self.assertIn("TARGET DEPENDENT", text)
        self.assertIn("A concise, targeted negative prompt MAY be used", text)

        # Numeric prompt-length guidance is explicitly a project heuristic.
        self.assertIn("PROJECT HEURISTIC", text)
        self.assertIn("not a hard model limit", text)

    def test_load_sdxl(self) -> None:
        text = load_skill("sdxl")

        self.assertIn("SDXL", text)
        self.assertIn("SCENE GRAPH", text)
        self.assertIn("LAYER 1", text)
        self.assertIn("LAYER 2", text)
        self.assertIn("LAYER 3", text)
        self.assertIn("SURGICAL", text)
        self.assertIn("COMMON MISTAKES", text)
        self.assertIn("SELF-CHECK", text)
        self.assertIn("positive_prompt", text)
        self.assertIn("negative_prompt", text)

        # The layered writing method is not presented as encoder architecture.
        self.assertIn("PROJECT METHOD", text)
        self.assertIn("not as a claim about SDXL inference stages", text)

        # Negative length is a project default, not a universal model rule.
        self.assertIn("not an SDXL architecture limit", text)
        self.assertIn("checkpoint-aware", text)

    def test_load_pony(self) -> None:
        text = load_skill("pony")

        self.assertIn("Pony", text)
        self.assertIn("Danbooru", text)
        self.assertIn("source_anime", text)
        self.assertIn("rating_safe", text)
        self.assertIn("COMMON MISTAKES", text)
        self.assertIn("SELF-CHECK", text)

        # Base Pony V6 XL uses the complete author-recommended score prefix.
        self.assertIn(
            "score_9, score_8_up, score_7_up, score_6_up, "
            "score_5_up, score_4_up",
            text,
        )

        # Pony supports captions and tags; tag-only is not treated as fact.
        self.assertIn("natural-language captions", text)
        self.assertIn("It is NOT a tag-only model", text)
        self.assertIn("deterministic hybrid structure", text)

        # Base Pony normally starts without a negative prompt.
        self.assertIn('negative_prompt": ""', text)
        self.assertIn("without a negative prompt in most cases", text)

        # Clip Skip belongs to runtime configuration, not generated prompt text.
        self.assertIn("Clip Skip 2", text)
        self.assertIn("runtime configuration", text)

    def test_invalid_family(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_skill("nonexistent_family")


if __name__ == "__main__":
    unittest.main()
