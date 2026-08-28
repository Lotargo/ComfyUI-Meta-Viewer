from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from app.ai.prompting import PromptFamily

SIMPLE_MODELS_DIR = Path(__file__).parent / "simple_models"


class QualityPresetLevel(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    DETAILED = "detailed"


@dataclass(frozen=True)
class ProfileResourceDependency:
    resource_type: str
    folder: str
    filename: str
    display_name: str
    download_url: str | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApprovedProfile:
    id: str
    name: str
    technical_name: str
    description: str
    prompt_family: PromptFamily
    architecture: str
    source_url: str
    source_version_id: int | None
    vram_min_gb: float
    vram_rec_gb: float
    workflow_ready: bool
    default_negative_prompt: str
    prompt_prefix: str
    aspect_ratios: tuple[dict[str, Any], ...]
    quality_preset_ids: tuple[str, ...]
    required_resources: tuple[ProfileResourceDependency, ...]
    directory: Path


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _load_profile(directory: Path) -> ApprovedProfile:
    manifest = _read_json(directory / "manifest.json")
    resources_data = _read_json(directory / "resources.json")
    resources: list[ProfileResourceDependency] = []
    for raw in resources_data.get("required", []):
        resources.append(
            ProfileResourceDependency(
                resource_type=str(raw.get("resource_type") or ""),
                folder=str(raw.get("folder") or ""),
                filename=str(raw.get("filename") or ""),
                display_name=str(raw.get("display_name") or raw.get("filename") or ""),
                download_url=str(raw.get("download_url") or "") or None,
                aliases=tuple(str(item) for item in raw.get("aliases", []) if item),
            )
        )
    family = PromptFamily(str(manifest.get("prompt_family") or "sdxl"))
    return ApprovedProfile(
        id=str(manifest["id"]),
        name=str(manifest["name"]),
        technical_name=str(manifest.get("technical_name") or manifest["name"]),
        description=str(manifest.get("description") or ""),
        prompt_family=family,
        architecture=str(manifest.get("architecture") or ""),
        source_url=str(manifest.get("source_url") or ""),
        source_version_id=(
            int(manifest["source_version_id"])
            if manifest.get("source_version_id") is not None
            else None
        ),
        vram_min_gb=float(manifest.get("vram_min_gb") or 0),
        vram_rec_gb=float(manifest.get("vram_rec_gb") or 0),
        workflow_ready=bool(manifest.get("workflow_ready")),
        default_negative_prompt=str(manifest.get("default_negative_prompt") or ""),
        prompt_prefix=str(manifest.get("prompt_prefix") or ""),
        aspect_ratios=tuple(manifest.get("aspect_ratios") or ()),
        quality_preset_ids=tuple(
            str(item) for item in manifest.get("quality_presets", ("fast", "standard", "detailed"))
        ),
        required_resources=tuple(resources),
        directory=directory,
    )


def load_approved_profiles(root: Path = SIMPLE_MODELS_DIR) -> dict[str, ApprovedProfile]:
    profiles: dict[str, ApprovedProfile] = {}
    if not root.is_dir():
        return profiles
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        manifest = directory / "manifest.json"
        resources = directory / "resources.json"
        if not manifest.is_file() or not resources.is_file():
            continue
        profile = _load_profile(directory)
        profiles[profile.id] = profile
    return profiles


APPROVED_PROFILES = load_approved_profiles()


def get_simple_workflow_path(profile_or_id: ApprovedProfile | str) -> Path:
    profile = (
        profile_or_id
        if isinstance(profile_or_id, ApprovedProfile)
        else APPROVED_PROFILES[str(profile_or_id)]
    )
    return profile.directory / "workflow.json"


def load_simple_workflow_json(profile_or_id: ApprovedProfile | str) -> dict[str, Any]:
    path = get_simple_workflow_path(profile_or_id)
    if not path.is_file():
        profile_id = profile_or_id.id if isinstance(profile_or_id, ApprovedProfile) else profile_or_id
        raise FileNotFoundError(f"Simple Mode workflow is not prepared yet for {profile_id}")
    return _read_json(path)


def _inventory_names(inventory: Any, folder: str) -> set[str]:
    models = getattr(inventory, "models", None)
    if not isinstance(models, dict):
        return set()
    return {Path(str(name)).name.casefold() for name in models.get(folder, [])}


def check_profile_health(
    profile: ApprovedProfile,
    inventory: Any | None = None,
) -> dict[str, Any]:
    missing: list[dict[str, Any]] = []
    inventory_known = inventory is not None and isinstance(getattr(inventory, "models", None), dict)
    for dep in profile.required_resources:
        candidates = {dep.filename.casefold(), *(alias.casefold() for alias in dep.aliases)}
        found = bool(candidates & _inventory_names(inventory, dep.folder)) if inventory_known else False
        if not found:
            missing.append(
                {
                    "resource_type": dep.resource_type,
                    "folder": dep.folder,
                    "filename": dep.filename,
                    "display_name": dep.display_name,
                    "download_url": dep.download_url,
                }
            )

    if not inventory_known:
        status = "unknown"
        message = "Проверяем локальные компоненты"
    elif missing:
        status = "not_installed"
        message = f"Не хватает компонентов: {len(missing)}"
    elif not profile.workflow_ready or not get_simple_workflow_path(profile).is_file():
        status = "workflow_pending"
        message = "Компоненты готовы, workflow ещё калибруется"
    else:
        status = "ready"
        message = "Готова к генерации"

    return {
        "status": status,
        "ready": status == "ready",
        "missing_resources": missing,
        "installable": bool(missing) and all(item.get("download_url") for item in missing),
        "message": message,
    }


def _preset_summary(profile: ApprovedProfile) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for preset_id in profile.quality_preset_ids:
        path = profile.directory / "presets" / f"{preset_id}.json"
        if not path.is_file():
            continue
        data = _read_json(path)
        result[preset_id] = {"label": str(data.get("label") or preset_id)}
    return result


def serialize_approved_profile(
    profile: ApprovedProfile,
    inventory: Any | None = None,
    *,
    include_health: bool = True,
) -> dict[str, Any]:
    payload = {
        "id": profile.id,
        "name": profile.name,
        "technical_name": profile.technical_name,
        "description": profile.description,
        "prompt_family": profile.prompt_family.value,
        "architecture": profile.architecture,
        "source_url": profile.source_url,
        "source_version_id": profile.source_version_id,
        "vram_min_gb": profile.vram_min_gb,
        "vram_rec_gb": profile.vram_rec_gb,
        "workflow_ready": profile.workflow_ready,
        "aspect_ratios": list(profile.aspect_ratios),
        "quality_presets": _preset_summary(profile),
    }
    if include_health:
        payload["health"] = check_profile_health(profile, inventory)
    return payload


def _set_binding(workflow: dict[str, Any], binding: dict[str, Any] | None, value: Any) -> None:
    if not binding:
        return
    node = workflow.get(str(binding.get("node")))
    if not isinstance(node, dict):
        raise KeyError(f"Workflow node {binding.get('node')} is missing")
    inputs = node.setdefault("inputs", {})
    inputs[str(binding.get("input"))] = value


def _load_bindings(profile: ApprovedProfile) -> dict[str, Any]:
    path = profile.directory / "bindings.json"
    if not path.is_file():
        raise FileNotFoundError(f"Bindings are not prepared yet for {profile.id}")
    return _read_json(path)


def _load_preset(profile: ApprovedProfile, quality: QualityPresetLevel) -> dict[str, Any]:
    path = profile.directory / "presets" / f"{quality.value}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Preset {quality.value} is missing for {profile.id}")
    return _read_json(path)


