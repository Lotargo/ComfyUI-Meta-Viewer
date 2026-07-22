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


class ArchitectureInteriorPromptScenarioTest(unittest.TestCase):
    def setUp(self) -> None:
        self.compiler = PromptCompiler()

    def test_flux_and_sdxl_compile_supported_manifest(self) -> None:
        for family in (PromptFamily.FLUX, PromptFamily.SDXL):
            with self.subTest(family=family.value):
                bundle = self.compiler.compile(
                    PromptTask(
                        family=family,
                        operation=PromptOperation.GENERATE,
                        scenario=PromptScenario.ARCHITECTURE_INTERIOR,
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
                    "architecture_interior",
                )
                self.assertIn("Keep perspective coherent", bundle.render())

    def test_pony_compiles_with_limited_capability_warning(self) -> None:
        bundle = self.compiler.compile(
            PromptTask(
                family=PromptFamily.PONY,
                operation=PromptOperation.GENERATE,
                scenario=PromptScenario.ARCHITECTURE_INTERIOR,
            )
        )

        self.assertEqual(bundle.capability_status, CapabilityStatus.LIMITED)
        self.assertEqual(len(bundle.warnings), 1)
        self.assertIn("limited support", bundle.warnings[0])
        self.assertIn("believable scale", bundle.render())


if __name__ == "__main__":
    unittest.main()
