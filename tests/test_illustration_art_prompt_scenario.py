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


class IllustrationArtPromptScenarioTest(unittest.TestCase):
    def setUp(self) -> None:
        self.compiler = PromptCompiler()

    def test_all_families_compile_supported_manifest(self) -> None:
        for family in PromptFamily:
            with self.subTest(family=family.value):
                bundle = self.compiler.compile(
                    PromptTask(
                        family=family,
                        operation=PromptOperation.GENERATE,
                        scenario=PromptScenario.ILLUSTRATION_ART,
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
                    "illustration_art",
                )
                self.assertIn("Choose a coherent medium", bundle.render())

    def test_manifest_requires_story_hierarchy_and_visible_mood_evidence(self) -> None:
        bundle = self.compiler.compile(
            PromptTask(
                family=PromptFamily.FLUX,
                operation=PromptOperation.GENERATE,
                scenario=PromptScenario.ILLUSTRATION_ART,
            )
        )

        rendered = bundle.render()
        self.assertIn("narrative moment", rendered)
        self.assertIn("readable focal hierarchy", rendered)
        self.assertIn("separately traceable", rendered)
        self.assertIn("its own visible design evidence", rendered)


if __name__ == "__main__":
    unittest.main()
