from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ai.cli import CommandResult
from app.ai.execution import (
    OpenCodeIntentJudgeExecutor,
    OpenCodePromptExecutionResult,
)
from app.ai.intent_benchmark import (
    BENCHMARKS,
    IntentBenchmarkReport,
    evaluate_intent_heuristics,
    intent_status,
)
from app.ai.judging import (
    IntentJudgeResult,
    IntentJudgeScores,
    parse_intent_judge_result,
)
from app.ai.prompting import PromptCompiler, PromptResult


class IntentJudgeContractTest(unittest.TestCase):
    def test_scores_total_exactly_matches_rubric_sum(self) -> None:
        scores = IntentJudgeScores(
            intent_fidelity=18,
            useful_visual_expansion=17,
            atmosphere_translation=13,
            composition_and_camera=9,
            lighting=8,
            environment_and_materials=9,
            coherence_and_model_fit=9,
            restraint_and_consistency=5,
        )
        self.assertEqual(scores.total, 88)

    def test_strict_judge_json_is_parsed(self) -> None:
        parsed = parse_intent_judge_result(json.dumps({
            "schema_version": "1",
            "scores": {
                "intent_fidelity": 20,
                "useful_visual_expansion": 18,
                "atmosphere_translation": 14,
                "composition_and_camera": 9,
                "lighting": 9,
                "environment_and_materials": 9,
                "coherence_and_model_fit": 9,
                "restraint_and_consistency": 5,
            },
            "strengths": ["Preserves the core request."],
            "weaknesses": ["Could be slightly more concise."],
            "rationale": "The candidate expands the short request into a coherent visual plan.",
        }))
        self.assertEqual(parsed.total, 93)
        self.assertEqual(parsed.verdict, "pass")


class IntentHeuristicTest(unittest.TestCase):
    def setUp(self) -> None:
        self.benchmark = BENCHMARKS["flux-portrait-intent-basic"]

    def _score(self, result: PromptResult) -> int:
        return sum(
            metric.points
            for metric in evaluate_intent_heuristics(self.benchmark, result)
        )

    def test_shallow_paraphrase_scores_low(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "An atmospheric portrait of an adult female ceramic artist in her workshop, "
                "natural, refined, and cozy."
            ),
            negative_prompt="",
        )
        metrics = {
            metric.metric_id: metric
            for metric in evaluate_intent_heuristics(self.benchmark, result)
        }
        self.assertLess(self._score(result), 60)
        self.assertEqual(metrics["non_trivial_expansion"].status, "fail")
        self.assertEqual(metrics["invented_camera_language"].status, "fail")
        self.assertEqual(metrics["invented_lighting"].status, "fail")

    def test_independent_visual_expansion_scores_high(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "An intimate editorial portrait of an adult woman ceramic artist in a working pottery studio, "
                "framed as an eye-level medium close-up with a calm, relaxed expression. Soft warm window light "
                "shapes one side of her face while gentle shadow preserves depth and a faint rim separates her "
                "from shelves of handmade bowls, clay tools, and a pottery wheel. She wears a charcoal linen apron "
                "dusted with pale clay and holds a matte ceramic cup, revealing natural skin texture, fabric weave, "
                "and handmade surfaces. Restrained earth tones, shallow depth of field, and an authentic unposed "
                "editorial finish make the workshop feel refined, inviting, and quietly cozy."
            ),
            negative_prompt="",
        )
        metrics = evaluate_intent_heuristics(self.benchmark, result)
        self.assertGreaterEqual(sum(metric.points for metric in metrics), 90)
        self.assertTrue(all(metric.status != "fail" for metric in metrics))


