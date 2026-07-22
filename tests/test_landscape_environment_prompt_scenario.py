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


class LandscapeEnvironmentPromptScenarioTest(unittest.TestCase):
    def setUp(self) -> None:
        self.compiler = PromptCompiler()

    def test_all_families_compile_supported_manifest(self) -> None:
        for family in PromptFamily:
            with self.subTest(family=family.value):
                bundle = self.compiler.compile(
                    PromptTask(
                        family=family,
                        operation=PromptOperation.GENERATE,
                        scenario=PromptScenario.LANDSCAPE_ENVIRONMENT,
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
                    "landscape_environment",
                )
                self.assertIn("Keep geography coherent", bundle.render())

    def test_manifest_requires_depth_water_and_scale_consistency(self) -> None:
        bundle = self.compiler.compile(
            PromptTask(
                family=PromptFamily.FLUX,
                operation=PromptOperation.GENERATE,
                scenario=PromptScenario.LANDSCAPE_ENVIRONMENT,
            )
        )

        rendered = bundle.render()
        self.assertIn("foreground, middle ground, and background", rendered)
        self.assertIn("Water follows terrain", rendered)
        self.assertIn("clear scale system", rendered)


if __name__ == "__main__":
    unittest.main()
