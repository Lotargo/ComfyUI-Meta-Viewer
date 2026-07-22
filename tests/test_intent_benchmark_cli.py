from __future__ import annotations

import tempfile
import unittest
from collections import Counter
from pathlib import Path

from app.ai.intent_benchmark_core import (
    BENCHMARKS,
    _interactive_selection,
    build_parser,
    evaluate_intent_heuristics,
)
from app.ai.execution import OpenCodeIntentJudgeExecutor
from app.ai.profiles import AIProfileStore
from app.ai.prompting import PromptCompiler, PromptFamily, PromptResult, PromptScenario
from app.ai.secrets import SecretStoreStatus


class MemorySecretStore:
    def __init__(self):
        self.values: dict[str, str] = {}

    def status(self) -> SecretStoreStatus:
        return SecretStoreStatus(True, "tests.MemorySecretStore", "Test store")

    def get(self, profile_id: str) -> str | None:
        return self.values.get(profile_id)

    def set(self, profile_id: str, value: str) -> None:
        self.values[profile_id] = value

    def delete(self, profile_id: str) -> None:
        self.values.pop(profile_id, None)


class FakeConsole:
    def __init__(self, responses: list[str]):
        self.responses = iter(responses)
        self.output: list[str] = []

    def print(self, value: object = "") -> None:
        self.output.append(str(value))

    def input(self, prompt: str = "") -> str:
        self.output.append(prompt)
        return next(self.responses)


class IntentBenchmarkCatalogTest(unittest.TestCase):
    def test_family_adaptations_are_independent_runnable_benchmarks(self) -> None:
        counts = Counter(
            benchmark.task.family for benchmark in BENCHMARKS.values()
        )
        self.assertEqual(counts[PromptFamily.FLUX], 7)
        self.assertEqual(counts[PromptFamily.SDXL], 7)
        self.assertEqual(counts[PromptFamily.PONY], 6)

        flux = BENCHMARKS["flux-portrait-intent-basic"]
        sdxl = BENCHMARKS["sdxl-portrait-intent-basic"]
        pony = BENCHMARKS["pony-portrait-intent-basic"]
        self.assertEqual(flux.input_text, sdxl.input_text)
        self.assertEqual(flux.input_text, pony.input_text)
        self.assertIs(flux.task.family, PromptFamily.FLUX)
        self.assertIs(sdxl.task.family, PromptFamily.SDXL)
        self.assertIs(pony.task.family, PromptFamily.PONY)
        self.assertNotIn("pony-graphic-design-text-intent-basic", BENCHMARKS)

    def test_every_registered_adaptation_compiles_on_its_own(self) -> None:
        compiler = PromptCompiler()
        for benchmark in BENCHMARKS.values():
            with self.subTest(benchmark=benchmark.benchmark_id):
                bundle = compiler.compile(benchmark.task)
                self.assertIs(bundle.task.family, benchmark.task.family)
                self.assertIs(bundle.task.scenario, benchmark.task.scenario)

    def test_judge_policy_uses_selected_family_conventions(self) -> None:
        sdxl = OpenCodeIntentJudgeExecutor._family_policy("sdxl")
        pony = OpenCodeIntentJudgeExecutor._family_policy("pony")
        self.assertIn("targeted negative prompt is allowed", sdxl)
        self.assertIn("score_9 through score_4_up", pony)
        self.assertIn("rating_safe", pony)

    def test_pony_adaptation_enforces_base_family_controls(self) -> None:
        benchmark = BENCHMARKS["pony-portrait-intent-basic"]
        missing = evaluate_intent_heuristics(
            benchmark,
            PromptResult(positive_prompt="An adult ceramic artist portrait."),
        )
        missing_policy = next(
            metric for metric in missing if metric.metric_id == "family_prompt_policy"
        )
        self.assertEqual(missing_policy.status, "fail")
        self.assertIn("score_9", missing_policy.detail)
        self.assertIn("source_*", missing_policy.detail)
        self.assertIn("rating_safe", missing_policy.detail)

        valid = evaluate_intent_heuristics(
            benchmark,
            PromptResult(
                positive_prompt=(
                    "score_9, score_8_up, score_7_up, score_6_up, score_5_up, "
                    "score_4_up, source_anime, rating_safe, adult ceramic artist portrait"
                )
            ),
        )
        valid_policy = next(
            metric for metric in valid if metric.metric_id == "family_prompt_policy"
        )
        self.assertEqual(valid_policy.status, "pass")


class IntentBenchmarkInteractiveSelectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.store = AIProfileStore(
            Path(self.temp_dir.name) / "config.json",
            secret_store=MemorySecretStore(),
        )
        self.profile = self.store.create(
            {
                "kind": "cli",
                "name": "OpenCode Test",
                "model": "opencode/mimo-v2.5-free",
                "timeout_seconds": 300,
                "multimodal": False,
                "cli_type": "opencode",
                "executable": "C:/tools/opencode.cmd",
            }
        )
        self.store.set_defaults({"text_profile_id": self.profile["id"]})

    def test_selects_one_sdxl_scenario_without_creating_a_comparison(self) -> None:
        console = FakeConsole([
            "2",  # SDXL
            "",   # generate
            "6",  # graphic_design_text
            "",   # default generator
            "",   # same-model judge
            "",   # default report path
        ])

        selection = _interactive_selection(console, self.store)

        self.assertIsNotNone(selection)
        assert selection is not None
        self.assertEqual(
            selection.benchmark_id,
            "sdxl-graphic-design-text-intent-basic",
        )
        self.assertEqual(selection.generator_profile, self.profile["id"])
        self.assertIsNone(selection.judge_profile)
        self.assertEqual(
            selection.json_out,
            "reports/sdxl-graphic-design-text-intent-basic.json",
        )

    def test_pony_menu_excludes_unsupported_graphic_text(self) -> None:
        console = FakeConsole([
            "3",  # Pony
            "",   # generate
            "q",  # cancel at scenario selection
        ])

        selection = _interactive_selection(console, self.store)

        self.assertIsNone(selection)
        rendered = "\n".join(console.output)
        self.assertIn(PromptScenario.PORTRAIT.value, rendered)
        self.assertNotIn(PromptScenario.GRAPHIC_DESIGN_TEXT.value, rendered)

    def test_no_subcommand_selects_interactive_mode_in_main(self) -> None:
        args = build_parser().parse_args([])
        self.assertIsNone(args.command)


if __name__ == "__main__":
    unittest.main()