class OpenCodeIntentJudgeExecutorTest(unittest.TestCase):
    def test_judge_uses_isolated_tool_denied_agent_and_five_minute_timeout(self) -> None:
        raw_result = json.dumps({
            "schema_version": "1",
            "scores": {
                "intent_fidelity": 20,
                "useful_visual_expansion": 18,
                "atmosphere_translation": 14,
                "composition_and_camera": 9,
                "lighting": 9,
                "environment_and_materials": 9,
                "coherence_and_model_fit": 9,
                "restraint_and_consistency": 5,
            },
            "strengths": ["Strong visual expansion."],
            "weaknesses": [],
            "rationale": "The prompt preserves intent and adds useful visual decisions.",
        })
        event_output = json.dumps({"part": {"text": raw_result}})
        captured: dict = {}

        def fake_run_command(args, *, timeout, cwd=None):
            workspace = Path(cwd)
            captured["args"] = list(args)
            captured["timeout"] = timeout
            captured["config"] = json.loads(
                (workspace / "opencode.json").read_text(encoding="utf-8")
            )
            captured["task"] = (workspace / "cmv-judge-task.md").read_text(
                encoding="utf-8"
            )
            return CommandResult(
                returncode=0,
                stdout=event_output,
                stderr="",
                elapsed_ms=77,
            )

        profile = {
            "id": "same-model",
            "kind": "cli",
            "name": "OpenCode",
            "model": "provider/model",
            "timeout_seconds": 60,
            "multimodal": False,
            "cli_type": "opencode",
            "executable": "C:/tools/opencode.cmd",
        }
        with (
            patch(
                "app.ai.execution.opencode_judge.find_executable",
                return_value="C:/tools/opencode.cmd",
            ),
            patch(
                "app.ai.execution.opencode_judge.run_command",
                side_effect=fake_run_command,
            ),
        ):
            executed = OpenCodeIntentJudgeExecutor().execute(
                profile=profile,
                family="flux",
                user_request="Сделай уютный портрет взрослой девушки-керамиста.",
                candidate=PromptResult(
                    positive_prompt="An editorial portrait of an adult ceramic artist.",
                    negative_prompt="",
                ),
            )

        self.assertEqual(executed.result.total, 93)
        self.assertEqual(executed.latency_ms, 77)
        self.assertEqual(captured["timeout"], 300)
        self.assertEqual(
            captured["config"]["agent"]["cmv-intent-judge"]["permission"],
            {"*": "deny"},
        )
        self.assertIn("ORIGINAL HUMAN REQUEST", captured["task"])
        self.assertIn("CANDIDATE POSITIVE PROMPT", captured["task"])
        self.assertIn("Assume it came from an unknown system", " ".join(captured["args"]))


class IntentReportTest(unittest.TestCase):
    def test_same_model_judge_is_disclosed_and_scores_are_combined(self) -> None:
        benchmark = BENCHMARKS["flux-portrait-intent-basic"]
        bundle = PromptCompiler().compile(benchmark.task)
        candidate = PromptResult(
            positive_prompt=(
                "An editorial portrait of an adult woman ceramic artist in a pottery studio, framed as an "
                "eye-level medium close-up. Warm window light crosses natural skin texture and a linen apron "
                "dusted with clay, while shelves, a pottery wheel, handmade bowls, and matte ceramic surfaces "
                "build an authentic workshop setting. Restrained earth tones, soft shadow, shallow depth of "
                "field, and an intimate unposed mood make the image refined, natural, and cozy."
            ),
            negative_prompt="",
        )
        generation = OpenCodePromptExecutionResult(
            result=candidate,
            bundle=bundle,
            latency_ms=10,
            raw_response_sha256="1" * 64,
        )
        judge_result = IntentJudgeResult(
            scores=IntentJudgeScores(
                intent_fidelity=19,
                useful_visual_expansion=18,
                atmosphere_translation=14,
                composition_and_camera=9,
                lighting=9,
                environment_and_materials=9,
                coherence_and_model_fit=9,
                restraint_and_consistency=5,
            ),
            strengths=("Preserves intent.",),
            weaknesses=(),
            rationale="Strong result.",
        )

        class JudgeExecution:
            result = judge_result
            latency_ms = 11
            raw_response_sha256 = "2" * 64

            @staticmethod
            def metadata():
                return {"transport": "opencode"}

        profile = {"id": "p", "model": "provider/model", "name": "OpenCode"}
        report = IntentBenchmarkReport(
            benchmark=benchmark,
            generator_profile=profile,
            judge_profile=profile,
            generation=generation,
            judge=JudgeExecution(),  # type: ignore[arg-type]
            heuristic_metrics=evaluate_intent_heuristics(benchmark, candidate),
        )
        self.assertTrue(report.same_model_judge)
        self.assertEqual(
            report.combined_score,
            round((report.heuristic_percentage + report.judge_score) / 2),
        )
        self.assertEqual(intent_status(report, 80), "pass")
        self.assertTrue(report.to_dict()["profiles"]["same_model_judge"])


if __name__ == "__main__":
    unittest.main()
