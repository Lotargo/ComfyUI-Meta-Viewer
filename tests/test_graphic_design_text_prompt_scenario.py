from __future__ import annotations

import unittest

from app.ai.prompting import (
    CapabilityStatus,
    PromptCompiler,
    PromptCompilerError,
    PromptFamily,
    PromptOperation,
    PromptScenario,
    PromptTask,
)


class GraphicDesignTextPromptScenarioTest(unittest.TestCase):
    def setUp(self) -> None:
        self.compiler = PromptCompiler()

    def test_family_capabilities_are_asymmetric(self) -> None:
        expected = {
            PromptFamily.FLUX: CapabilityStatus.SUPPORTED,
            PromptFamily.SDXL: CapabilityStatus.LIMITED,
        }
        for family, status in expected.items():
            with self.subTest(family=family.value):
                bundle = self.compiler.compile(
                    PromptTask(
                        family=family,
                        operation=PromptOperation.GENERATE,
                        scenario=PromptScenario.GRAPHIC_DESIGN_TEXT,
                    )
                )
                self.assertEqual(bundle.capability_status, status)
                self.assertEqual(
                    [
                        section.section_id
                        for section in bundle.sections
                        if section.kind == "scenario"
                    ],
                    ["graphic_design_text"],
                )

        with self.assertRaisesRegex(
            PromptCompilerError,
            "unsupported for family 'pony'",
        ):
            self.compiler.compile(
                PromptTask(
                    family=PromptFamily.PONY,
                    operation=PromptOperation.GENERATE,
                    scenario=PromptScenario.GRAPHIC_DESIGN_TEXT,
                )
            )

    def test_manifest_requires_exact_copy_hierarchy_and_realistic_text_budget(self) -> None:
        bundle = self.compiler.compile(
            PromptTask(
                family=PromptFamily.FLUX,
                operation=PromptOperation.GENERATE,
                scenario=PromptScenario.GRAPHIC_DESIGN_TEXT,
            )
        )

        rendered = bundle.render()
        self.assertIn("Quote every exact text block", rendered)
        self.assertIn("placement and hierarchy", rendered)
        self.assertIn("Reserve clean negative space", rendered)
        self.assertIn("one short headline", rendered)
        self.assertIn("do not claim deterministic typography", rendered)


if __name__ == "__main__":
    unittest.main()
