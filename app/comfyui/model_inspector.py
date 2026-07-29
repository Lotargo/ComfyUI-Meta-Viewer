from __future__ import annotations

import json
from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import struct
from typing import Any, Literal

from app.ai.resources import CompatibilityStatus, ModelEcosystem, ModelResource, ModelResourceCatalog, ResourceType
from app.config_store import ConfigStore
from .detector import detect_comfyui
from .resource_taxonomy import FOLDER_RESOURCE_TYPES, RESOURCE_MODEL_FOLDERS, classify_inventory_resource
from .workflow_inventory import client_from_store, collect_runtime_inventory, _infer_architecture


TARGET_FOLDERS_BY_TYPE: dict[ResourceType, str] = {
    ResourceType.CHECKPOINT: "checkpoints",
    ResourceType.LORA: "loras",
    ResourceType.LOCON: "loras",
    ResourceType.DORA: "loras",
    ResourceType.VAE: "vae",
    ResourceType.EMBEDDING: "embeddings",
    ResourceType.DIFFUSION_MODEL: "diffusion_models",
    ResourceType.DIFFUSION_MODEL_GGUF: "unet",
    ResourceType.TEXT_ENCODER: "text_encoders",
    ResourceType.TEXT_ENCODER_GGUF: "clip",
    ResourceType.CLIP_VISION: "clip_vision",
    ResourceType.CONTROLNET: "controlnet",
    ResourceType.UPSCALE_MODEL: "upscale_models",
}


@dataclass
class InspectionResult:
    file_path: str
    file_name: str
    file_size_bytes: int
    container_format: str
    detected_resource_type: ResourceType
    detected_architecture: ModelEcosystem
    confidence: Literal["high", "medium", "low"]
    recommended_folder: str
    recommended_target_path: str
    metadata: dict[str, Any] = field(default_factory=dict)
    sample_tensor_keys: list[str] = field(default_factory=list)


def inspect_model_file(file_path_str: str, store: ConfigStore | None = None) -> InspectionResult:
    path = Path(file_path_str)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path_str}")

    size_bytes = path.stat().st_size
    suffix = path.suffix.casefold()

    container_format = "unknown"
    metadata: dict[str, Any] = {}
    tensor_keys: list[str] = []

    detected_type: ResourceType | None = None
    detected_arch = _infer_architecture(path.name)
    confidence: Literal["high", "medium", "low"] = "low"

    if suffix == ".safetensors":
        container_format = "safetensors"
        try:
            with open(path, "rb") as f:
                header_len_bytes = f.read(8)
                if len(header_len_bytes) == 8:
                    header_len = struct.unpack("<Q", header_len_bytes)[0]
                    if 0 < header_len < 100 * 1024 * 1024:
                        header_json_bytes = f.read(header_len)
                        raw_header = json.loads(header_json_bytes.decode("utf-8"))
                        if "__metadata__" in raw_header:
                            metadata = raw_header["__metadata__"]
                        tensor_keys = [k for k in raw_header.keys() if k != "__metadata__"]
        except Exception:
            pass

        if tensor_keys or metadata:
            detected_type, arch_from_keys, score = _analyze_safetensors_keys(tensor_keys, metadata)
            if arch_from_keys:
                detected_arch = arch_from_keys
            if score == "high":
                confidence = "high"
            elif score == "medium":
                confidence = "medium"

    elif suffix == ".gguf":
        container_format = "gguf"
        try:
            with open(path, "rb") as f:
                magic = f.read(4)
                if magic == b"GGUF":
                    confidence = "medium"
        except Exception:
            pass

        if "clip" in path.name.lower() or "t5" in path.name.lower():
            detected_type = ResourceType.TEXT_ENCODER_GGUF
        else:
            detected_type = ResourceType.DIFFUSION_MODEL_GGUF

    if detected_type is None:
        # Fallback to filename heuristic
        for folder_name, rtype in FOLDER_RESOURCE_TYPES.items():
            if folder_name in path.parent.name.lower():
                detected_type = rtype
                confidence = "medium"
                break
        if detected_type is None:
            lowered = path.name.lower()
            if "lora" in lowered:
                detected_type = ResourceType.LORA
            elif "vae" in lowered:
                detected_type = ResourceType.VAE
            elif "control" in lowered:
                detected_type = ResourceType.CONTROLNET
            elif "upscale" in lowered or "esrgan" in lowered or "swinir" in lowered:
                detected_type = ResourceType.UPSCALE_MODEL
            else:
                detected_type = ResourceType.CHECKPOINT
                confidence = "low"

    rec_folder = TARGET_FOLDERS_BY_TYPE.get(detected_type, "checkpoints")

    target_dir = ""
    if store is not None:
        config = store.comfyui_settings()
        install_path = config.get("install_path")
        if install_path:
            detection = detect_comfyui(str(install_path), custom_python=config.get("custom_python"))
            if detection.is_valid and detection.comfy_dir:
                target_dir = str(Path(detection.comfy_dir) / "models" / rec_folder / path.name)

    return InspectionResult(
        file_path=str(path.resolve()),
        file_name=path.name,
        file_size_bytes=size_bytes,
        container_format=container_format,
        detected_resource_type=detected_type,
        detected_architecture=detected_arch,
        confidence=confidence,
        recommended_folder=rec_folder,
        recommended_target_path=target_dir or f"models/{rec_folder}/{path.name}",
        metadata=metadata,
        sample_tensor_keys=tensor_keys[:10],
    )


