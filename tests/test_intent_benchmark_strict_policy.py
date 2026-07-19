from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.ai.execution import OpenCodeIntentJudgeExecutor
from app.ai.intent_benchmark import (
    BENCHMARKS,
    evaluate_intent_heuristics,
    intent_status,
)
from app.ai.prompting import PromptResult


class StrictIntentStatusTest(unittest.TestCase):
    def _report(
        self,
        candidate: PromptResult,
        *,
        combined_score: int,
        score_gap: int = 0,
    ) -> SimpleNamespace:
        benchmark = BENCHMARKS["flux-product-intent-basic"]
        return SimpleNamespace(
            benchmark=benchmark,
            heuristic_metrics=evaluate_intent_heuristics(benchmark, candidate),
            combined_score=combined_score,
            score_gap=score_gap,
            missing_required_intents=(),
        )

    def test_uploaded_product_result_is_warn_not_clean_pass(self) -> None:
        candidate = PromptResult(
            positive_prompt=(
                "A luxurious perfume bottle with a sleek glass silhouette, filled with a golden amber liquid, "
                "positioned upright on a smooth marble surface. The bottle features a polished metallic cap and "
                "subtle embossed branding on its front. Soft, warm studio lighting enters from the upper left, "
                "creating gentle highlights on the glass curves and a soft shadow beneath, with a clean gradient "
                "background in neutral tones. Shot with a shallow depth of field to emphasize the bottle's details, "
                "conveying a premium and inviting aesthetic."
            ),
            negative_prompt="",
        )
        report = self._report(candidate, combined_score=85, score_gap=2)
        metrics = {item.metric_id: item for item in report.heuristic_metrics}

        self.assertEqual(metrics["core_intent"].status, "warn")
        self.assertEqual(metrics["invented_camera_language"].status, "fail")
        self.assertEqual(intent_status(report, 80), "warn")

    def test_complete_product_result_can_cleanly_pass(self) -> None:
        candidate = PromptResult(
            positive_prompt=(
                "A centered close-up commercial product photograph of a luxury perfume bottle, presented upright "
                "in a precise three-quarter view with the blank front label area clearly visible. Warm studio key "
                "light and a restrained rim create controlled highlights along the transparent glass edges, golden "
                "amber liquid, and polished metal cap. The bottle rests on a warm beige stone plinth with a grounded "
                "contact shadow against a clean seamless gradient background and deliberate negative space. Crisp "
                "packshot art direction, minimal reflections, and refined material separation keep the image premium, "
                "clean, and gently warm without invented brand text."
            ),
            negative_prompt="",
        )
        report = self._report(candidate, combined_score=91, score_gap=5)
        metrics = {item.metric_id: item for item in report.heuristic_metrics}

        self.assertEqual(metrics["core_intent"].status, "pass")
        self.assertEqual(metrics["invented_camera_language"].status, "pass")
        self.assertEqual(intent_status(report, 80), "pass")


class ProductJudgePolicyTest(unittest.TestCase):
    def test_product_policy_requires_real_camera_strategy_and_no_fabricated_text(self) -> None:
        package = OpenCodeIntentJudgeExecutor._render_judge_package(
            family="flux",
            user_request="Сделай рекламную фотографию флакона духов: дорого, чисто и тепло.",
            candidate=PromptResult(
                positive_prompt="A glass perfume bottle with shallow depth of field.",
                negative_prompt="",
            ),
            required_intents=("premium_refined", "clean_minimal", "warm"),
        )

        self.assertIn("PRODUCT-OBJECT BENCHMARK POLICY", package)
        self.assertIn("Shallow depth of field alone is not", package)
        self.assertIn("advertising, commercial, packshot, or product-photography", package)
        self.assertIn("invented readable branding", package)

    def test_portrait_judge_package_does_not_receive_product_policy(self) -> None:
        package = OpenCodeIntentJudgeExecutor._render_judge_package(
            family="flux",
            user_request="Сделай уютный портрет девушки-керамиста.",
            candidate=PromptResult(
                positive_prompt="An intimate portrait of an adult ceramic artist.",
                negative_prompt="",
            ),
            required_intents=("natural", "premium_refined", "cozy"),
        )

        self.assertNotIn("PRODUCT-OBJECT BENCHMARK POLICY", package)


if __name__ == "__main__":
    unittest.main()
