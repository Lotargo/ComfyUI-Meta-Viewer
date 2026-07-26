from __future__ import annotations

import hashlib
from pathlib import Path

from app.ai.resources import (
    CompatibilityStatus,
    ModelEcosystem,
    ModelResource,
    ModelResourceCatalog,
)
from app.config_store import ConfigStore

from .client import ComfyUIClient, ComfyUIClientError
from .detector import detect_comfyui
from .resource_taxonomy import (
    FOLDER_RESOURCE_TYPES,
    RESOURCE_MODEL_FOLDERS,
    classify_inventory_resource,
)
from .workflow_models import RuntimeInventory

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
    try:
        existing_by_hash = {
            resource.content_hash: resource
            for resource in catalog.list_resources(only_available=False)
        }
    except Exception:
        existing_by_hash = {}
    discovered_hashes: set[str] = set()
    for folder, names in models.items():
        for name in names:
            resource_type = classify_inventory_resource(folder, name)
            if resource_type is None:
                continue
            identity = hashlib.sha256(f"comfyui:{folder}:{name}".encode("utf-8")).hexdigest()
            discovered_hashes.add(identity)
            architecture = _infer_architecture(name)
            try:
                existing = existing_by_hash.get(identity)
                if existing is not None:
                    resolved_architecture = (
                        architecture
                        if existing.metadata_source == "comfyui"
                        else existing.architecture
                    )
                    resource = existing.model_copy(update={
                        "file_path": name,
                        "resource_type": resource_type,
                        "architecture": resolved_architecture,
                        "prompt_family": (
                            resolved_architecture.value
                            if resolved_architecture is not ModelEcosystem.OTHER
                            else (
                                "generic"
                                if existing.metadata_source == "comfyui"
                                else existing.prompt_family
                            )
                        ),
                        "is_available": True,
                    })
                else:
                    resource = ModelResource(
                        content_hash=identity,
                        file_path=name,
                        resource_type=resource_type,
                        architecture=architecture,
                        prompt_family=architecture.value if architecture is not ModelEcosystem.OTHER else "generic",
                        display_name=Path(name).stem,
                        metadata_source="comfyui",
                        technical_status=CompatibilityStatus.SUPPORTED,
                        is_available=True,
                    )
                catalog.register(resource)
            except Exception:
                # Inventory remains usable even if a stale or locked catalog cannot be updated.
                continue

    for identity, existing in existing_by_hash.items():
        if (
            existing.metadata_source != "comfyui"
            or identity in discovered_hashes
            or not existing.is_available
        ):
            continue
        try:
            catalog.register(existing.model_copy(update={"is_available": False}))
        except Exception:
            continue


def _infer_architecture(name: str) -> ModelEcosystem:
    lowered = name.casefold()
    if "pony" in lowered:
        return ModelEcosystem.PONY
    if "illustrious" in lowered or "noobai" in lowered:
        return ModelEcosystem.ILLUSTRIOUS
    if "flux" in lowered or "chroma" in lowered:
        return ModelEcosystem.FLUX_1
    if "hunyuan" in lowered:
        return ModelEcosystem.HUNYUAN_VIDEO
    # T5XXL encoders are shared by ecosystems such as Flux and SD3. The
    # trailing "xxl" is not evidence that the file belongs to SDXL.
    if "t5xxl" in lowered or "t5-v1_1-xxl" in lowered:
        return ModelEcosystem.OTHER
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
