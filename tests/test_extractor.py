import base64
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.extractor import _generate_params_from_api, make_thumbnail_b64


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


class TestMakeThumbnailB64(unittest.TestCase):
    def test_missing_or_invalid_path_returns_none(self) -> None:
        # Non-existent file path
        res = make_thumbnail_b64("non_existent_file.png")
        self.assertIsNone(res)

        # Non-image file or invalid image content
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"not an image file content")
            f_path = Path(f.name)

        try:
            res = make_thumbnail_b64(f_path)
            self.assertIsNone(res)
        finally:
            if f_path.exists():
                f_path.unlink()

    def test_rgb_image_thumbnail_jpeg(self) -> None:
        # RGB image should return jpeg format in data URL
        img = Image.new("RGB", (200, 200), color="red")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            f_path = Path(f.name)

        try:
            res = make_thumbnail_b64(f_path)
            self.assertIsNotNone(res)
            self.assertTrue(res.startswith("data:image/jpeg;base64,"))

            # Verify we can decode it and check size is correct
            b64_data = res.split(",")[1]
            decoded_bytes = base64.b64decode(b64_data)
            thumb_img = Image.open(io.BytesIO(decoded_bytes))
            self.assertEqual(thumb_img.size, (200, 200))
        finally:
            if f_path.exists():
                f_path.unlink()

    def test_rgba_image_thumbnail_png(self) -> None:
        # RGBA image should return png format in data URL
        img = Image.new("RGBA", (150, 150), color=(255, 0, 0, 128))
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img.save(f, format="PNG")
            f_path = Path(f.name)

        try:
            res = make_thumbnail_b64(f_path)
            self.assertIsNotNone(res)
            self.assertTrue(res.startswith("data:image/png;base64,"))

            b64_data = res.split(",")[1]
            decoded_bytes = base64.b64decode(b64_data)
            thumb_img = Image.open(io.BytesIO(decoded_bytes))
            self.assertEqual(thumb_img.size, (150, 150))
            self.assertEqual(thumb_img.mode, "RGBA")
        finally:
            if f_path.exists():
                f_path.unlink()

    def test_cmyk_image_conversion(self) -> None:
        # CMYK mode is not in (RGB, RGBA, L, P, LA), should convert to RGB and return JPEG
        img = Image.new("CMYK", (100, 100))
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            f_path = Path(f.name)

        try:
            res = make_thumbnail_b64(f_path)
            self.assertIsNotNone(res)
            self.assertTrue(res.startswith("data:image/jpeg;base64,"))

            b64_data = res.split(",")[1]
            decoded_bytes = base64.b64decode(b64_data)
            thumb_img = Image.open(io.BytesIO(decoded_bytes))
            self.assertEqual(thumb_img.size, (100, 100))
            self.assertEqual(thumb_img.mode, "RGB")
        finally:
            if f_path.exists():
                f_path.unlink()

    def test_image_resizing_with_max_size(self) -> None:
        # Large image should be resized down to max_size
        img = Image.new("RGB", (2000, 1000), color="blue")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            f_path = Path(f.name)

        try:
            # Using custom max_size=500
            res = make_thumbnail_b64(f_path, max_size=500)
            self.assertIsNotNone(res)
            self.assertTrue(res.startswith("data:image/jpeg;base64,"))

            b64_data = res.split(",")[1]
            decoded_bytes = base64.b64decode(b64_data)
            thumb_img = Image.open(io.BytesIO(decoded_bytes))
            # Resizing keeps aspect ratio: 2000x1000 down to 500x250
            self.assertEqual(thumb_img.size, (500, 250))

            # Using default max_size=1024
            res_default = make_thumbnail_b64(f_path)
            b64_data_default = res_default.split(",")[1]
            thumb_img_default = Image.open(io.BytesIO(base64.b64decode(b64_data_default)))
            # Resizing keeps aspect ratio: 2000x1000 down to 1024x512
            self.assertEqual(thumb_img_default.size, (1024, 512))
        finally:
            if f_path.exists():
                f_path.unlink()


if __name__ == "__main__":
    unittest.main()
