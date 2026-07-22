from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app import database
from app.ai.resources import (
    CapabilityResolver,
    CompatibilityStatus,
    ModelEcosystem,
    ModelResource,
    ModelResourceCatalog,
    ModelResourceError,
    ResourceType,
)


class ModelResourcesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()
        self.catalog = ModelResourceCatalog()

    def tearDown(self) -> None:
        database.set_db_path(self.old_db_path)
        self.temp_dir.cleanup()

    def test_register_and_retrieve_model_resource(self) -> None:
        resource = ModelResource(
            content_hash="abc123456789",
            file_path="/models/checkpoints/flux1-dev.safetensors",
            resource_type=ResourceType.CHECKPOINT,
            architecture=ModelEcosystem.FLUX_1,
            display_name="Flux.1 Dev Checkpoint",
            trigger_words=["flux style", "photorealistic"],
            default_strength=1.0,
        )
        saved = self.catalog.register(resource)
        self.assertEqual(saved.content_hash, "abc123456789")
        self.assertEqual(saved.architecture, ModelEcosystem.FLUX_1)
        self.assertEqual(saved.trigger_words, ["flux style", "photorealistic"])

        retrieved = self.catalog.get_by_hash("abc123456789")
        self.assertEqual(retrieved.display_name, "Flux.1 Dev Checkpoint")

        resources = self.catalog.list_resources(resource_type=ResourceType.CHECKPOINT)
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].content_hash, "abc123456789")

    def test_capability_resolver_matching_ecosystem(self) -> None:
        lora = ModelResource(
            content_hash="lora12345678",
            file_path="/models/loras/sdxl_detail.safetensors",
            resource_type=ResourceType.LORA,
            architecture=ModelEcosystem.SDXL,
            display_name="SDXL Detail Enhancer",
        )
        eval_result = CapabilityResolver.evaluate(
            checkpoint_architecture=ModelEcosystem.SDXL,
            resource=lora,
        )
        self.assertEqual(eval_result.status, CompatibilityStatus.SUPPORTED)

    def test_capability_resolver_cross_ecosystem_rules(self) -> None:
        sdxl_lora = ModelResource(
            content_hash="lora_sdxl_99",
            file_path="/models/loras/sdxl_anime.safetensors",
            resource_type=ResourceType.LORA,
            architecture=ModelEcosystem.SDXL,
            display_name="SDXL Anime LoRA",
        )
        # Pony checkpoint + SDXL LoRA -> LIMITED
        pony_eval = CapabilityResolver.evaluate(
            checkpoint_architecture=ModelEcosystem.PONY,
            resource=sdxl_lora,
        )
        self.assertEqual(pony_eval.status, CompatibilityStatus.LIMITED)
        self.assertIn("Pony checkpoint is built on SDXL architecture", pony_eval.reason)

        # Flux checkpoint + SDXL LoRA -> INCOMPATIBLE
        flux_eval = CapabilityResolver.evaluate(
            checkpoint_architecture=ModelEcosystem.FLUX_1,
            resource=sdxl_lora,
        )
        self.assertEqual(flux_eval.status, CompatibilityStatus.INCOMPATIBLE)
        self.assertIn("incompatible", flux_eval.reason.lower())

    def test_resolve_selection_preserves_resources_and_reevaluates(self) -> None:
        lora1 = ModelResource(
            content_hash="lora11111111",
            file_path="/models/loras/sdxl_style.safetensors",
            resource_type=ResourceType.LORA,
            architecture=ModelEcosystem.SDXL,
            display_name="SDXL Style",
        )
        lora2 = ModelResource(
            content_hash="lora22222222",
            file_path="/models/loras/flux_style.safetensors",
            resource_type=ResourceType.LORA,
            architecture=ModelEcosystem.FLUX_1,
            display_name="Flux Style",
        )

        evaluations = CapabilityResolver.resolve_selection(
            checkpoint_architecture=ModelEcosystem.FLUX_1,
            resources=[lora1, lora2],
        )

        self.assertEqual(len(evaluations), 2)
        self.assertEqual(evaluations[0].status, CompatibilityStatus.INCOMPATIBLE)
        self.assertEqual(evaluations[1].status, CompatibilityStatus.SUPPORTED)


if __name__ == "__main__":
    unittest.main()
