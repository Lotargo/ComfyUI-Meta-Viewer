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
from app.ai.prompting import PromptCompiler, PromptResult, PromptScenario


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
        parsed = parse_intent_judge_result(
            json.dumps(
                {
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
                    "rationale": "The candidate expands the request into a coherent visual plan.",
                }
            )
        )
        self.assertEqual(parsed.total, 93)
        self.assertEqual(parsed.verdict, "pass")


class BenchmarkDefinitionTest(unittest.TestCase):
    def test_migrated_scenario_benchmarks_are_registered(self) -> None:
        self.assertIn("flux-portrait-intent-basic", BENCHMARKS)
        self.assertIn("flux-single-character-intent-basic", BENCHMARKS)
        self.assertIn("flux-architecture-interior-intent-basic", BENCHMARKS)
        self.assertIn("flux-landscape-environment-intent-basic", BENCHMARKS)
        self.assertIn("flux-product-intent-basic", BENCHMARKS)
        self.assertEqual(
            BENCHMARKS["flux-single-character-intent-basic"].task.scenario,
            PromptScenario.SINGLE_CHARACTER,
        )
        self.assertEqual(
            BENCHMARKS["flux-architecture-interior-intent-basic"].task.scenario,
            PromptScenario.ARCHITECTURE_INTERIOR,
        )
        self.assertEqual(
            BENCHMARKS["flux-landscape-environment-intent-basic"].task.scenario,
            PromptScenario.LANDSCAPE_ENVIRONMENT,
        )
        self.assertEqual(
            BENCHMARKS["flux-product-intent-basic"].task.scenario,
            PromptScenario.PRODUCT_OBJECT,
        )

    def test_each_benchmark_has_a_hundred_point_heuristic_rubric(self) -> None:
        strong_candidates = {
            "flux-portrait-intent-basic": PromptResult(
                positive_prompt=(
                    "An intimate high-end editorial portrait of an adult woman ceramic artist in a working pottery "
                    "studio, framed as an eye-level medium close-up with a relaxed direct gaze. Soft warm window light "
                    "shapes her face while shelves, a pottery wheel, clay tools, and handmade bowls create an authentic "
                    "workshop background. A linen apron dusted with clay, natural skin texture, matte ceramic surfaces, "
                    "restrained earth tones, and shallow depth of field make the scene refined and quietly cozy."
                ),
                negative_prompt="",
            ),
            "flux-product-intent-basic": PromptResult(
                positive_prompt=(
                    "A high-end commercial product photograph of an upright perfume bottle, composed as a centered "
                    "three-quarter hero shot with crisp label visibility and clean negative space. Warm amber key light "
                    "and a narrow rim create controlled reflections through transparent glass, pale gold liquid, and a "
                    "brushed metal cap. The bottle stands on a travertine pedestal against a seamless warm beige gradient "
                    "background, with a grounded shadow and polished minimal art direction."
                ),
                negative_prompt="",
            ),
            "flux-single-character-intent-basic": PromptResult(
                positive_prompt=(
                    "A single adult woman ranger stands alone in a full-body eye-level view on a narrow forest trail, "
                    "her confident stance and steady gaze reading clearly against the mist. Practical layered clothing, "
                    "a weathered wool cloak, leather boots, utility belt, map case, and field gear form a coherent "
                    "travel-worn silhouette. Soft side light filters through the canopy and catches the woven fabric "
                    "while her feet stay grounded among moss, roots, and fallen leaves with a contact shadow. Muted "
                    "earth tones, background fog, and subtle shadowed mystery create a purposeful concept-art scene."
                ),
                negative_prompt="",
            ),
            "flux-architecture-interior-intent-basic": PromptResult(
                positive_prompt=(
                    "A bright compact modern library interior photographed from eye height with a wide-angle "
                    "architectural lens and coherent one-point perspective. A clear central aisle leads from the "
                    "foreground to a calm reading area in the background, with built-in oak bookshelves defining the "
                    "perimeter. Comfortable wool-upholstered reading chairs, side tables, integrated storage, and task "
                    "lighting create a functional human-scale layout with unobstructed circulation. Natural daylight "
                    "from tall windows washes warm plaster walls and timber surfaces while pendant lights add a soft "
                    "warm glow. Restrained earth tones and quiet architectural-photography styling keep the intimate "
                    "space serene, welcoming, and well-organized."
                ),
                negative_prompt="",
            ),
            "flux-landscape-environment-intent-basic": PromptResult(
                positive_prompt=(
                    "A wide panoramic northern valley landscape at dawn, viewed from an elevated rocky foreground. "
                    "A winding river leads through the broad tundra valley floor and reflective water catches cool "
                    "blue first light before disappearing toward distant towering mountains. Moss, lichen, scattered "
                    "boulders, and sparse birch follow the riverbanks, while low mist and atmospheric haze separate "
                    "the middle ground from the far ridges. The high horizon and sweeping leading line create vast "
                    "spatial depth and monumental scale. Crisp blue-grey shadows and a restrained sunrise glow make "
                    "the natural vista feel open, cold, majestic, and awe-inspiring in photographic detail."
                ),
                negative_prompt="",
            ),
        }
        for benchmark_id, candidate in strong_candidates.items():
            with self.subTest(benchmark=benchmark_id):
                metrics = evaluate_intent_heuristics(BENCHMARKS[benchmark_id], candidate)
                self.assertEqual(sum(metric.maximum for metric in metrics), 100)


