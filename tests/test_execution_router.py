from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app import database
from app.ai.execution import (
    AdapterExecutionError,
    AdapterExecutionResult,
    ExecutionCapabilities,
    ExecutionMode,
    ExecutionRouter,
    ExecutionRouterError,
)
from app.ai.job_store import AIJobStatus, AIJobStore
from app.ai.prompting import (
    PromptCompiler,
    PromptFamily,
    PromptOperation,
    PromptResult,
    PromptScenario,
    PromptTask,
    SceneSpec,
)


class FakeAdapter:
    def __init__(
        self,
        adapter_id: str,
        kind: str,
        *,
        mode: ExecutionMode,
        image_inputs: tuple[str, ...] = (),
        failure: AdapterExecutionError | None = None,
    ):
        self.adapter_id = adapter_id
        self.kind = kind
        self.failure = failure
        self.capabilities = ExecutionCapabilities(
            mode=mode,
            supports_images=bool(image_inputs),
            image_inputs=image_inputs,
            supports_json_output=True,
            supports_skills=mode is ExecutionMode.AGENT_HOST,
        )
        self.prepared = None

    def supports_profile(self, profile: dict) -> bool:
        return profile.get("kind") == self.kind

    def execute(self, prepared):
        self.prepared = prepared
        if self.failure is not None:
            raise self.failure
        result = PromptResult(
            positive_prompt=f"result from {self.adapter_id}",
            negative_prompt="watermark",
        )
        return AdapterExecutionResult(
            result=result,
            bundle=prepared.bundle,
            metadata={"transport": self.adapter_id, "latency_ms": 7},
        )

    def cancel(self, _run_id: str) -> None:
        return None


class ExecutionRouterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()
        self.store = AIJobStore()
        self.task = PromptTask(
            family=PromptFamily.FLUX,
            operation=PromptOperation.GENERATE,
            scenario=PromptScenario.PORTRAIT,
        )
        self.direct = FakeAdapter(
            "direct-test",
            "openai_compatible",
            mode=ExecutionMode.DIRECT,
            image_inputs=("data_url",),
        )
        self.host = FakeAdapter(
            "host-test",
            "agent_host",
            mode=ExecutionMode.AGENT_HOST,
            image_inputs=("file_path",),
        )
        self.router = ExecutionRouter(
            adapters=(self.direct, self.host),
            compiler=PromptCompiler(),
            job_store=self.store,
        )

    def tearDown(self) -> None:
        database.set_db_path(self.old_db_path)
        self.temp_dir.cleanup()

    def test_routes_by_adapter_match_and_persists_normalized_result(self) -> None:
        outcome = self.router.execute(
            profile={
                "id": "profile-1",
                "kind": "agent_host",
                "model": "host/model",
            },
            task=self.task,
            user_input="Create a portrait.",
            image_path="portrait.png",
        )

        self.assertEqual(outcome.adapter_id, "host-test")
        self.assertEqual(outcome.result.positive_prompt, "result from host-test")
        self.assertIsNone(self.direct.prepared)
        self.assertEqual(self.host.prepared.bundle, outcome.bundle)
        self.assertEqual(self.host.prepared.image_path, Path("portrait.png"))

        snapshot = self.store.get(outcome.job_id)
        self.assertEqual(snapshot.job.status, AIJobStatus.COMPLETED)
        self.assertEqual(snapshot.job.execution_backend, "host-test")
        self.assertEqual(snapshot.job.provider_profile_id, "profile-1")
        self.assertEqual(snapshot.job.model_id, "host/model")
        self.assertEqual(snapshot.result, outcome.result)
        self.assertEqual(snapshot.drafts[0].draft.versions, outcome.bundle.versions)
        self.assertEqual(snapshot.execution_metadata["transport"], "host-test")

    def test_capabilities_reject_wrong_image_representation_before_job_creation(self) -> None:
        capabilities = self.router.capabilities_for({"kind": "agent_host"})
        self.assertEqual(capabilities.mode, ExecutionMode.AGENT_HOST)
        self.assertTrue(capabilities.supports_skills)

        with self.assertRaises(ExecutionRouterError) as caught:
            self.router.execute(
                profile={"kind": "agent_host"},
                task=self.task,
                user_input="Reconstruct.",
                image_data_url="data:image/png;base64,AA==",
            )
        self.assertEqual(caught.exception.code, "incompatible_image_input")
        self.assertIsNone(caught.exception.job_id)

        conn = database.get_conn()
        try:
            count = conn.execute("SELECT COUNT(*) FROM ai_jobs").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 0)

    def test_backend_failure_is_normalized_and_persisted(self) -> None:
        failure = AdapterExecutionError(
            "Provider overloaded.",
            code="provider_error",
            stage="host",
            technical_error="HTTP 503",
        )
        failing = FakeAdapter(
            "failing-host",
            "agent_host",
            mode=ExecutionMode.AGENT_HOST,
            failure=failure,
        )
        router = ExecutionRouter(adapters=(failing,), job_store=self.store)

        with self.assertRaises(ExecutionRouterError) as caught:
            router.execute(
                profile={"kind": "agent_host"},
                task=self.task,
                user_input="Create a portrait.",
            )
        self.assertEqual(caught.exception.code, "provider_error")
        self.assertEqual(caught.exception.stage, "host")
        self.assertEqual(caught.exception.technical_error, "HTTP 503")

        snapshot = self.store.get(caught.exception.job_id)
        self.assertEqual(snapshot.job.status, AIJobStatus.FAILED)
        self.assertEqual(snapshot.job.technical_error, "HTTP 503")
        self.assertIsNone(snapshot.result)

    def test_unsupported_and_ambiguous_profiles_are_rejected_deterministically(self) -> None:
        with self.assertRaises(ExecutionRouterError) as unsupported:
            self.router.capabilities_for({"kind": "unknown"})
        self.assertEqual(unsupported.exception.code, "unsupported_backend")

        duplicate = FakeAdapter(
            "second-direct",
            "openai_compatible",
            mode=ExecutionMode.DIRECT,
        )
        ambiguous = ExecutionRouter(adapters=(self.direct, duplicate), job_store=self.store)
        with self.assertRaises(ExecutionRouterError) as caught:
            ambiguous.capabilities_for({"kind": "openai_compatible"})
        self.assertEqual(caught.exception.code, "ambiguous_backend")

    def test_job_creation_failure_is_normalized_before_adapter_execution(self) -> None:
        with self.assertRaises(ExecutionRouterError) as caught:
            self.router.execute(
                profile={"kind": "openai_compatible"},
                task=self.task,
                user_input="Create a portrait.",
                asset_id=999,
            )
        self.assertEqual(caught.exception.code, "persistence_error")
        self.assertEqual(caught.exception.stage, "persistence")
        self.assertIsNone(caught.exception.job_id)
        self.assertIn("FOREIGN KEY", caught.exception.technical_error)
        self.assertIsNone(self.direct.prepared)

    def test_scene_spec_is_persisted_as_part_of_the_routed_job(self) -> None:
        scene_spec = SceneSpec(
            recommended_scenario=PromptScenario.PORTRAIT,
            uncertain_details=("small earring",),
        )
        outcome = self.router.execute(
            profile={"kind": "openai_compatible"},
            task=self.task,
            user_input="Render the reviewed SceneSpec.",
            scene_spec=scene_spec,
        )
        self.assertEqual(self.store.get(outcome.job_id).scene_spec, scene_spec)


if __name__ == "__main__":
    unittest.main()
