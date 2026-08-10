from __future__ import annotations

import hashlib
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
from app.comfyui.workflow_inventory import _sync_catalog


class ModelResourcesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()
        self.catalog = ModelResourceCatalog()

    def tearDown(self) -> None:
        database.set_db_path(self.old_db_path)
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

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

    def test_inventory_sync_preserves_curated_compatibility_status(self) -> None:
        name = "flux1-dev.safetensors"
        identity = hashlib.sha256(f"comfyui:checkpoints:{name}".encode("utf-8")).hexdigest()
        self.catalog.register(ModelResource(
            content_hash=identity,
            file_path=name,
            resource_type=ResourceType.CHECKPOINT,
            architecture=ModelEcosystem.FLUX_1,
            display_name="Curated Flux checkpoint",
            metadata_source="manual",
            technical_status=CompatibilityStatus.INCOMPATIBLE,
            restriction_reason="Use a separate-components workflow.",
        ))

        _sync_catalog(self.catalog, {"checkpoints": [name]})
        refreshed = self.catalog.get_by_hash(identity)

        self.assertEqual(refreshed.metadata_source, "manual")
        self.assertEqual(refreshed.technical_status, CompatibilityStatus.INCOMPATIBLE)
        self.assertEqual(refreshed.restriction_reason, "Use a separate-components workflow.")
        self.assertEqual(refreshed.display_name, "Curated Flux checkpoint")

    def test_inventory_sync_does_not_misclassify_t5xxl_as_sdxl(self) -> None:
        name = "t5xxl_fp16.safetensors"
        identity = hashlib.sha256(f"comfyui:text_encoders:{name}".encode("utf-8")).hexdigest()
        stale_identity = hashlib.sha256(f"comfyui:clip:{name}".encode("utf-8")).hexdigest()
        self.catalog.register(ModelResource(
            content_hash=identity,
            file_path=name,
            resource_type=ResourceType.TEXT_ENCODER,
            architecture=ModelEcosystem.SDXL,
            display_name="Previously inferred T5XXL encoder",
            metadata_source="comfyui",
        ))
        self.catalog.register(ModelResource(
            content_hash=stale_identity,
            file_path=name,
            resource_type=ResourceType.TEXT_ENCODER,
            architecture=ModelEcosystem.SDXL,
            prompt_family="sdxl",
            display_name="Stale alias for T5XXL encoder",
            metadata_source="comfyui",
        ))

        _sync_catalog(self.catalog, {"text_encoders": [name]})
        refreshed = self.catalog.get_by_hash(identity)

        self.assertEqual(refreshed.architecture, ModelEcosystem.OTHER)
        self.assertEqual(refreshed.prompt_family, "generic")
        self.assertFalse(self.catalog.get_by_hash(stale_identity).is_available)


if __name__ == "__main__":
    unittest.main()