class PortraitIntentHeuristicTest(unittest.TestCase):
    def setUp(self) -> None:
        self.benchmark = BENCHMARKS["flux-portrait-intent-basic"]

    def _metrics(self, result: PromptResult):
        return {
            metric.metric_id: metric
            for metric in evaluate_intent_heuristics(self.benchmark, result)
        }

    def test_shallow_paraphrase_scores_low(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "An atmospheric portrait of an adult female ceramic artist in her workshop, "
                "natural, refined, and cozy."
            ),
            negative_prompt="",
        )
        metrics = self._metrics(result)
        self.assertLess(sum(metric.points for metric in metrics.values()), 65)
        self.assertEqual(metrics["non_trivial_expansion"].status, "fail")
        self.assertEqual(metrics["invented_camera_language"].status, "fail")
        self.assertEqual(metrics["invented_lighting"].status, "fail")

    def test_independent_visual_expansion_scores_high(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "An intimate high-end editorial portrait of an adult woman ceramic artist in a working pottery studio, "
                "framed as an eye-level medium close-up with a calm, relaxed gaze. Soft warm window light shapes one "
                "side of her face while gentle shadow preserves depth and a faint rim separates her from shelves of "
                "handmade bowls, clay tools, and a pottery wheel. She wears a charcoal linen apron dusted with pale clay "
                "and holds a matte ceramic cup, revealing natural skin texture and handmade surfaces. Restrained earth "
                "tones, shallow depth of field, and authentic unposed styling make the workshop refined and quietly cozy."
            ),
            negative_prompt="",
        )
        metrics = evaluate_intent_heuristics(self.benchmark, result)
        self.assertGreaterEqual(sum(metric.points for metric in metrics), 95)
        self.assertTrue(all(metric.status != "fail" for metric in metrics))

    def test_cross_language_expansion_uses_visual_decisions(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "A close-up portrait of an adult young woman ceramicist in her sunlit workshop, softly illuminated by "
                "warm natural window light. She has a focused expression and gazes off-camera, with fine clay dust on "
                "her fingers and natural skin texture. The background dissolves into bokeh showing shelves of ceramic "
                "pieces and pottery tools. Shallow depth of field and golden-hour shadows make the atmosphere warm, "
                "intimate, and authentic."
            ),
            negative_prompt="",
        )
        metrics = self._metrics(result)
        self.assertEqual(metrics["non_trivial_expansion"].status, "pass")
        self.assertNotIn("lexical novelty", metrics["non_trivial_expansion"].detail)
        self.assertEqual(metrics["requested_intent_coverage"].status, "warn")
        self.assertIn("premium_refined", metrics["requested_intent_coverage"].detail)


