from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from threading import Thread, Lock
import time
import urllib.request
import urllib.error
from typing import Any, Mapping

from app.ai.resources import (
    CompatibilityStatus,
    ModelEcosystem,
    ModelResource,
    ModelResourceCatalog,
    ResourceType,
)
from app.config_store import ConfigStore
from .detector import detect_comfyui
from .resource_taxonomy import (
    FOLDER_RESOURCE_TYPES,
    RESOURCE_MODEL_FOLDERS,
    classify_inventory_resource,
    get_container_format,
)

logger = logging.getLogger(__name__)

MODEL_EXTENSIONS = {".safetensors", ".gguf", ".sft", ".ckpt", ".pt", ".pth", ".bin", ".onnx"}


def compute_quick_hash(file_path: Path, max_bytes: int = 10 * 1024 * 1024) -> str:
    """Compute a fast SHA256 digest of up to max_bytes of a model file."""
    hasher = hashlib.sha256()
    try:
        size = file_path.stat().st_size
        with open(file_path, "rb") as f:
            if size <= max_bytes:
                hasher.update(f.read())
            else:
                chunk_size = max_bytes // 2
                hasher.update(f.read(chunk_size))
                f.seek(max(0, size - chunk_size))
                hasher.update(f.read(chunk_size))
    except Exception:
        return ""
    return hasher.hexdigest()


def fetch_civitai_model_by_hash(file_hash: str, timeout: float = 4.0) -> dict[str, Any] | None:
    """Fetch model version metadata from Civitai by hash."""
    if not file_hash or len(file_hash) < 8:
        return None
    url = f"https://civitai.com/api/v1/model-versions/by-hash/{file_hash}"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "ComfyUIMetaViewer/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.debug(f"Civitai hash lookup failed for {file_hash[:8]}: {exc}")
    return None


class BackgroundModelScanner:
    """Background service that scans model files, queries Civitai, and updates the catalog."""

    def __init__(self, store: ConfigStore, catalog: ModelResourceCatalog | None = None) -> None:
        self.store = store
        self.catalog = catalog or ModelResourceCatalog()
        self._lock = Lock()
        self._scanning = False
        self._scanned_count = 0
        self._total_count = 0
        self._current_file = ""
        self._last_scan_time = 0.0
        self._last_error: str | None = None

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "scanning": self._scanning,
                "scanned_count": self._scanned_count,
                "total_count": self._total_count,
                "current_file": self._current_file,
                "last_scan_time": self._last_scan_time,
                "last_error": self._last_error,
            }

    def trigger_rescan(self) -> bool:
        with self._lock:
            if self._scanning:
                return False
            self._scanning = True
            self._scanned_count = 0
            self._total_count = 0
            self._current_file = ""

        thread = Thread(target=self._run_scan, daemon=True)
        thread.start()
        return True

    def _get_model_directories(self) -> list[tuple[str, Path]]:
        config = self.store.comfyui_settings()
        install_path = config.get("install_path")
        if not install_path:
            return []
        detection = detect_comfyui(str(install_path), custom_python=config.get("custom_python"))
        if not detection.is_valid or not detection.comfy_dir:
            return []

        models_dir = Path(detection.comfy_dir) / "models"
        if not models_dir.is_dir():
            return []

        directories: list[tuple[str, Path]] = []
        folders = sorted({folder for values in RESOURCE_MODEL_FOLDERS.values() for folder in values})
        for folder in folders:
            target = models_dir / folder
            if target.is_dir():
                directories.append((folder, target))
        return directories

    def _run_scan(self) -> None:
        logger.info("Starting background model scanner...")
        start_time = time.time()
        try:
            directories = self._get_model_directories()
            all_files: list[tuple[str, str, Path]] = []
            for folder, dir_path in directories:
                for root, _, files in os.walk(dir_path):
                    for filename in files:
                        ext = Path(filename).suffix.casefold()
                        if ext in MODEL_EXTENSIONS:
                            file_path = Path(root) / filename
                            rel_name = file_path.relative_to(dir_path).as_posix()
                            all_files.append((folder, rel_name, file_path))

            with self._lock:
                self._total_count = len(all_files)
                self._scanned_count = 0

            for folder, name, path in all_files:
                with self._lock:
                    self._current_file = name
                try:
                    self._scan_single_file(folder, name, path)
                except Exception as err:
                    logger.debug(f"Error scanning model {name}: {err}")
                with self._lock:
                    self._scanned_count += 1
                time.sleep(0.02)  # Yield CPU

            with self._lock:
                self._last_scan_time = time.time()
                self._current_file = ""
                self._last_error = None
            logger.info(f"Model scan completed in {time.time() - start_time:.2f}s ({len(all_files)} files processed).")
        except Exception as exc:
            logger.error(f"Background model scan failed: {exc}")
            with self._lock:
                self._last_error = str(exc)
                self._current_file = ""
        finally:
            with self._lock:
                self._scanning = False

    def _scan_single_file(self, folder: str, name: str, path: Path) -> None:
        resource_type = classify_inventory_resource(folder, name) or ResourceType.CHECKPOINT
        identity = hashlib.sha256(f"comfyui:{folder}:{name}".encode("utf-8")).hexdigest()
        container_format = get_container_format(name)

        existing = None
        try:
            existing = self.catalog.get(identity)
        except Exception:
            pass

        if existing is not None and existing.metadata_source == "civitai":
            return

        file_hash = compute_quick_hash(path)
        civitai_meta = fetch_civitai_model_by_hash(file_hash) if file_hash else None

        lowered_name = name.casefold()
        is_video = (
            any(kw in lowered_name for kw in ("hunyuan", "animate", "wan", "cogvideo", "svd", "mochi", "ltx"))
            or (civitai_meta and "video" in str(civitai_meta).casefold())
        )

        architecture = ModelEcosystem.OTHER
        if civitai_meta:
            base_model = str(civitai_meta.get("baseModel") or "").casefold()
            if "sd 1.5" in base_model or "sd1" in base_model:
                architecture = ModelEcosystem.SD15
            elif "sdxl" in base_model or "pony" in base_model:
                architecture = ModelEcosystem.PONY if "pony" in base_model or "pony" in lowered_name else ModelEcosystem.SDXL
            elif "flux" in base_model or "flux" in lowered_name:
                architecture = ModelEcosystem.FLUX_1
            elif "hunyuan" in base_model or "hunyuan" in lowered_name:
                architecture = ModelEcosystem.HUNYUAN_VIDEO

        display_name = (
            civitai_meta.get("model", {}).get("name")
            or civitai_meta.get("name")
            or Path(name).stem
        ) if civitai_meta else Path(name).stem

        resource = ModelResource(
            content_hash=identity,
            file_path=name,
            resource_type=resource_type,
            architecture=architecture,
            prompt_family=architecture.value if architecture is not ModelEcosystem.OTHER else "generic",
            display_name=display_name,
            metadata_source="civitai" if civitai_meta else "comfyui",
            technical_status=CompatibilityStatus.SUPPORTED,
            is_available=True,
        )
        try:
            self.catalog.register(resource)
        except Exception:
            pass


_scanner_instance: BackgroundModelScanner | None = None
_scanner_lock = Lock()


def get_model_scanner(store: ConfigStore) -> BackgroundModelScanner:
    global _scanner_instance
    with _scanner_lock:
        if _scanner_instance is None:
            _scanner_instance = BackgroundModelScanner(store)
        return _scanner_instance


__all__ = [
    "BackgroundModelScanner",
    "compute_quick_hash",
    "fetch_civitai_model_by_hash",
    "get_model_scanner",
]
