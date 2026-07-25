from __future__ import annotations

import unittest

from app.ai.resources import ResourceType
from app.comfyui.resource_taxonomy import (
    classify_inventory_resource,
    inventory_resource_matches,
)
from app.comfyui.workflow_models import WorkflowTemplateManifest


class ResourceTaxonomyTest(unittest.TestCase):
    def test_legacy_manifest_aliases_normalize_to_canonical_types(self) -> None:
        manifest = WorkflowTemplateManifest.model_validate({
            "id": "legacy-aliases",
            "name": "Legacy aliases",
            "version": "1.0.0",
            "category": "simple",
            "media_type": "image",
            "supported_ecosystems": ["other"],
            "loader_family": "gguf",
            "component_policy": {"clip": "required", "vae": "not_applicable"},
            "resource_slots": {
                "model": {
                    "label": "Model",
                    "accepts": ["unet", "unet_gguf", "clip", "clip_gguf"],
                },
            },
            "output_nodes": ["1"],
        })

        self.assertEqual(
            manifest.resource_slots["model"].accepts,
            [
                ResourceType.DIFFUSION_MODEL,
                ResourceType.DIFFUSION_MODEL_GGUF,
                ResourceType.TEXT_ENCODER,
                ResourceType.TEXT_ENCODER_GGUF,
            ],
        )
        self.assertEqual(
            manifest.model_dump(mode="json")["resource_slots"]["model"]["accepts"],
            [
                "diffusion_model",
                "diffusion_model_gguf",
                "text_encoder",
                "text_encoder_gguf",
            ],
        )

    def test_gguf_is_classified_within_shared_comfyui_folders(self) -> None:
        self.assertEqual(
            classify_inventory_resource("diffusion_models", "flux1-dev.safetensors"),
            ResourceType.DIFFUSION_MODEL,
        )
        self.assertEqual(
            classify_inventory_resource("unet", "flux1-dev.Q5_K_S.GGUF"),
            ResourceType.DIFFUSION_MODEL_GGUF,
        )
        self.assertEqual(
            classify_inventory_resource("text_encoders", "t5xxl_fp16.safetensors"),
            ResourceType.TEXT_ENCODER,
        )
        self.assertEqual(
            classify_inventory_resource("clip", "t5-v1_1-xxl.Q4_K_M.gguf"),
            ResourceType.TEXT_ENCODER_GGUF,
        )

    def test_comfyui_gguf_virtual_folders_have_explicit_semantic_types(self) -> None:
        self.assertEqual(
            classify_inventory_resource("unet_gguf", "pony.Q4_K_M.gguf"),
            ResourceType.DIFFUSION_MODEL_GGUF,
        )
        self.assertEqual(
            classify_inventory_resource("clip_gguf", "t5xxl.Q5_K_M.gguf"),
            ResourceType.TEXT_ENCODER_GGUF,
        )

    def test_standard_and_gguf_slots_do_not_accept_each_others_files(self) -> None:
        self.assertTrue(
            inventory_resource_matches(
                "diffusion_models",
                "flux1-dev.safetensors",
                ResourceType.DIFFUSION_MODEL,
            )
        )
        self.assertFalse(
            inventory_resource_matches(
                "diffusion_models",
                "flux1-dev.Q4_K_M.gguf",
                ResourceType.DIFFUSION_MODEL,
            )
        )
        self.assertTrue(
            inventory_resource_matches(
                "diffusion_models",
                "flux1-dev.Q4_K_M.gguf",
                ResourceType.DIFFUSION_MODEL_GGUF,
            )
        )
        self.assertTrue(
            inventory_resource_matches(
                "unet_gguf",
                "pony.Q4_K_M.gguf",
                ResourceType.DIFFUSION_MODEL_GGUF,
            )
        )


if __name__ == "__main__":
    unittest.main()