class SingleCharacterIntentHeuristicTest(unittest.TestCase):
    def setUp(self) -> None:
        self.benchmark = BENCHMARKS["flux-single-character-intent-basic"]

    def _metrics(self, result: PromptResult):
        return {
            metric.metric_id: metric
            for metric in evaluate_intent_heuristics(self.benchmark, result)
        }

    def test_shallow_character_paraphrase_scores_low(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "A single adult woman ranger shown full body on a forest trail, "
                "practical, confident, and mysterious."
            ),
            negative_prompt="",
        )
        metrics = self._metrics(result)
        self.assertLess(sum(metric.points for metric in metrics.values()), 65)
        self.assertEqual(metrics["non_trivial_expansion"].status, "fail")
        self.assertEqual(metrics["invented_lighting"].status, "fail")
        self.assertEqual(metrics["coherent_costume"].status, "fail")

    def test_coherent_full_body_character_direction_scores_high(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "A single adult woman ranger pauses alone in a full-body eye-level shot on a narrow forest trail. "
                "Her confident stance, steady gaze, and one hand holding a map create a purposeful silhouette. "
                "Practical layered clothing, a weathered wool cloak, sturdy leather boots, a utility belt, map case, "
                "and compact field gear show functional travel-worn design. Soft side light filters through the canopy, "
                "drawing a restrained rim across woven fabric while her planted feet meet moss, roots, fallen leaves, "
                "and a grounded contact shadow. Muted earth tones, shallow background fog, and shadowed tree trunks "
                "give the photographic scene an enigmatic, quietly mysterious atmosphere."
            ),
            negative_prompt="",
        )
        metrics = evaluate_intent_heuristics(self.benchmark, result)
        self.assertEqual(sum(metric.points for metric in metrics), 100)
        self.assertTrue(all(metric.status == "pass" for metric in metrics))

    def test_portrait_detail_does_not_replace_character_design(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "A close-up portrait of an adult woman ranger in a forest, with natural skin texture, "
                "a confident gaze, soft window light, and a mysterious expression."
            ),
            negative_prompt="",
        )
        metrics = self._metrics(result)
        self.assertEqual(metrics["coherent_costume"].status, "fail")
        self.assertEqual(metrics["environment_relationship"].status, "fail")
        self.assertEqual(metrics["character_action"].status, "fail")

    def test_real_mimo_result_recognizes_costume_and_visual_mystery(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "A full-body view of an adult female ranger standing confidently on a narrow forest trail, her "
                "posture relaxed yet alert with one hand resting on a sheathed dagger. She wears practical leather "
                "armor over a sturdy tunic, a hooded cloak draped over her shoulders, and weathered boots, all in "
                "muted earth tones that blend with the environment. Dappled sunlight filters through the dense "
                "canopy, casting soft, shifting shadows on the mossy ground and highlighting the texture of her gear "
                "and the quiet determination in her gaze. The trail winds behind her into misty woodland depths, "
                "framing her solitary presence against layers of ferns, tree trunks, and distant foliage."
            ),
            negative_prompt="",
        )
        metrics = self._metrics(result)
        self.assertEqual(metrics["coherent_costume"].status, "pass")
        self.assertEqual(metrics["requested_intent_coverage"].status, "pass")
        self.assertEqual(sum(metric.points for metric in metrics.values()), 100)


