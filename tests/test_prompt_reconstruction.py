from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app import database
from app.ai.execution import (
    AdapterExecutionResult,
    ExecutionCapabilities,
    ExecutionMode,
    ExecutionRouter,
)
from app.ai.job_store import AIJobStore, PromptDraftSource
from app.ai.prompting import (
    PromptFamily,
    PromptOperation,
    PromptResult,
    PromptScenario,
    PromptTask,
    SceneComposition,
    SceneSpec,
    SceneSubject,
)
from app.ai.reconstruction import (
    PromptReconstructionError,
    PromptReconstructionService,
    SceneAnalysisService,
)
from app.ai.transport import OpenAICompatibleResponse


class SceneRenderAdapter:
    adapter_id = "scene-render-test"
    capabilities = ExecutionCapabilities(mode=ExecutionMode.DIRECT)

    def __init__(self) -> None:
        self.calls = []

    @staticmethod
    def supports_profile(profile: dict) -> bool:
        return profile.get("kind") == "scene-render-test"

    def execute(self, prepared):
        self.calls.append(prepared)
        return AdapterExecutionResult(
            result=PromptResult(
                positive_prompt="centered clear glass bottle, warm beige background",
                negative_prompt="duplicate bottle",
            ),
            bundle=prepared.bundle,
            metadata={"transport": self.adapter_id},
        )

    def cancel(self, _run_id: str) -> None:
        return None


class PromptReconstructionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()
        self.adapter = SceneRenderAdapter()
        self.store = AIJobStore()
        self.service = PromptReconstructionService(
            router=ExecutionRouter(
                adapters=(self.adapter,),
                job_store=self.store,
            )
        )
        self.task = PromptTask(
            family=PromptFamily.FLUX,
            operation=PromptOperation.RECONSTRUCT,
            scenario=PromptScenario.PRODUCT_OBJECT,
        )
        self.scene_spec = SceneSpec(
            recommended_scenario=PromptScenario.PRODUCT_OBJECT,
            subjects=(SceneSubject(kind="clear glass bottle", position="center"),),
            composition=SceneComposition(background="warm beige"),
            uncertain_details=("small label text",),
        )

    def tearDown(self) -> None:
        database.set_db_path(self.old_db_path)
        self.temp_dir.cleanup()

    def test_rerender_reuses_scene_spec_without_an_image_input(self) -> None:
        first = self.service.render_from_scene_spec(
            profile={"kind": "scene-render-test"},
            task=self.task,
            scene_spec=self.scene_spec,
        )
        second = self.service.render_from_scene_spec(
            profile={"kind": "scene-render-test"},
            task=self.task,
            scene_spec=self.scene_spec,
        )

        self.assertNotEqual(first.job_id, second.job_id)
        self.assertEqual(len(self.adapter.calls), 2)
        self.assertTrue(all(call.image_data_url is None for call in self.adapter.calls))
        self.assertTrue(all(call.image_path is None for call in self.adapter.calls))
        self.assertTrue(all("REVIEWED SCENE SPEC JSON" in call.user_input for call in self.adapter.calls))
        self.assertEqual(self.store.get(first.job_id).scene_spec, self.scene_spec)
        self.assertEqual(self.store.get(second.job_id).scene_spec, self.scene_spec)
        first_draft = self.store.get(first.job_id).drafts[-1].draft
        self.assertEqual(first_draft.source_kind, PromptDraftSource.SCENE_SPEC)
        self.assertEqual(
            first_draft.source_payload["composition"]["background"],
            "warm beige",
        )

    def test_edited_scene_spec_is_the_persisted_render_source(self) -> None:
        edited = self.scene_spec.model_copy(
            update={
                "composition": SceneComposition(background="cool grey seamless paper"),
                "uncertain_details": (),
            }
        )
        outcome = self.service.render_from_scene_spec(
            profile={"kind": "scene-render-test"},
            task=self.task,
            scene_spec=edited,
        )
        self.assertEqual(self.store.get(outcome.job_id).scene_spec, edited)
        self.assertIn("cool grey seamless paper", self.adapter.calls[0].user_input)

    def test_operation_is_enforced_and_scenario_recommendation_is_editable(self) -> None:
        generate_task = self.task.model_copy(
            update={"operation": PromptOperation.GENERATE}
        )
        with self.assertRaises(PromptReconstructionError) as operation_error:
            self.service.render_from_scene_spec(
                profile={"kind": "scene-render-test"},
                task=generate_task,
                scene_spec=self.scene_spec,
            )
        self.assertEqual(
            operation_error.exception.code, "invalid_reconstruction_operation"
        )

        confirmed_override = self.task.model_copy(
            update={"scenario": PromptScenario.PORTRAIT}
        )
        outcome = self.service.render_from_scene_spec(
            profile={"kind": "scene-render-test"},
            task=confirmed_override,
            scene_spec=self.scene_spec,
        )
        self.assertEqual(outcome.bundle.task.scenario, PromptScenario.PORTRAIT)
        self.assertEqual(
            self.store.get(outcome.job_id).scene_spec.recommended_scenario,
            PromptScenario.PRODUCT_OBJECT,
        )
        self.assertEqual(len(self.adapter.calls), 1)

    def test_vision_analysis_creates_reviewable_persisted_scene_spec(self) -> None:
        calls = []

        def chat_runner(profile, *, api_key, messages):
            calls.append((profile, api_key, messages))
            return OpenAICompatibleResponse(
                text=(
                    '{"schema_version":"1","recommended_scenario":"product_object",'
                    '"subjects":[{"kind":"clear glass bottle","position":"center",'
                    '"attributes":{},"confidence":0.98}],'
                    '"composition":{"shot":"product close-up","camera_angle":"eye level",'
                    '"background":"warm beige"},"visible_text":[],'
                    '"uncertain_details":["small label text"]}'
                ),
                latency_ms=17,
            )

        service = SceneAnalysisService(
            job_store=self.store,
            chat_runner=chat_runner,
        )
        outcome = service.analyze(
            profile={
                "id": "vision-profile",
                "kind": "openai_compatible",
                "model": "vision-model",
                "multimodal": True,
            },
            api_key="vision-secret",
            task=self.task,
            image_data_url="data:image/png;base64,iVBORw0KGgo=",
        )

        snapshot = self.store.get(outcome.job_id)
        self.assertEqual(snapshot.job.status.value, "waiting_for_review")
        self.assertEqual(snapshot.job.task.output_contract, "scene_spec")
        self.assertEqual(snapshot.scene_spec, outcome.scene_spec)
        self.assertEqual(outcome.scene_spec.subjects[0].kind, "clear glass bottle")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], "vision-secret")
        self.assertEqual(calls[0][2][1]["content"][1]["type"], "image_url")

    def test_invalid_vision_contract_marks_analysis_job_failed(self) -> None:
        service = SceneAnalysisService(
            job_store=self.store,
            chat_runner=lambda *_args, **_kwargs: OpenAICompatibleResponse(
                text='{"not":"a scene spec"}',
                latency_ms=3,
            ),
        )
        with self.assertRaises(PromptReconstructionError) as error:
            service.analyze(
                profile={
                    "id": "vision-profile",
                    "kind": "openai_compatible",
                    "model": "vision-model",
                    "multimodal": True,
                },
                task=self.task,
                image_data_url="data:image/png;base64,iVBORw0KGgo=",
            )
        self.assertEqual(error.exception.stage, "contract")
        self.assertIsNotNone(error.exception.job_id)
        self.assertEqual(
            self.store.get(error.exception.job_id).job.status.value,
            "failed",
        )

    def test_opencode_vision_analysis_uses_isolated_image_attachment(self) -> None:
        captured = {}

        class FakeOpenCodeExecutor:
            @staticmethod
            def execute_raw(**kwargs):
                image_path = Path(kwargs["image_path"])
                captured["profile"] = kwargs["profile"]
                captured["task_package"] = kwargs["task_package"]
                captured["image_exists"] = image_path.is_file()
                captured["image_bytes"] = image_path.read_bytes()
                return type("Raw", (), {
                    "text": (
                        '{"schema_version":"1","recommended_scenario":"product_object",'
                        '"subjects":[{"kind":"clear glass bottle","position":"center",'
                        '"attributes":{},"confidence":0.98}],'
                        '"composition":{"shot":"product close-up","camera_angle":"eye level",'
                        '"background":"warm beige"},"visible_text":[],'
                        '"uncertain_details":[]}'
                    ),
                    "latency_ms": 23,
                    "raw_response_sha256": "b" * 64,
                })()

        service = SceneAnalysisService(
            job_store=self.store,
            chat_runner=lambda *_args, **_kwargs: self.fail(
                "OpenAI transport must not run for OpenCode vision analysis."
            ),
            opencode_executor=FakeOpenCodeExecutor(),
        )
        outcome = service.analyze(
            profile={
                "id": "opencode-vision",
                "kind": "cli",
                "cli_type": "opencode",
                "model": "provider/vision-model",
                "multimodal": True,
            },
            task=self.task,
            image_data_url="data:image/png;base64,iVBORw0KGgo=",
        )

        snapshot = self.store.get(outcome.job_id)
        self.assertEqual(snapshot.job.execution_backend, "vision-opencode")
        self.assertEqual(snapshot.job.status.value, "waiting_for_review")
        self.assertTrue(captured["image_exists"])
        self.assertEqual(captured["image_bytes"], b"\x89PNG\r\n\x1a\n")
        self.assertIn("SceneSpec", captured["task_package"])
        self.assertEqual(outcome.raw_response_sha256, "b" * 64)


if __name__ == "__main__":
    unittest.main()
