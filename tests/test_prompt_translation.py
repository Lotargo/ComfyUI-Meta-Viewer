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
from app.ai.job_store import AIJobStore
from app.ai.prompting import (
    PromptFamily,
    PromptOperation,
    PromptResult,
    PromptScenario,
    PromptTask,
)
from app.ai.translation import (
    PromptText,
    PromptTranslationError,
    PromptTranslationService,
    PromptTranslationStore,
)


class TranslationAdapter:
    adapter_id = "translation-test"
    capabilities = ExecutionCapabilities(mode=ExecutionMode.DIRECT)

    def __init__(self) -> None:
        self.prepared = None

    @staticmethod
    def supports_profile(profile: dict) -> bool:
        return profile.get("kind") == "translation-test"

    def execute(self, prepared):
        self.prepared = prepared
        return AdapterExecutionResult(
            result=PromptResult(
                positive_prompt="a quiet glass house in the northern forest",
                negative_prompt="text, watermark",
            ),
            bundle=prepared.bundle,
            metadata={"transport": "translation-test"},
        )

    def cancel(self, _run_id: str) -> None:
        return None


class PromptTranslationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()
        self.adapter = TranslationAdapter()
        self.job_store = AIJobStore()
        self.translation_store = PromptTranslationStore()
        self.service = PromptTranslationService(
            router=ExecutionRouter(
                adapters=(self.adapter,),
                job_store=self.job_store,
            ),
            store=self.translation_store,
        )
        self.task = PromptTask(
            family=PromptFamily.FLUX,
            operation=PromptOperation.TRANSLATE,
            scenario=PromptScenario.ARCHITECTURE_INTERIOR,
        )

    def tearDown(self) -> None:
        database.set_db_path(self.old_db_path)
        self.temp_dir.cleanup()

    def test_translation_persists_source_and_result_as_separate_prompts(self) -> None:
        source = PromptText(
            positive_prompt="тихий стеклянный дом в северном лесу",
            negative_prompt="текст, водяной знак",
        )
        outcome = self.service.translate(
            profile={
                "id": "translator",
                "kind": "translation-test",
                "model": "mimo-v2.5-free",
            },
            task=self.task,
            source=source,
            source_language="ru",
            target_language="en",
        )

        self.assertEqual(outcome.translation.source, source)
        self.assertEqual(
            outcome.translation.translated.positive_prompt,
            "a quiet glass house in the northern forest",
        )
        self.assertNotEqual(
            outcome.translation.source.positive_prompt,
            outcome.translation.translated.positive_prompt,
        )
        self.assertEqual(outcome.translation.target_language, "en")
        self.assertEqual(outcome.execution.bundle.task.operation, PromptOperation.TRANSLATE)
        self.assertIn("TARGET LANGUAGE\nen", self.adapter.prepared.user_input)
        self.assertIn("тихий стеклянный дом", self.adapter.prepared.user_input)

        reloaded = PromptTranslationStore().get(outcome.execution.job_id)
        self.assertEqual(reloaded, outcome.translation)
        snapshot = AIJobStore().get(outcome.execution.job_id)
        self.assertEqual(snapshot.job.task.operation, PromptOperation.TRANSLATE)
        self.assertEqual(snapshot.result, outcome.execution.result)

    def test_adaptation_cannot_be_silently_executed_as_translation(self) -> None:
        adapt_task = self.task.model_copy(
            update={"operation": PromptOperation.ADAPT}
        )
        with self.assertRaises(PromptTranslationError) as caught:
            self.service.translate(
                profile={"kind": "translation-test"},
                task=adapt_task,
                source=PromptText(positive_prompt="portrait"),
                target_language="en",
            )
        self.assertEqual(caught.exception.code, "invalid_translation_operation")
        self.assertIsNone(self.adapter.prepared)

        conn = database.get_conn()
        try:
            count = conn.execute("SELECT COUNT(*) FROM ai_jobs").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 0)

    def test_translation_record_requires_a_completed_ai_job(self) -> None:
        with self.assertRaises(PromptTranslationError) as caught:
            self.translation_store.save(
                job_id=999,
                source=PromptText(positive_prompt="исходный prompt"),
                translated=PromptText(positive_prompt="source prompt"),
                target_language="en",
            )
        self.assertEqual(caught.exception.code, "translation_job_incomplete")
        with self.assertRaises(PromptTranslationError) as missing:
            self.translation_store.get(999)
        self.assertEqual(missing.exception.code, "translation_not_found")

        queued = self.job_store.create(
            task=self.task,
            execution_backend="translation-test",
        )
        with self.assertRaises(PromptTranslationError) as queued_error:
            self.translation_store.save(
                job_id=queued.id,
                source=PromptText(positive_prompt="исходный prompt"),
                translated=PromptText(positive_prompt="source prompt"),
                target_language="en",
            )
        self.assertEqual(queued_error.exception.code, "translation_job_incomplete")

    def test_language_identifiers_are_bounded_before_execution(self) -> None:
        with self.assertRaises(PromptTranslationError) as caught:
            self.service.translate(
                profile={"kind": "translation-test"},
                task=self.task,
                source=PromptText(positive_prompt="portrait"),
                target_language="x" * 81,
            )
        self.assertEqual(caught.exception.code, "invalid_language")
        self.assertIsNone(self.adapter.prepared)

        with self.assertRaises(ValueError):
            PromptText(positive_prompt="   ")


if __name__ == "__main__":
    unittest.main()