class ArchitectureInteriorIntentHeuristicTest(unittest.TestCase):
    def setUp(self) -> None:
        self.benchmark = BENCHMARKS["flux-architecture-interior-intent-basic"]

    def _metrics(self, result: PromptResult):
        return {
            metric.metric_id: metric
            for metric in evaluate_intent_heuristics(self.benchmark, result)
        }

    def test_shallow_interior_paraphrase_scores_low(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "A bright small modern library interior with a reading area, "
                "calm, warm, and functional."
            ),
            negative_prompt="",
        )
        metrics = self._metrics(result)
        self.assertLess(sum(metric.points for metric in metrics.values()), 65)
        self.assertEqual(metrics["non_trivial_expansion"].status, "fail")
        self.assertEqual(metrics["architectural_perspective"].status, "fail")
        self.assertEqual(metrics["surface_materials"].status, "fail")

    def test_coherent_library_architecture_scores_high(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "A bright compact modern library interior photographed from eye height with a wide-angle "
                "architectural lens and coherent one-point perspective. A clear central aisle leads from the "
                "foreground to a calm reading area in the background, with built-in oak bookshelves defining the "
                "perimeter. Comfortable wool-upholstered reading chairs, side tables, integrated storage, and task "
                "lighting create a functional human-scale layout with unobstructed circulation. Natural daylight "
                "from tall windows washes warm plaster walls and timber surfaces while pendant lights add a soft "
                "warm glow. Restrained earth tones and quiet architectural-photography styling keep the intimate "
                "space serene, welcoming, and well-organized."
            ),
            negative_prompt="",
        )
        metrics = evaluate_intent_heuristics(self.benchmark, result)
        self.assertEqual(sum(metric.points for metric in metrics), 100)
        self.assertTrue(all(metric.status == "pass" for metric in metrics))

    def test_decorative_mood_does_not_replace_spatial_design(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "A serene warm photograph of a woman reading in a beautiful room, with cozy light, "
                "soft fabric, and an elegant atmosphere."
            ),
            negative_prompt="",
        )
        metrics = self._metrics(result)
        self.assertEqual(metrics["core_intent"].status, "fail")
        self.assertEqual(metrics["architectural_perspective"].status, "fail")
        self.assertEqual(metrics["spatial_layout"].status, "fail")

    def test_real_mimo_result_recognizes_visible_calm_and_function(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "A bright interior view of a small modern library with a reading zone. A tall floor-to-ceiling oak "
                "bookshelf lines the left wall, filled with organized books. In the centre, a low-profile linen sofa "
                "and round wooden side table rest on a soft wool rug beneath a large south-facing window. Warm diffused "
                "daylight pours through the window, casting gentle shadows across the oak flooring and illuminating "
                "the warm timber tones. A slender brass floor lamp stands beside the sofa. Recessed warm LED strips "
                "trace the flat white ceiling. Eye-level perspective from the entrance, creating depth through layered "
                "furniture and shelving. Architectural visualization with natural lighting and realistic material "
                "textures."
            ),
            negative_prompt="",
        )
        metrics = self._metrics(result)
        self.assertEqual(metrics["requested_intent_coverage"].status, "pass")
        self.assertEqual(sum(metric.points for metric in metrics.values()), 100)