def _analyze_safetensors_keys(
    keys: list[str], metadata: dict[str, Any]
) -> tuple[ResourceType | None, ModelEcosystem | None, str]:
    has_cond = any("cond_stage_model." in k for k in keys)
    has_first_stage = any("first_stage_model." in k for k in keys)
    has_model_diff = any("model.diffusion_model." in k for k in keys)
    has_unet = any("model.unet." in k for k in keys)
    has_lora = any("lora_down" in k or "lora_up" in k or "lora_unet" in k or "lora_te" in k for k in keys)
    has_control = any("control_model." in k for k in keys)
    has_upscale = any("conv_first." in k or "upsampler." in k for k in keys)
    has_vae = any("decoder.conv_in" in k or "encoder.conv_in" in k for k in keys)

    # Check metadata architecture first if available
    arch_meta = metadata.get("modelspec.architecture") or metadata.get("ss_base_model_version") or ""
    arch: ModelEcosystem | None = None
    if "flux" in arch_meta.lower():
        arch = ModelEcosystem.FLUX_1
    elif "pony" in arch_meta.lower():
        arch = ModelEcosystem.PONY
    elif "sdxl" in arch_meta.lower():
        arch = ModelEcosystem.SDXL

    if has_lora:
        return ResourceType.LORA, arch, "high"
    if has_control:
        return ResourceType.CONTROLNET, arch, "high"
    if has_upscale:
        return ResourceType.UPSCALE_MODEL, arch, "high"
    if has_cond and has_first_stage:
        return ResourceType.CHECKPOINT, arch, "high"
    if has_model_diff and not has_cond:
        return ResourceType.DIFFUSION_MODEL, arch or ModelEcosystem.FLUX_1, "high"
    if has_vae and not has_model_diff and not has_cond:
        return ResourceType.VAE, arch, "high"
    if has_unet:
        return ResourceType.CHECKPOINT, arch, "medium"

    return None, arch, "low"


def register_model_file(
    source_path_str: str,
    target_folder: str,
    action: Literal["copy", "link"],
    store: ConfigStore,
    catalog: ModelResourceCatalog | None = None,
) -> dict[str, Any]:
    source_path = Path(source_path_str)
    if not source_path.is_file():
        raise FileNotFoundError(f"Source file not found: {source_path_str}")

    config = store.comfyui_settings()
    install_path = config.get("install_path")
    if not install_path:
        raise ValueError("ComfyUI install path is not configured.")

    detection = detect_comfyui(str(install_path), custom_python=config.get("custom_python"))
    if not detection.is_valid or not detection.comfy_dir:
        raise ValueError("Invalid ComfyUI installation directory.")

    model_root = Path(detection.comfy_dir) / "models"
    dest_dir = model_root / target_folder
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_path = dest_dir / source_path.name
    if dest_path.resolve() == source_path.resolve():
        # Already in destination folder
        action_performed = "already_exists"
    else:
        if action == "link":
            try:
                if dest_path.exists():
                    dest_path.unlink()
                os.symlink(source_path, dest_path)
                action_performed = "symlink"
            except (OSError, NotImplementedError):
                shutil.copy2(source_path, dest_path)
                action_performed = "copy_fallback"
        else:
            shutil.copy2(source_path, dest_path)
            action_performed = "copy"

    inventory = collect_runtime_inventory(store, catalog=catalog)

    relative_name = source_path.name
    folder_models = inventory.models.get(target_folder, [])
    found_in_inventory = any(relative_name in m for m in folder_models)

    return {
        "success": True,
        "action_performed": action_performed,
        "source_path": str(source_path),
        "target_path": str(dest_path),
        "target_folder": target_folder,
        "found_in_inventory": found_in_inventory,
        "inventory_online": inventory.online,
    }


__all__ = [
    "InspectionResult",
    "inspect_model_file",
    "register_model_file",
]