def compile_simple_workflow(
    profile: ApprovedProfile,
    *,
    positive_prompt: str,
    negative_prompt: str | None = None,
    aspect_ratio: str = "1:1",
    quality: QualityPresetLevel = QualityPresetLevel.STANDARD,
    batch_size: int = 1,
    seed: int = -1,
    custom_dir: Path | None = None,
) -> dict[str, Any]:
    del custom_dir
    if not profile.workflow_ready:
        raise FileNotFoundError(f"Workflow is still being calibrated for {profile.name}")

    workflow = copy.deepcopy(load_simple_workflow_json(profile))
    bindings = _load_bindings(profile)
    preset = _load_preset(profile, quality)

    ratio = next(
        (item for item in profile.aspect_ratios if str(item.get("ratio")) == aspect_ratio),
        profile.aspect_ratios[0] if profile.aspect_ratios else {"width": 1024, "height": 1024},
    )
    effective_seed = seed if seed >= 0 else random.randint(0, 1125899906842624)
    effective_positive = positive_prompt.strip()
    if profile.prompt_prefix and effective_positive:
        effective_positive = f"{profile.prompt_prefix}, {effective_positive}"
    effective_negative = negative_prompt if negative_prompt is not None else profile.default_negative_prompt

    _set_binding(workflow, bindings.get("positive_prompt"), effective_positive)
    _set_binding(workflow, bindings.get("negative_prompt"), effective_negative or "")
    _set_binding(workflow, bindings.get("seed"), effective_seed)
    _set_binding(workflow, bindings.get("width"), int(ratio.get("width") or 1024))
    _set_binding(workflow, bindings.get("height"), int(ratio.get("height") or 1024))
    _set_binding(workflow, bindings.get("batch_size"), max(1, min(int(batch_size), 4)))

    preset_bindings = bindings.get("preset") if isinstance(bindings.get("preset"), dict) else {}
    overrides = preset.get("overrides") if isinstance(preset.get("overrides"), dict) else {}
    for key, value in overrides.items():
        _set_binding(workflow, preset_bindings.get(key), value)

    return workflow
