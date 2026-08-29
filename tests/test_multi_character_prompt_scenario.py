from __future__ import annotations

import unittest

from app.ai.prompting import (
    CapabilityStatus,
    PromptCompiler,
    PromptFamily,
    PromptOperation,
    PromptScenario,
    PromptTask,
)


class MultiCharacterPromptScenarioTest(unittest.TestCase):
    def setUp(self) -> None:
        self.compiler = PromptCompiler()

    def test_all_families_compile_multi_character_manifest(self) -> None:
        for family in PromptFamily:
            with self.subTest(family=family.value):
                bundle = self.compiler.compile(
                    PromptTask(
                        family=family,
                        operation=PromptOperation.GENERATE,
                        scenario=PromptScenario.MULTI_CHARACTER,
                    )
                )

                self.assertEqual(
                    bundle.capability_status,
                    CapabilityStatus.SUPPORTED,
                )
                scenario_sections = [
                    section
                    for section in bundle.sections
                    if section.kind == "scenario"
                ]
                self.assertEqual(len(scenario_sections), 1)
                self.assertEqual(
                    scenario_sections[0].section_id,
                    "multi_character",
                )
                rendered = bundle.render()
                self.assertIn("Scenario: multi_character", rendered)
                self.assertIn("SPATIAL ANCHORING", rendered)
                self.assertIn("ANTI-CLONING", rendered)

    def test_multi_character_manifest_defines_spatial_and_cloning_rules(self) -> None:
        bundle = self.compiler.compile(
            PromptTask(
                family=PromptFamily.FLUX,
                operation=PromptOperation.GENERATE,
                scenario=PromptScenario.MULTI_CHARACTER,
            )
        )

        rendered = bundle.render()
        self.assertIn("On the left", rendered)
        self.assertIn("On the right", rendered)
        self.assertIn("SMALL GROUP (2–5", rendered)
        self.assertIn("LARGE GROUP / CROWD (6+", rendered)
        self.assertIn("TWINS EXCEPTION", rendered)
        self.assertIn("sequential complete character blocks", rendered.lower())


if __name__ == "__main__":
    unittest.main()
