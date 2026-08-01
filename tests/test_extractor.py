import unittest
import struct
import tempfile
import zlib
from pathlib import Path

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


class ReadPngTextChunksTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_png_bytes(self, data: bytes) -> Path:
        filepath = self.dir_path / "test.png"
        with open(filepath, "wb") as f:
            f.write(data)
        return filepath

    def build_chunk(self, chunk_type: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = b"\x00\x00\x00\x00"  # Dummy CRC is fine since read_png_text_chunks only skips f.read(4)
        return length + chunk_type + data + crc

    def test_invalid_signature(self):
        path = self.write_png_bytes(b"INVALID_SIGNATURE\x00\x00")
        from app.extractor import read_png_text_chunks
        self.assertEqual(read_png_text_chunks(path), {})

    def test_valid_signature_empty_chunks(self):
        path = self.write_png_bytes(b"\x89PNG\r\n\x1a\n")
        from app.extractor import read_png_text_chunks
        self.assertEqual(read_png_text_chunks(path), {})

    def test_truncated_chunks(self):
        path = self.write_png_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00")
        from app.extractor import read_png_text_chunks
        self.assertEqual(read_png_text_chunks(path), {})

    def test_valid_text_chunk(self):
        chunk_data = b"Comment\x00Hello Latin-1 \xe9"
        png_data = b"\x89PNG\r\n\x1a\n" + self.build_chunk(b"tEXt", chunk_data)
        path = self.write_png_bytes(png_data)
        from app.extractor import read_png_text_chunks
        self.assertEqual(read_png_text_chunks(path), {"Comment": "Hello Latin-1 \xe9"})

    def test_text_chunk_missing_null(self):
        chunk_data = b"CommentNoSeparator"
        png_data = b"\x89PNG\r\n\x1a\n" + self.build_chunk(b"tEXt", chunk_data)
        path = self.write_png_bytes(png_data)
        from app.extractor import read_png_text_chunks
        self.assertEqual(read_png_text_chunks(path), {})

    def test_valid_itxt_uncompressed(self):
        chunk_data = b"Prompt\x00" + b"\x00\x00" + b"en\x00" + b"prompt_translated\x00" + "Hello UTF-8 \u2605".encode("utf-8")
        png_data = b"\x89PNG\r\n\x1a\n" + self.build_chunk(b"iTXt", chunk_data)
        path = self.write_png_bytes(png_data)
        from app.extractor import read_png_text_chunks
        self.assertEqual(read_png_text_chunks(path), {"Prompt": "Hello UTF-8 \u2605"})

    def test_valid_itxt_compressed(self):
        compressed_value = zlib.compress("Hello Compressed \u2605".encode("utf-8"))
        chunk_data = b"Workflow\x00" + b"\x01\x00" + b"en\x00" + b"workflow_translated\x00" + compressed_value
        png_data = b"\x89PNG\r\n\x1a\n" + self.build_chunk(b"iTXt", chunk_data)
        path = self.write_png_bytes(png_data)
        from app.extractor import read_png_text_chunks
        self.assertEqual(read_png_text_chunks(path), {"Workflow": "Hello Compressed \u2605"})

    def test_itxt_missing_first_null(self):
        chunk_data = b"NoNullHere"
        png_data = b"\x89PNG\r\n\x1a\n" + self.build_chunk(b"iTXt", chunk_data)
        path = self.write_png_bytes(png_data)
        from app.extractor import read_png_text_chunks
        self.assertEqual(read_png_text_chunks(path), {})

    def test_itxt_insufficient_rest_length(self):
        chunk_data = b"Prompt\x00" + b"\x00"
        png_data = b"\x89PNG\r\n\x1a\n" + self.build_chunk(b"iTXt", chunk_data)
        path = self.write_png_bytes(png_data)
        from app.extractor import read_png_text_chunks
        self.assertEqual(read_png_text_chunks(path), {})

    def test_itxt_missing_language_null(self):
        chunk_data = b"Prompt\x00" + b"\x00\x00" + b"en_no_null_separator"
        png_data = b"\x89PNG\r\n\x1a\n" + self.build_chunk(b"iTXt", chunk_data)
        path = self.write_png_bytes(png_data)
        from app.extractor import read_png_text_chunks
        self.assertEqual(read_png_text_chunks(path), {})

    def test_itxt_missing_translated_null(self):
        chunk_data = b"Prompt\x00" + b"\x00\x00" + b"en\x00" + b"translated_no_null"
        png_data = b"\x89PNG\r\n\x1a\n" + self.build_chunk(b"iTXt", chunk_data)
        path = self.write_png_bytes(png_data)
        from app.extractor import read_png_text_chunks
        self.assertEqual(read_png_text_chunks(path), {})

    def test_itxt_corrupt_zlib_data(self):
        chunk_data = b"Workflow\x00" + b"\x01\x00" + b"en\x00" + b"wf\x00" + b"corrupt_zlib_payload_here"
        png_data = b"\x89PNG\r\n\x1a\n" + self.build_chunk(b"iTXt", chunk_data)
        path = self.write_png_bytes(png_data)
        from app.extractor import read_png_text_chunks
        self.assertEqual(read_png_text_chunks(path), {})


if __name__ == "__main__":
    unittest.main()
