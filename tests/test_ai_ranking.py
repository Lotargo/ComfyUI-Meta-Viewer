from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app import database
from app.main import app
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


class MalformedVisionAdapter(DummyVisionAdapter):
    adapter_id = "malformed-vision"

    def execute(self, prepared):
        return AdapterExecutionResult(
            result=PromptResult(positive_prompt="Rank: S", negative_prompt=""),
            bundle=prepared.bundle,
            metadata={"transport": "malformed-vision"},
        )


class FailingVisionAdapter(DummyVisionAdapter):
    adapter_id = "failing-vision"

    def execute(self, prepared):
        raise RuntimeError("network transport failed")


class RejectingVisionAdapter(DummyVisionAdapter):
    adapter_id = "rejecting-vision"

    def execute(self, prepared):
        raise RuntimeError("content_policy rejection")


class AIRankingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()
        self.old_app_config = {
            "TESTING": app.config.get("TESTING"),
            "CONFIG_FILE": app.config.get("CONFIG_FILE"),
        }
        app.config.update(
            TESTING=True,
            CONFIG_FILE=str(Path(self.temp_dir.name) / "config.json"),
        )
        self.client = app.test_client()

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
        app.config.update(self.old_app_config)
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
        self.assertEqual(rating.output_schema_version, "1")

    def test_manual_rank_override(self) -> None:
        result = AIRatingResult(
            status=AIRatingStatus.RATED,
            rank=AIRank.B,
            technical_quality=8,
            composition=8,
            prompt_adherence=8,
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
        self.assertIsNone(rating.rank)
        self.assertIn("disabled", rating.explanation)

    def test_malformed_response_is_unreadable_without_rank(self) -> None:
        service = AIRankingService(
            router=ExecutionRouter(adapters=(MalformedVisionAdapter(),)),
            store=self.store,
        )
        rating = service.evaluate_asset(
            profile={"kind": "dummy-vision"},
            image_id=self.image_id,
        )
        self.assertEqual(rating.status, AIRatingStatus.UNREADABLE)
        self.assertIsNone(rating.rank)

    def test_technical_failure_does_not_create_low_artistic_rank(self) -> None:
        service = AIRankingService(
            router=ExecutionRouter(adapters=(FailingVisionAdapter(),)),
            store=self.store,
        )
        rating = service.evaluate_asset(
            profile={"kind": "dummy-vision"},
            image_id=self.image_id,
        )
        self.assertEqual(rating.status, AIRatingStatus.GENERATION_ERROR)
        self.assertIsNone(rating.rank)

    def test_policy_rejection_does_not_create_low_artistic_rank(self) -> None:
        service = AIRankingService(
            router=ExecutionRouter(adapters=(RejectingVisionAdapter(),)),
            store=self.store,
        )
        rating = service.evaluate_asset(
            profile={"kind": "dummy-vision"},
            image_id=self.image_id,
        )
        self.assertEqual(rating.status, AIRatingStatus.AI_REJECTED)
        self.assertIsNone(rating.rank)

    def test_delete_rating_preserves_asset(self) -> None:
        self.store.save(
            image_id=self.image_id,
            result=AIRatingResult(
                rank=AIRank.A,
                technical_quality=8,
                composition=8,
                prompt_adherence=8,
            ),
        )
        self.assertTrue(self.store.delete(self.image_id))
        self.assertFalse(self.store.delete(self.image_id))
        conn = database.get_conn()
        try:
            self.assertIsNotNone(
                conn.execute("SELECT id FROM images WHERE id=?", (self.image_id,)).fetchone()
            )
        finally:
            conn.close()

    def test_init_normalizes_legacy_low_rank_for_technical_status(self) -> None:
        conn = database.get_conn()
        try:
            conn.execute(
                """INSERT INTO ai_ratings (
                    image_id, rank, status, technical_quality, composition,
                    prompt_adherence, explanation
                ) VALUES (?, 'F', 'generation_error', 1, 1, 1, 'legacy')""",
                (self.image_id,),
            )
            conn.commit()
        finally:
            conn.close()

        database.init_db()
        normalized = self.store.get_by_image_id(self.image_id)
        self.assertEqual(normalized.status, AIRatingStatus.GENERATION_ERROR)
        self.assertIsNone(normalized.rank)
        self.assertIsNone(normalized.technical_quality)

    def test_rating_api_supports_override_get_and_delete(self) -> None:
        created = self.client.patch(
            f"/api/ai/ratings/{self.image_id}",
            json={"rank_override": "SS"},
        )
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.get_json()["rating"]["rank_override"], "SS")
        self.assertEqual(
            self.client.get(f"/api/ai/ratings/{self.image_id}").status_code,
            200,
        )
        self.assertEqual(
            self.client.delete(f"/api/ai/ratings/{self.image_id}").status_code,
            200,
        )
        self.assertEqual(
            self.client.get(f"/api/ai/ratings/{self.image_id}").status_code,
            404,
        )

    def test_evaluate_endpoint_requires_saved_multimodal_profile(self) -> None:
        response = self.client.post(
            "/api/ai/evaluate",
            json={
                "image_id": self.image_id,
                "profile": {"kind": "dummy-vision", "multimodal": True},
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "missing_profile")


if __name__ == "__main__":
    unittest.main()
