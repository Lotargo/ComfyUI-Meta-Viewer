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
)


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


if __name__ == "__main__":
    unittest.main()
