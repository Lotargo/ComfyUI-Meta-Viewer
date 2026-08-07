from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.comfyui.resource_taxonomy import get_container_format, inventory_resource_matches
from app.ai.resources import ResourceType
from app.comfyui.model_scanner import BackgroundModelScanner, compute_quick_hash


def test_get_container_format():
    assert get_container_format("model.safetensors") == "safetensors"
    assert get_container_format("model.gguf") == "gguf"
    assert get_container_format("model.ckpt") == "other"
    assert get_container_format("model.pt") == "other"


def test_inventory_resource_matches_diffusion_and_checkpoint():
    assert inventory_resource_matches("checkpoints", "sdxl.safetensors", ResourceType.CHECKPOINT) is True
    assert inventory_resource_matches("unet", "flux.gguf", ResourceType.DIFFUSION_MODEL_GGUF) is True
    assert inventory_resource_matches("diffusion_models", "model.safetensors", ResourceType.DIFFUSION_MODEL) is True


def test_compute_quick_hash(tmp_path: Path):
    test_file = tmp_path / "test_model.safetensors"
    test_file.write_bytes(b"1234567890" * 100)
    digest = compute_quick_hash(test_file)
    assert len(digest) == 64  # SHA256 hex string length


def test_background_model_scanner_status(tmp_path: Path):
    store = MagicMock()
    store.comfyui_settings.return_value = {"install_path": ""}
    scanner = BackgroundModelScanner(store)
    status = scanner.get_status()
    assert status["scanning"] is False
    assert status["scanned_count"] == 0
    assert "current_file" in status


def test_get_model_scanner_singleton(tmp_path: Path):
    store = MagicMock()
    from app.comfyui.model_scanner import get_model_scanner
    scanner1 = get_model_scanner(store)
    scanner2 = get_model_scanner(store)
    assert scanner1 is scanner2
