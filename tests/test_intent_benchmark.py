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

    def _metrics(self, result: PromptResult):
        return {
            metric.metric_id: metric
            for metric in evaluate_intent_heuristics(self.benchmark, result)
        }

    def _score(self, result: PromptResult) -> int:
        return sum(self._metrics(result)[key].points for key in self._metrics(result))

    def test_shallow_paraphrase_scores_low(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "An atmospheric portrait of an adult female ceramic artist in her workshop, "
                "natural, refined, and cozy."
            ),
            negative_prompt="",
        )
        metrics = self._metrics(result)
        self.assertLess(self._score(result), 65)
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
        metrics = tuple(evaluate_intent_heuristics(self.benchmark, result))
        self.assertGreaterEqual(sum(metric.points for metric in metrics), 95)
        self.assertTrue(all(metric.status != "fail" for metric in metrics))

    def test_cross_language_expansion_uses_visual_decisions_not_lexical_novelty(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "A close-up portrait of an adult young woman ceramicist in her sunlit workshop, her face softly "
                "illuminated by warm natural window light from the left. She has a gentle, focused expression as "
                "she gazes slightly off-camera, with fine clay dust visible on her fingers. Her dark hair is loosely "
                "gathered back, revealing natural skin texture and a serene demeanor. The background dissolves into "
                "soft bokeh showing blurred shelves of finished ceramic pieces and pottery tools, creating depth "
                "with shallow depth of field. The atmosphere feels warm, intimate, and authentic, with golden-hour "
                "light casting soft shadows across her features and the textured workshop surfaces."
            ),
            negative_prompt="",
        )
        metrics = self._metrics(result)
        expansion = metrics["non_trivial_expansion"]
        requested = metrics["requested_intent_coverage"]
        self.assertEqual(expansion.status, "pass")
        self.assertNotIn("lexical novelty", expansion.detail)
        self.assertIn("visual decision groups", expansion.detail)
        self.assertEqual(requested.status, "warn")
        self.assertIn("premium_refined", requested.detail)


class OpenCodeIntentJudgeExecutorTest(unittest.TestCase):
    def test_judge_uses_family_policy_required_intents_and_five_minute_timeout(self) -> None:
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
                user_request="Сделай уютный дорогой портрет взрослой девушки-керамиста.",
                candidate=PromptResult(
                    positive_prompt="An editorial portrait of an adult ceramic artist.",
                    negative_prompt="",
                ),
                required_intents=("natural", "premium_refined", "cozy"),
            )

        self.assertEqual(executed.result.total, 93)
        self.assertEqual(executed.latency_ms, 77)
        self.assertEqual(captured["timeout"], 300)
        self.assertEqual(
            captured["config"]["agent"]["cmv-intent-judge"]["permission"],
            {"*": "deny"},
        )
        self.assertIn("REQUIRED INTENT DIMENSIONS", captured["task"])
        self.assertIn("premium_refined", captured["task"])
        self.assertIn("empty negative_prompt is correct", captured["task"])
        self.assertIn("must not be penalized", captured["task"])
        self.assertIn("Assume it came from an unknown system", " ".join(captured["args"]))


class IntentReportTest(unittest.TestCase):
    def _judge_result(self, total_style: str = "strong") -> IntentJudgeResult:
        if total_style == "strong":
            scores = IntentJudgeScores(
                intent_fidelity=19,
                useful_visual_expansion=18,
                atmosphere_translation=14,
                composition_and_camera=9,
                lighting=9,
                environment_and_materials=9,
                coherence_and_model_fit=9,
                restraint_and_consistency=5,
            )
        else:
            scores = IntentJudgeScores(
                intent_fidelity=18,
                useful_visual_expansion=17,
                atmosphere_translation=10,
                composition_and_camera=9,
                lighting=10,
                environment_and_materials=9,
                coherence_and_model_fit=9,
                restraint_and_consistency=5,
            )
        return IntentJudgeResult(
            scores=scores,
            strengths=("Preserves intent.",),
            weaknesses=(),
            rationale="Strong result.",
        )

    def _report(self, candidate: PromptResult, judge_result: IntentJudgeResult):
        benchmark = BENCHMARKS["flux-portrait-intent-basic"]
        generation = OpenCodePromptExecutionResult(
            result=candidate,
            bundle=PromptCompiler().compile(benchmark.task),
            latency_ms=10,
            raw_response_sha256="1" * 64,
        )

        class JudgeExecution:
            result = judge_result
            latency_ms = 11
            raw_response_sha256 = "2" * 64

            @staticmethod
            def metadata():
                return {"transport": "opencode"}

        profile = {"id": "p", "model": "provider/model", "name": "OpenCode"}
        return IntentBenchmarkReport(
            benchmark=benchmark,
            generator_profile=profile,
            judge_profile=profile,
            generation=generation,
            judge=JudgeExecution(),  # type: ignore[arg-type]
            heuristic_metrics=evaluate_intent_heuristics(benchmark, candidate),
        )

    def test_same_model_judge_uses_sixty_forty_weighting(self) -> None:
        candidate = PromptResult(
            positive_prompt=(
                "An editorial portrait of an adult woman ceramic artist in a pottery studio, framed as an "
                "eye-level medium close-up. Warm window light crosses natural skin texture and a linen apron "
                "dusted with clay, while shelves, a pottery wheel, handmade bowls, and matte ceramic surfaces "
                "build an authentic workshop setting. She holds a ceramic cup with a relaxed gaze. Restrained "
                "earth tones, soft shadow, shallow depth of field, and an intimate unposed mood make the image "
                "refined, natural, and cozy."
            ),
            negative_prompt="",
        )
        report = self._report(candidate, self._judge_result())
        self.assertTrue(report.same_model_judge)
        self.assertEqual(report.score_weights, (0.60, 0.40))
        self.assertEqual(
            report.combined_score,
            round(report.heuristic_percentage * 0.60 + report.judge_score * 0.40),
        )
        self.assertEqual(intent_status(report, 80), "pass")
        serialized = report.to_dict()
        self.assertEqual(serialized["schema_version"], "2")
        self.assertEqual(serialized["scores"]["weights"]["heuristic"], 0.60)

    def test_missing_requested_mood_caps_status_at_warn(self) -> None:
        candidate = PromptResult(
            positive_prompt=(
                "A close-up portrait of an adult young woman ceramicist in her sunlit workshop, softly illuminated "
                "by warm natural window light. She has a focused expression and gazes off-camera, with clay dust on "
                "her fingers and natural skin texture. Soft bokeh reveals shelves, pottery tools, and ceramic pieces "
                "in the background. Shallow depth of field and golden-hour shadows make the atmosphere warm, intimate, "
                "and authentic."
            ),
            negative_prompt="",
        )
        report = self._report(candidate, self._judge_result("missing-premium"))
        self.assertGreaterEqual(report.combined_score, 80)
        self.assertIn("premium_refined", report.missing_required_intents)
        self.assertEqual(intent_status(report, 80), "warn")


if __name__ == "__main__":
    unittest.main()
