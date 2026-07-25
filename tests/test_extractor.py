import unittest

from app.extractor import _generate_params_from_api


class GenerateParamsFromApiTests(unittest.TestCase):
    def test_lora_strengths_are_preserved(self) -> None:
        prompt = {
            "1": {
                "class_type": "LoraLoader",
                "inputs": {
                    "lora_name": "split.safetensors",
                    "strength_model": 0.8,
                    "strength_clip": 0.6,
                },
            },
            "2": {
                "class_type": "LoraLoaderModelOnly",
                "inputs": {
                    "lora_name": "model-only.safetensors",
                    "strength_model": 1.25,
                },
            },
            "3": {
                "class_type": "LoraLoader",
                "inputs": {"lora_name": ""},
            },
        }

        self.assertEqual(
            _generate_params_from_api(prompt)["loras"],
            [
                {
                    "name": "split.safetensors",
                    "strength_model": 0.8,
                    "strength_clip": 0.6,
                },
                {"name": "model-only.safetensors", "strength": 1.25},
            ],
        )

    def test_gguf_unet_takes_model_identity_over_conditioning_checkpoint(self) -> None:
        prompt = {
            "1": {
                "class_type": "UnetLoaderGGUF",
                "inputs": {"unet_name": "pony.Q4_K_M.gguf"},
            },
            "2": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "pony-conditioning.safetensors"},
            },
        }

        self.assertEqual(
            _generate_params_from_api(prompt)["model"],
            "pony.Q4_K_M.gguf",
        )


if __name__ == "__main__":
    unittest.main()