class LandscapeEnvironmentIntentHeuristicTest(unittest.TestCase):
    def setUp(self) -> None:
        self.benchmark = BENCHMARKS["flux-landscape-environment-intent-basic"]

    def _metrics(self, result: PromptResult):
        return {
            metric.metric_id: metric
            for metric in evaluate_intent_heuristics(self.benchmark, result)
        }

    def test_shallow_landscape_paraphrase_scores_low(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "A wide landscape of a northern valley with a river and distant mountains at dawn, "
                "spacious, cool, and majestic."
            ),
            negative_prompt="",
        )
        metrics = self._metrics(result)
        self.assertLess(sum(metric.points for metric in metrics.values()), 65)
        self.assertEqual(metrics["non_trivial_expansion"].status, "fail")
        self.assertEqual(metrics["terrain_ecology"].status, "fail")
        self.assertEqual(metrics["water_geography"].status, "fail")

    def test_coherent_northern_landscape_scores_high(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "A wide panoramic northern valley landscape at dawn, viewed from an elevated rocky foreground. "
                "A winding river leads through the broad tundra valley floor and reflective water catches cool "
                "blue first light before disappearing toward distant towering mountains. Moss, lichen, scattered "
                "boulders, and sparse birch follow the riverbanks, while low mist and atmospheric haze separate "
                "the middle ground from the far ridges. The high horizon and sweeping leading line create vast "
                "spatial depth and monumental scale. Crisp blue-grey shadows and a restrained sunrise glow make "
                "the natural vista feel open, cold, majestic, and awe-inspiring in photographic detail."
            ),
            negative_prompt="",
        )
        metrics = evaluate_intent_heuristics(self.benchmark, result)
        self.assertEqual(sum(metric.points for metric in metrics), 100)
        self.assertTrue(all(metric.status == "pass" for metric in metrics))

    def test_generic_epic_scenery_does_not_replace_geography(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "An epic majestic scenic view with cinematic cool light, beautiful nature, "
                "dramatic clouds, and an expansive atmosphere."
            ),
            negative_prompt="",
        )
        metrics = self._metrics(result)
        self.assertEqual(metrics["core_intent"].status, "fail")
        self.assertEqual(metrics["terrain_ecology"].status, "fail")
        self.assertEqual(metrics["water_geography"].status, "fail")

    def test_real_mimo_result_accepts_establishing_view_as_landscape(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "A wide establishing view of a northern valley at dawn, with a shallow braided river winding through "
                "sparse boreal grassland in the foreground. Distant snow-capped mountains rise beyond a dark conifer "
                "forest in the middle ground, their peaks catching the first warm light of sunrise. A pale blue-pink "
                "sky fades to soft gold near the horizon, and low morning mist clings to the riverbanks, creating "
                "atmospheric depth and a sense of spacious, cool, quietly majestic solitude."
            ),
            negative_prompt="",
        )
        metrics = self._metrics(result)
        self.assertEqual(metrics["core_intent"].status, "pass")
        self.assertEqual(sum(metric.points for metric in metrics.values()), 100)

    def test_real_mimo_result_separates_water_detail_from_missing_majesty(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "A wide panoramic view of a northern valley at dawn, with a silver river winding through the low "
                "ground from left to right. The foreground shows scattered boulders and sparse boreal scrub, while "
                "the river cuts a reflective path through dark spruce forest in the middle ground. Distant snow-dusted "
                "mountains rise against a pale pink and blue sky, their peaks softened by morning haze. Cool dawn "
                "light enters from the right and casts long blue shadows across the valley floor, with mist lingering "
                "along the water's edge. Landscape photography with natural colour, atmospheric perspective, and a "
                "sense of spacious solitude."
            ),
            negative_prompt="",
        )
        metrics = self._metrics(result)
        self.assertEqual(metrics["water_geography"].status, "pass")
        self.assertEqual(metrics["requested_intent_coverage"].status, "warn")
        self.assertIn("majestic", metrics["requested_intent_coverage"].detail)


class ProductIntentHeuristicTest(unittest.TestCase):
    def setUp(self) -> None:
        self.benchmark = BENCHMARKS["flux-product-intent-basic"]

    def _metrics(self, result: PromptResult):
        return {
            metric.metric_id: metric
            for metric in evaluate_intent_heuristics(self.benchmark, result)
        }

    def test_shallow_product_paraphrase_scores_low(self) -> None:
        result = PromptResult(
            positive_prompt="A beautiful luxury clean warm advertising image of a perfume bottle.",
            negative_prompt="",
        )
        metrics = self._metrics(result)
        self.assertLess(sum(metric.points for metric in metrics.values()), 65)
        self.assertEqual(metrics["non_trivial_expansion"].status, "fail")
        self.assertEqual(metrics["invented_product_set"].status, "fail")
        self.assertEqual(metrics["product_materials"].status, "fail")

    def test_product_art_direction_scores_high(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "A high-end commercial product photograph of an upright perfume bottle, composed as a centered "
                "three-quarter hero shot with crisp label visibility and generous clean negative space. Warm amber key "
                "light from camera-left and a narrow rim create controlled specular highlights and elegant reflections "
                "through transparent glass, pale gold liquid, and a brushed metal cap. The bottle stands on a travertine "
                "pedestal against a seamless warm beige gradient background, with a grounded shadow, refined minimal "
                "styling, and polished luxury campaign art direction."
            ),
            negative_prompt="",
        )
        metrics = evaluate_intent_heuristics(self.benchmark, result)
        self.assertEqual(sum(metric.points for metric in metrics), 100)
        self.assertTrue(all(metric.status == "pass" for metric in metrics))

    def test_product_benchmark_does_not_reward_portrait_only_detail(self) -> None:
        result = PromptResult(
            positive_prompt=(
                "An adult woman with natural skin texture and a relaxed gaze holds perfume in a warm portrait. "
                "The image is elegant, clean, and cozy with soft window light."
            ),
            negative_prompt="",
        )
        metrics = self._metrics(result)
        self.assertEqual(metrics["core_intent"].status, "fail")
        self.assertEqual(metrics["product_materials"].status, "fail")
        self.assertEqual(metrics["product_presentation"].status, "fail")


