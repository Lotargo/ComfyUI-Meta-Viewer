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
from app.ai.prompting import PromptResult
from app.ai.ranking import (
    AIRank,
    AIRankingService,
    AIRatingResult,
    AIRatingService,
    AIRatingStatus,
    AIRatingStore,
)


class DummyVisionAdapter:
    adapter_id = "dummy-vision"
    capabilities = ExecutionCapabilities(mode=ExecutionMode.DIRECT)

    @staticmethod
    def supports_profile(profile: dict) -> bool:
        return profile.get("kind") == "dummy-vision"

    def execute(self, prepared):
        return AdapterExecutionResult(
            result=PromptResult(
                positive_prompt=(
                    '{"rank": "S", "technical_quality": 9.5, "composition": 9.0, '
                    '"prompt_adherence": 9.2, "defects": [], "explanation": "Masterpiece shot"}'
                ),
                negative_prompt="",
            ),
            bundle=prepared.bundle,
            metadata={"transport": "dummy-vision"},
        )

    def cancel(self, _run_id: str) -> None:
        return None


class AIRankingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()

        conn = database.get_conn()
        try:
            folder_id = conn.execute(
                "INSERT INTO folders (path, name) VALUES ('/test', 'test')",
            ).lastrowid
            self.image_id = conn.execute(
                "INSERT INTO images (folder_id, rel_path, file_name) VALUES (?, 'img.png', 'img.png')",
                (folder_id,),
            ).lastrowid
            conn.commit()
        finally:
            conn.close()

        self.store = AIRatingStore()
        self.adapter = DummyVisionAdapter()
        self.router = ExecutionRouter(adapters=(self.adapter,))
        self.service = AIRankingService(router=self.router, store=self.store)

    def tearDown(self) -> None:
        database.set_db_path(self.old_db_path)
        self.temp_dir.cleanup()

    def test_save_and_retrieve_ai_rating(self) -> None:
        result = AIRatingResult(
            status=AIRatingStatus.RATED,
            rank=AIRank.SS,
            technical_quality=9.8,
            composition=9.5,
            prompt_adherence=9.6,
            defects=["minor shadow mismatch"],
            explanation="Exceptional detail and color harmony",
        )
        rating = self.store.save(
            image_id=self.image_id,
            result=result,
            execution_backend="dummy-vision",
        )
        self.assertEqual(rating.rank, AIRank.SS)
        self.assertEqual(rating.effective_rank, AIRank.SS)
        self.assertEqual(rating.defects, ["minor shadow mismatch"])

    def test_manual_rank_override(self) -> None:
        result = AIRatingResult(
            status=AIRatingStatus.RATED,
            rank=AIRank.B,
            explanation="Good image",
        )
        self.store.save(image_id=self.image_id, result=result)

        overridden = self.store.set_manual_override(self.image_id, AIRank.SSS)
        self.assertEqual(overridden.rank, AIRank.B)
        self.assertEqual(overridden.rank_override, AIRank.SSS)
        self.assertEqual(overridden.effective_rank, AIRank.SSS)

    def test_evaluate_asset_integration(self) -> None:
        rating = self.service.evaluate_asset(
            profile={"kind": "dummy-vision"},
            image_id=self.image_id,
            prompt_text="A fantasy dragon on a mountain peak",
        )
        self.assertEqual(rating.rank, AIRank.S)
        self.assertEqual(rating.technical_quality, 9.5)
        self.assertEqual(rating.status, AIRatingStatus.RATED)

    def test_disabled_ai_ranking_returns_not_rated(self) -> None:
        rating = self.service.evaluate_asset(
            profile={"kind": "dummy-vision"},
            image_id=self.image_id,
            enabled=False,
        )
        self.assertEqual(rating.status, AIRatingStatus.NOT_RATED)
        self.assertIn("disabled", rating.explanation)


if __name__ == "__main__":
    unittest.main()
