from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app import database
from app.ai.adaptation import PromptAdaptationService
from app.ai.execution import (
    AdapterExecutionResult,
    ExecutionCapabilities,
    ExecutionMode,
    ExecutionRouter,
)
from app.ai.prompting import (
    PromptFamily,
    PromptOperation,
    PromptResult,
    PromptScenario,
    PromptTask,
)
from app.ai.translation import PromptText, PromptTranslationStore


class AdaptAdapter:
    adapter_id = "adaptation-test"
    capabilities = ExecutionCapabilities(mode=ExecutionMode.DIRECT)

    def __init__(self) -> None:
        self.prepared = None

    @staticmethod
    def supports_profile(profile: dict) -> bool:
        return profile.get("kind") == "adaptation-test"

    def execute(self, prepared):
        self.prepared = prepared
        return AdapterExecutionResult(
            result=PromptResult(
                positive_prompt="score_9, score_8_up, masterpiece, 1girl, pony style portrait",
                negative_prompt="score_4, score_5, low quality",
            ),
            bundle=prepared.bundle,
            metadata={"transport": "adaptation-test"},
        )

    def cancel(self, _run_id: str) -> None:
        return None


class PromptAdaptationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()

        self.adapter = AdaptAdapter()
        self.router = ExecutionRouter(adapters=(self.adapter,))
        self.translation_store = PromptTranslationStore()
        self.service = PromptAdaptationService(
            router=self.router,
            translation_store=self.translation_store,
        )
        self.task = PromptTask(
            family=PromptFamily.PONY,
            operation=PromptOperation.ADAPT,
            scenario=PromptScenario.SINGLE_CHARACTER,
        )

    def tearDown(self) -> None:
        database.set_db_path(self.old_db_path)
        self.temp_dir.cleanup()

    def test_adapt_transforms_prompt_for_target_family(self) -> None:
        source = PromptText(
            positive_prompt="A young girl in a cyberpunk outfit under neon rain",
            negative_prompt="ugly",
        )
        outcome = self.service.adapt(
            profile={"kind": "adaptation-test"},
            task=self.task,
            source=source,
            target_family=PromptFamily.PONY,
        )

        self.assertEqual(outcome.source_prompt, source)
        self.assertIn("score_9", outcome.adapted_prompt.positive_prompt)
        self.assertEqual(outcome.target_family, PromptFamily.PONY)
        self.assertEqual(outcome.execution.bundle.task.operation, PromptOperation.ADAPT)


if __name__ == "__main__":
    unittest.main()