class OpenCodeIntentJudgeExecutorTest(unittest.TestCase):
    def test_judge_uses_family_policy_required_intents_and_five_minute_timeout(self) -> None:
        raw_result = json.dumps(
            {
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
            }
        )
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
                user_request="Сделай дорогой чистый и тёплый рекламный кадр флакона духов.",
                candidate=PromptResult(
                    positive_prompt="A luxury commercial product photograph of a perfume bottle.",
                    negative_prompt="",
                ),
                required_intents=("premium_refined", "clean_minimal", "warm"),
            )

        self.assertEqual(executed.result.total, 93)
        self.assertEqual(captured["timeout"], 300)
        self.assertEqual(
            captured["config"]["agent"]["cmv-intent-judge"]["permission"],
            {"*": "deny"},
        )
        self.assertIn("clean_minimal", captured["task"])
        self.assertIn("empty negative_prompt is correct", captured["task"])
        self.assertIn("must not be penalized", captured["task"])
        self.assertIn("Assume it came from an unknown system", " ".join(captured["args"]))


class IntentReportTest(unittest.TestCase):
    @staticmethod
    def _judge_result(atmosphere: int = 14) -> IntentJudgeResult:
        return IntentJudgeResult(
            scores=IntentJudgeScores(
                intent_fidelity=19,
                useful_visual_expansion=18,
                atmosphere_translation=atmosphere,
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

    def _report(
        self,
        benchmark_id: str,
        candidate: PromptResult,
        judge_result: IntentJudgeResult,
    ) -> IntentBenchmarkReport:
        benchmark = BENCHMARKS[benchmark_id]
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
                "An intimate high-end editorial portrait of an adult woman ceramic artist in a pottery studio, framed "
                "as an eye-level medium close-up. Warm window light crosses natural skin texture and a linen apron "
                "dusted with clay, while shelves, a pottery wheel, handmade bowls, and matte ceramic surfaces build an "
                "authentic workshop setting. She holds a cup with a relaxed gaze. Restrained earth tones, soft shadow, "
                "shallow depth of field, and an intimate unposed mood make the image refined, natural, and cozy."
            ),
            negative_prompt="",
        )
        report = self._report(
            "flux-portrait-intent-basic",
            candidate,
            self._judge_result(),
        )
        self.assertEqual(report.score_weights, (0.60, 0.40))
        self.assertEqual(
            report.combined_score,
            round(report.heuristic_percentage * 0.60 + report.judge_score * 0.40),
        )
        self.assertEqual(intent_status(report, 80), "pass")
        serialized = report.to_dict()
        self.assertEqual(serialized["schema_version"], "3")
        self.assertEqual(serialized["scores"]["weights"]["heuristic"], 0.60)

    def test_missing_product_warmth_caps_status_at_warn(self) -> None:
        candidate = PromptResult(
            positive_prompt=(
                "A high-end commercial product photograph of an upright perfume bottle, composed as a centered macro "
                "hero shot with crisp label visibility and clean negative space. Cool diffused key light and a narrow "
                "rim create reflections through transparent glass, clear liquid, and a brushed silver cap. The bottle "
                "stands on an acrylic pedestal against a seamless white gradient background with a grounded shadow and "
                "polished minimalist luxury art direction."
            ),
            negative_prompt="",
        )
        report = self._report(
            "flux-product-intent-basic",
            candidate,
            self._judge_result(atmosphere=10),
        )
        self.assertGreaterEqual(report.combined_score, 80)
        self.assertIn("warm", report.missing_required_intents)
        self.assertEqual(intent_status(report, 80), "warn")


if __name__ == "__main__":
    unittest.main()
