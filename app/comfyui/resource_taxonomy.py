from __future__ import annotations

from pathlib import Path

from app.ai.resources import ResourceType


# Folder names are the public names exposed by ComfyUI's model inventory API.
# Core ComfyUI exposes the physical folders, while ComfyUI-GGUF also registers
# virtual ``unet_gguf`` and ``clip_gguf`` folder names for its loader choices.
# Shared folders still need extension-based classification.
RESOURCE_MODEL_FOLDERS: dict[ResourceType, tuple[str, ...]] = {
    ResourceType.CHECKPOINT: ("checkpoints",),
    ResourceType.LORA: ("loras",),
    ResourceType.LOCON: ("loras",),
    ResourceType.DORA: ("loras",),
    ResourceType.VAE: ("vae",),
    ResourceType.EMBEDDING: ("embeddings",),
    ResourceType.DIFFUSION_MODEL: ("diffusion_models", "unet"),
    ResourceType.DIFFUSION_MODEL_GGUF: ("unet_gguf", "diffusion_models", "unet"),
    ResourceType.TEXT_ENCODER: ("text_encoders", "clip"),
    ResourceType.TEXT_ENCODER_GGUF: ("clip_gguf", "text_encoders", "clip"),
    ResourceType.CLIP_VISION: ("clip_vision",),
    ResourceType.CONTROLNET: ("controlnet",),
    ResourceType.UPSCALE_MODEL: ("upscale_models",),
}


FOLDER_RESOURCE_TYPES: dict[str, ResourceType] = {
    "checkpoints": ResourceType.CHECKPOINT,
    "loras": ResourceType.LORA,
    "vae": ResourceType.VAE,
    "embeddings": ResourceType.EMBEDDING,
    "diffusion_models": ResourceType.DIFFUSION_MODEL,
    "unet": ResourceType.DIFFUSION_MODEL,
    "unet_gguf": ResourceType.DIFFUSION_MODEL_GGUF,
    "text_encoders": ResourceType.TEXT_ENCODER,
    "clip": ResourceType.TEXT_ENCODER,
    "clip_gguf": ResourceType.TEXT_ENCODER_GGUF,
    "clip_vision": ResourceType.CLIP_VISION,
    "controlnet": ResourceType.CONTROLNET,
    "upscale_models": ResourceType.UPSCALE_MODEL,
}


def classify_inventory_resource(folder: str, name: str) -> ResourceType | None:
    resource_type = FOLDER_RESOURCE_TYPES.get(folder)
    if resource_type is ResourceType.DIFFUSION_MODEL and Path(name).suffix.casefold() == ".gguf":
        return ResourceType.DIFFUSION_MODEL_GGUF
    if resource_type is ResourceType.TEXT_ENCODER and Path(name).suffix.casefold() == ".gguf":
        return ResourceType.TEXT_ENCODER_GGUF
    return resource_type


def inventory_resource_matches(folder: str, name: str, expected: ResourceType) -> bool:
    return classify_inventory_resource(folder, name) is expected


__all__ = [
    "FOLDER_RESOURCE_TYPES",
    "RESOURCE_MODEL_FOLDERS",
    "classify_inventory_resource",
    "inventory_resource_matches",
]
