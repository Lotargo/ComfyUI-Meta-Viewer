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


class ProductObjectPromptScenarioTest(unittest.TestCase):
    def setUp(self) -> None:
        self.compiler = PromptCompiler()

    def test_flux_product_object_compiles_registered_manifest(self) -> None:
        bundle = self.compiler.compile(
            PromptTask(
                family=PromptFamily.FLUX,
                operation=PromptOperation.GENERATE,
                scenario=PromptScenario.PRODUCT_OBJECT,
            )
        )

        self.assertEqual(bundle.capability_status, CapabilityStatus.SUPPORTED)
        self.assertEqual(bundle.versions["scenario"], "1")
        scenario_sections = [
            section for section in bundle.sections if section.kind == "scenario"
        ]
        self.assertEqual(len(scenario_sections), 1)
        self.assertEqual(scenario_sections[0].section_id, "product_object")
        self.assertTrue(
            scenario_sections[0].source.endswith(
                "app/ai/prompting/content/scenarios/product_object.md"
            )
        )
        rendered = bundle.render()
        self.assertIn("Scenario: product_object", rendered)
        self.assertIn("readable product face", rendered)
        self.assertIn("controlled material behaviour", rendered)

    def test_pony_product_object_keeps_limited_capability_warning(self) -> None:
        bundle = self.compiler.compile(
            PromptTask(
                family=PromptFamily.PONY,
                operation=PromptOperation.GENERATE,
                scenario=PromptScenario.PRODUCT_OBJECT,
            )
        )

        self.assertEqual(bundle.capability_status, CapabilityStatus.LIMITED)
        self.assertEqual(len(bundle.warnings), 1)
        self.assertIn("limited support", bundle.warnings[0])
        self.assertIn("Scenario: product_object", bundle.render())


if __name__ == "__main__":
    unittest.main()
