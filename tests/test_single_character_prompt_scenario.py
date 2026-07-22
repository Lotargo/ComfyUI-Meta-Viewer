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


class SingleCharacterPromptScenarioTest(unittest.TestCase):
    def setUp(self) -> None:
        self.compiler = PromptCompiler()

    def test_all_families_compile_single_character_manifest(self) -> None:
        for family in PromptFamily:
            with self.subTest(family=family.value):
                bundle = self.compiler.compile(
                    PromptTask(
                        family=family,
                        operation=PromptOperation.GENERATE,
                        scenario=PromptScenario.SINGLE_CHARACTER,
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
                    "single_character",
                )
                self.assertIn(
                    "Exactly one primary character",
                    bundle.render(),
                )

    def test_single_character_manifest_is_distinct_from_portrait_rules(self) -> None:
        bundle = self.compiler.compile(
            PromptTask(
                family=PromptFamily.FLUX,
                operation=PromptOperation.GENERATE,
                scenario=PromptScenario.SINGLE_CHARACTER,
            )
        )

        rendered = bundle.render()
        self.assertIn("full-body silhouette", rendered)
        self.assertIn("ground contact", rendered)
        self.assertIn("unambiguous ownership", rendered)


if __name__ == "__main__":
    unittest.main()
