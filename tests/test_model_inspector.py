import json
from pathlib import Path
import struct
import sys
import pytest

from app.ai.resources import ModelEcosystem, ResourceType
from app.comfyui.model_inspector import inspect_model_file, register_model_file
from app.config_store import ConfigStore


def test_inspect_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        inspect_model_file("nonexistent_model_path_xyz.safetensors")


def test_inspect_mock_safetensors(tmp_path):
    model_path = tmp_path / "test_flux_model.safetensors"
    header_dict = {
        "__metadata__": {"modelspec.architecture": "flux-1"},
        "model.diffusion_model.double_blocks.0.img_attn.qkv.weight": {"dtype": "F16", "shape": [10, 10], "data_offsets": [0, 200]}
    }
    header_json = json.dumps(header_dict).encode("utf-8")
    header_len = len(header_json)
    header_bytes = struct.pack("<Q", header_len) + header_json

    with open(model_path, "wb") as f:
        f.write(header_bytes)
        f.write(b"\x00" * 200)

    result = inspect_model_file(str(model_path))

    assert result.file_name == "test_flux_model.safetensors"
    assert result.container_format == "safetensors"
    assert result.detected_resource_type == ResourceType.DIFFUSION_MODEL
    assert result.detected_architecture == ModelEcosystem.FLUX_1
    assert result.confidence == "high"
    assert result.recommended_folder == "diffusion_models"


def test_inspect_mock_gguf(tmp_path):
    model_path = tmp_path / "flux_unet_Q4.gguf"
    with open(model_path, "wb") as f:
        f.write(b"GGUF\x03\x00\x00\x00")

    result = inspect_model_file(str(model_path))

    assert result.file_name == "flux_unet_Q4.gguf"
    assert result.container_format == "gguf"
    assert result.detected_resource_type == ResourceType.DIFFUSION_MODEL_GGUF
    assert result.confidence in ("medium", "high")
    assert result.recommended_folder == "unet"


def test_register_model_file(tmp_path):
    source = tmp_path / "my_lora.safetensors"
    source.write_bytes(b"mock lora data")

    comfy_dir = tmp_path / "ComfyUI"
    (comfy_dir / "models" / "loras").mkdir(parents=True)
    (comfy_dir / "main.py").write_text("# mock main")

    store = ConfigStore(tmp_path / "config.json")
    store.update_comfyui_settings(
        install_path=str(comfy_dir),
        custom_python=sys.executable,
    )

    res = register_model_file(
        source_path_str=str(source),
        target_folder="loras",
        action="copy",
        store=store,
    )

    assert res["success"] is True
    assert res["action_performed"] == "copy"
    assert Path(res["target_path"]).is_file()
    assert Path(res["target_path"]).read_bytes() == b"mock lora data"
