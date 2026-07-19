from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.ai.prompting import (
    CapabilityStatus,
    PromptCompiler,
    PromptCompilerError,
    PromptContractError,
    PromptFamily,
    PromptModifier,
    PromptOperation,
    PromptResult,
    PromptScenario,
    PromptTask,
    SceneComposition,
    SceneSpec,
    SceneSubject,
    VisibleText,
    parse_prompt_result,
    parse_scene_spec,
)


class PromptCompilerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.compiler = PromptCompiler()

    def test_compile_flux_portrait_is_deterministic(self) -> None:
        task = PromptTask(
            family=PromptFamily.FLUX,
            operation=PromptOperation.GENERATE,
            scenario=PromptScenario.PORTRAIT,
            modifiers=(PromptModifier.SAFE,),
        )

        first = self.compiler.compile(task)
        second = self.compiler.compile(task)

        self.assertEqual(first, second)
        self.assertEqual(first.render(), second.render())
        self.assertEqual(first.capability_status, CapabilityStatus.SUPPORTED)
        self.assertEqual(
            [section.kind for section in first.sections],
            [
                "family_base",
                "operation",
                "scenario",
                "modifier",
                "output_contract",
            ],
        )
        self.assertEqual(first.versions["family"], "legacy-1")
        self.assertEqual(first.versions["operation"], "1")
        self.assertEqual(first.versions["scenario"], "1")
        self.assertEqual(first.versions["modifier:safe"], "1")
        self.assertIn("INSTRUCTION PRECEDENCE", first.render())
        self.assertIn("Output contract and hard content boundaries", first.render())
        self.assertIn('"schema_version": "1"', first.render())

    def test_limited_sdxl_graphic_design_adds_warning(self) -> None:
        bundle = self.compiler.compile(PromptTask(
            family=PromptFamily.SDXL,
            operation=PromptOperation.RECONSTRUCT,
            scenario=PromptScenario.GRAPHIC_DESIGN_TEXT,
        ))

        self.assertEqual(bundle.capability_status, CapabilityStatus.LIMITED)
        self.assertEqual(len(bundle.warnings), 1)
        self.assertIn("limited support", bundle.warnings[0])
        self.assertIn("booklet covers", bundle.render())

    def test_unsupported_pony_graphic_design_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            PromptCompilerError,
            "unsupported for family 'pony'",
        ):
            self.compiler.compile(PromptTask(
                family=PromptFamily.PONY,
                operation=PromptOperation.GENERATE,
                scenario=PromptScenario.GRAPHIC_DESIGN_TEXT,
            ))

    def test_multi_character_requires_tested_checkpoint_override(self) -> None:
        with self.assertRaisesRegex(
            PromptCompilerError,
            "requires an explicit tested checkpoint capability profile",
        ):
            self.compiler.compile(PromptTask(
                family=PromptFamily.FLUX,
                operation=PromptOperation.GENERATE,
                scenario=PromptScenario.MULTI_CHARACTER,
                checkpoint_profile="z-image-unverified",
            ))

    def test_unmigrated_supported_scenario_fails_explicitly(self) -> None:
        with self.assertRaisesRegex(
            PromptCompilerError,
            "has not been migrated yet",
        ):
            self.compiler.compile(PromptTask(
                family=PromptFamily.FLUX,
                operation=PromptOperation.GENERATE,
                scenario=PromptScenario.SINGLE_CHARACTER,
            ))

    def test_safe_and_adult_only_are_mutually_exclusive(self) -> None:
        with self.assertRaises(ValidationError):
            PromptTask(
                family=PromptFamily.SDXL,
                operation=PromptOperation.GENERATE,
                scenario=PromptScenario.PORTRAIT,
                modifiers=(PromptModifier.SAFE, PromptModifier.ADULT_ONLY),
            )

    def test_scene_spec_is_strict_and_serializable(self) -> None:
        spec = SceneSpec(
            recommended_scenario=PromptScenario.GRAPHIC_DESIGN_TEXT,
            subjects=(SceneSubject(
                kind="perfume bottle",
                position="center",
                attributes={"material": "clear glass"},
                confidence=0.97,
            ),),
            composition=SceneComposition(
                shot="close-up product shot",
                camera_angle="slightly low",
                background="warm beige gradient",
            ),
            visible_text=(VisibleText(
                text="LUMIERE",
                placement="front label",
                confidence=0.96,
            ),),
            uncertain_details=("  small footer text  ", ""),
        )

        payload = spec.model_dump(mode="json")
        self.assertEqual(payload["schema_version"], "1")
        self.assertEqual(payload["recommended_scenario"], "graphic_design_text")
        self.assertEqual(payload["uncertain_details"], ["small footer text"])

        with self.assertRaises(ValidationError):
            SceneSpec(unknown_field=True)

    def test_prompt_result_rejects_extra_keys_and_strips_prompts(self) -> None:
        result = PromptResult(
            positive_prompt="  a glass bottle on a beige background  ",
            negative_prompt="  watermark  ",
        )
        self.assertEqual(
            result.positive_prompt,
            "a glass bottle on a beige background",
        )
        self.assertEqual(result.negative_prompt, "watermark")

        with self.assertRaises(ValidationError):
            PromptResult(positive_prompt="   ")

        with self.assertRaises(ValidationError):
            PromptResult(
                positive_prompt="valid",
                negative_prompt="",
                commentary="not allowed",
            )

    def test_parse_prompt_result_uses_one_strict_contract(self) -> None:
        result = parse_prompt_result(
            '{"schema_version":"1","positive_prompt":"portrait",'
            '"negative_prompt":"watermark"}'
        )
        self.assertEqual(result.positive_prompt, "portrait")

        with self.assertRaises(PromptContractError) as markdown_error:
            parse_prompt_result(
                '```json\n{"schema_version":"1",'
                '"positive_prompt":"portrait","negative_prompt":""}\n```'
            )
        self.assertEqual(markdown_error.exception.code, "markdown_wrapped_json")

        with self.assertRaises(PromptContractError) as version_error:
            parse_prompt_result(
                '{"schema_version":"2","positive_prompt":"portrait",'
                '"negative_prompt":""}'
            )
        self.assertEqual(version_error.exception.code, "contract_validation_error")

    def test_parse_scene_spec_rejects_non_object_json(self) -> None:
        with self.assertRaises(PromptContractError) as error:
            parse_scene_spec("[]")
        self.assertEqual(error.exception.code, "invalid_contract_shape")


if __name__ == "__main__":
    unittest.main()
