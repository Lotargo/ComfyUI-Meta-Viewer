from __future__ import annotations

import unittest

from app.ai.prompting import PromptResult
from app.ai.quality_benchmark import (
    BENCHMARKS,
    evaluate_prompt_quality,
)


class PromptQualityBenchmarkTest(unittest.TestCase):
    def setUp(self) -> None:
        self.benchmark = BENCHMARKS["flux-portrait-detailed"]

    def _percentage(self, result: PromptResult) -> int:
        metrics = evaluate_prompt_quality(self.benchmark, result)
        score = sum(metric.points for metric in metrics)
        maximum = sum(metric.maximum for metric in metrics)
        return round(score * 100 / maximum)

    def test_detailed_prompt_passes_high_quality_threshold(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "An editorial environmental portrait of a fictional adult ceramic artist in a working pottery studio, "
                "framed as an eye-level medium close-up with an 85 mm portrait-lens look. The artist turns their shoulders "
                "slightly away while maintaining calm direct eye contact, loose dark hair strands crossing natural skin "
                "texture. A charcoal linen apron carries pale clay dust, and both hands hold an unfinished matte ceramic "
                "cup at chest height. A softly blurred shelf edge creates foreground depth, the artist occupies the midground, "
                "and kiln shelves with bowls and tools recede into the background. Warm diffused key light enters from high "
                "camera-left, restrained cool fill opens the shadow side, and a subtle amber rim separates the figure from the "
                "kiln area. Shallow depth of field, realistic material response, restrained earth tones, high-end editorial photography."
            ),
            negative_prompt="",
        )
        self.assertGreaterEqual(self._percentage(result), 90)

    def test_shallow_paraphrase_scores_below_production_threshold(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "A polished studio portrait of a fictional adult ceramic artist in a three-quarter composition. "
                "The subject has a calm direct gaze, natural skin texture, and wears a charcoal work apron. "
                "Warm side lighting casts gentle shadows across the face and shoulders, while a softly blurred workshop "
                "background keeps focus on the artist."
            ),
            negative_prompt="",
        )
        metrics = evaluate_prompt_quality(self.benchmark, result)
        self.assertLess(self._percentage(result), 85)
        failed_groups = {
            metric.metric_id
            for metric in metrics
            if metric.status == "fail" and metric.metric_id.startswith("coverage:")
        }
        self.assertIn("coverage:hands_and_object", failed_groups)
        self.assertIn("coverage:camera_and_crop", failed_groups)
        self.assertIn("coverage:lighting_layers", failed_groups)

    def test_flux_negative_prompt_and_quality_slogans_are_penalized(self) -> None:
        result = PromptResult(
            positive_prompt="masterpiece, best quality, 8k portrait of a ceramic artist",
            negative_prompt="bad anatomy, watermark",
        )
        metrics = {
            metric.metric_id: metric
            for metric in evaluate_prompt_quality(self.benchmark, result)
        }
        self.assertEqual(metrics["flux_negative_policy"].status, "fail")
        self.assertEqual(metrics["concrete_language"].status, "fail")


if __name__ == "__main__":
    unittest.main()
