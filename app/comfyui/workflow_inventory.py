from __future__ import annotations

import hashlib
from pathlib import Path

from app.ai.resources import (
    CompatibilityStatus,
    ModelEcosystem,
    ModelResource,
    ModelResourceCatalog,
    ResourceType,
)
from app.config_store import ConfigStore

from .client import ComfyUIClient, ComfyUIClientError
from .detector import detect_comfyui
from .workflow_compiler import RESOURCE_MODEL_FOLDERS
from .workflow_models import RuntimeInventory


FOLDER_RESOURCE_TYPES: dict[str, ResourceType] = {
    "checkpoints": ResourceType.CHECKPOINT,
    "loras": ResourceType.LORA,
    "vae": ResourceType.VAE,
    "embeddings": ResourceType.EMBEDDING,
    "diffusion_models": ResourceType.DIFFUSION_MODEL,
    "unet": ResourceType.DIFFUSION_MODEL,
    "text_encoders": ResourceType.TEXT_ENCODER,
    "clip": ResourceType.TEXT_ENCODER,
    "clip_vision": ResourceType.CLIP_VISION,
    "controlnet": ResourceType.CONTROLNET,
    "upscale_models": ResourceType.UPSCALE_MODEL,
}

MODEL_SUFFIXES = {
    ".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".onnx"
}


def client_from_store(store: ConfigStore, *, timeout: float = 3.0) -> ComfyUIClient:
    config = store.comfyui_settings()
    return ComfyUIClient(
        host=str(config.get("host") or "127.0.0.1"),
        port=int(config.get("port") or 8188),
        timeout=timeout,
    )


def collect_runtime_inventory(
    store: ConfigStore,
    *,
    catalog: ModelResourceCatalog | None = None,
    client: ComfyUIClient | None = None,
) -> RuntimeInventory:
    api = client or client_from_store(store)
    folders = sorted({folder for values in RESOURCE_MODEL_FOLDERS.values() for folder in values})
    try:
        object_info = api.get_object_info()
        exposed_folders = set(api.list_model_folders())
        models: dict[str, list[str]] = {}
        for folder in folders:
            if folder not in exposed_folders:
                continue
            try:
                models[folder] = sorted(dict.fromkeys(api.list_models(folder)))
            except ComfyUIClientError:
                models[folder] = []
        inventory = RuntimeInventory(
            online=True,
            node_types=sorted(object_info),
            models=models,
            source="api",
        )
    except ComfyUIClientError as exc:
        models = _filesystem_inventory(store, folders)
        inventory = RuntimeInventory(
            online=False,
            error=str(exc),
            node_types=[],
            models=models,
            source="filesystem" if models else "none",
        )

    if catalog is not None:
        _sync_catalog(catalog, inventory.models)
    return inventory


def _filesystem_inventory(store: ConfigStore, folders: list[str]) -> dict[str, list[str]]:
    config = store.comfyui_settings()
    install_path = config.get("install_path")
    if not install_path:
        return {}
    detection = detect_comfyui(str(install_path), custom_python=config.get("custom_python"))
    if not detection.is_valid or detection.comfy_dir is None:
        return {}
    model_root = Path(detection.comfy_dir) / "models"
    if not model_root.is_dir():
        return {}

    inventory: dict[str, list[str]] = {}
    for folder in folders:
        directory = model_root / folder
        if not directory.is_dir():
            continue
        names: list[str] = []
        try:
            for path in directory.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in MODEL_SUFFIXES:
                    continue
                names.append(path.relative_to(directory).as_posix())
        except OSError:
            continue
        inventory[folder] = sorted(dict.fromkeys(names))
    return inventory


def _sync_catalog(catalog: ModelResourceCatalog, models: dict[str, list[str]]) -> None:
    for folder, names in models.items():
        resource_type = FOLDER_RESOURCE_TYPES.get(folder)
        if resource_type is None:
            continue
        for name in names:
            identity = hashlib.sha256(f"comfyui:{folder}:{name}".encode("utf-8")).hexdigest()
            architecture = _infer_architecture(name)
            try:
                catalog.register(ModelResource(
                    content_hash=identity,
                    file_path=name,
                    resource_type=resource_type,
                    architecture=architecture,
                    prompt_family=architecture.value if architecture is not ModelEcosystem.OTHER else "generic",
                    display_name=Path(name).stem,
                    metadata_source="comfyui",
                    technical_status=CompatibilityStatus.SUPPORTED,
                    is_available=True,
                ))
            except Exception:
                # Inventory remains usable even if a stale or locked catalog cannot be updated.
                continue


def _infer_architecture(name: str) -> ModelEcosystem:
    lowered = name.casefold()
    if "pony" in lowered:
        return ModelEcosystem.PONY
    if "illustrious" in lowered or "noobai" in lowered:
        return ModelEcosystem.ILLUSTRIOUS
    if "flux" in lowered or "chroma" in lowered:
        return ModelEcosystem.FLUX_1
    if any(token in lowered for token in ("sd15", "sd1.5", "v1-5", "1.5-pruned")):
        return ModelEcosystem.SD15
    if "sdxl" in lowered or "xl" in lowered:
        return ModelEcosystem.SDXL
    return ModelEcosystem.OTHER


__all__ = [
    "FOLDER_RESOURCE_TYPES",
    "client_from_store",
    "collect_runtime_inventory",
]
