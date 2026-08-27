from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from app.ai.prompting import PromptFamily
from app.ai.resources import ResourceType
from app.config_store import ConfigStore

logger = logging.getLogger(__name__)

SIMPLE_WORKFLOWS_DIR = Path(__file__).parent / "simple_workflows"


class QualityPresetLevel(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    HIGH = "high"
    MAXIMUM = "maximum"


@dataclass(frozen=True)
class QualityPreset:
    steps: int
    cfg: float
    sampler_name: str
    scheduler: str
    guidance: float = 3.5
    denoise: float = 1.0


@dataclass(frozen=True)
class AspectRatioOption:
    ratio: str
    width: int
    height: int
    label: str


@dataclass(frozen=True)
class ProfileExample:
    title: str
    prompt: str
    image_url: str


@dataclass(frozen=True)
class ProfileResourceDependency:
    resource_type: ResourceType
    folder: str
    filename: str
    display_name: str
    download_url: str | None = None
    civitai_model_id: int | None = None
    civitai_version_id: int | None = None


@dataclass
class ApprovedProfile:
    id: str
    name: str
    tagline: str
    description: str
    strengths: list[str]
    weaknesses: list[str]
    vram_min_gb: float
    vram_rec_gb: float
    technical_model: str
    prompt_family: PromptFamily
    flow_id: str  # e.g. "sdxl_pony" or "flux"
    default_negative_prompt: str | None
    quality_presets: dict[QualityPresetLevel, QualityPreset]
    aspect_ratios: list[AspectRatioOption]
    examples: list[ProfileExample] = field(default_factory=list)
    required_resources: list[ProfileResourceDependency] = field(default_factory=list)


# Curated Approved Profiles
APPROVED_PROFILES: dict[str, ApprovedProfile] = {
    "realism": ApprovedProfile(
        id="realism",
        name="Realism",
        tagline="Photorealistic & cinematic rendering",
        description="Optimized for true-to-life photographic portraits, cinematic lighting, natural textures, and realistic environmental scenes.",
        strengths=[
            "Lifelike human portraits and natural skin tones",
            "Authentic camera optics, depth of field, and bokeh",
            "Cinematic atmosphere and architectural details",
        ],
        weaknesses=[
            "Complex typography and precise in-image text",
            "Highly stylized or 2D cel-shaded artwork",
        ],
        vram_min_gb=6.0,
        vram_rec_gb=12.0,
        technical_model="SDXL 1.0 Photorealism Checkpoint",
        prompt_family=PromptFamily.SDXL,
        flow_id="sdxl_pony",
        default_negative_prompt="ugly, deformed, disfigured, blurry, bad anatomy, low quality, artifacts, watermark",
        quality_presets={
            QualityPresetLevel.FAST: QualityPreset(steps=18, cfg=5.5, sampler_name="euler", scheduler="normal"),
            QualityPresetLevel.STANDARD: QualityPreset(steps=25, cfg=6.5, sampler_name="euler_ancestral", scheduler="karras"),
            QualityPresetLevel.HIGH: QualityPreset(steps=35, cfg=7.0, sampler_name="dpmpp_2m_sde", scheduler="karras"),
            QualityPresetLevel.MAXIMUM: QualityPreset(steps=50, cfg=7.5, sampler_name="dpmpp_3m_sde", scheduler="karras"),
        },
        aspect_ratios=[
            AspectRatioOption(ratio="1:1", width=1024, height=1024, label="Square (1:1)"),
            AspectRatioOption(ratio="3:4", width=896, height=1152, label="Portrait (3:4)"),
            AspectRatioOption(ratio="4:3", width=1152, height=896, label="Landscape (4:3)"),
            AspectRatioOption(ratio="9:16", width=704, height=1216, label="Story / Reel (9:16)"),
            AspectRatioOption(ratio="16:9", width=1216, height=704, label="Widescreen (16:9)"),
        ],
        examples=[
            ProfileExample(
                title="Cinematic Portrait",
                prompt="Close-up portrait of a woman in rainy neon city lights, dramatic reflections, natural skin texture, 85mm f/1.4 lens",
                image_url="/static/assets/examples/realism_portrait.jpg",
            ),
            ProfileExample(
                title="Nordic Landscape",
                prompt="Misty mountain valley in Norway at dawn, pine trees, morning fog over glacial lake, cinematic light rays",
                image_url="/static/assets/examples/realism_landscape.jpg",
            ),
        ],
        required_resources=[
            ProfileResourceDependency(
                resource_type=ResourceType.CHECKPOINT,
                folder="checkpoints",
                filename="v1-5-pruned-emaonly.safetensors",
                display_name="SDXL Base Model",
            )
        ],
    ),
    "anime": ApprovedProfile(
        id="anime",
        name="Anime",
        tagline="Stylized anime and vibrant character art",
        description="Tailored for expressive anime illustrations, high-detail character designs, clean line art, and vibrant modern aesthetic styles.",
        strengths=[
            "Expressive character facial features, hair rendering, and dynamic poses",
            "Clean line art and stylized illustrative coloring",
            "Broad aesthetic coverage from retro 90s to modern visual novel styles",
        ],
        weaknesses=[
            "Strict photorealism and live-action textures",
            "Messy non-illustrative concepts",
        ],
        vram_min_gb=6.0,
        vram_rec_gb=10.0,
        technical_model="Pony Diffusion V6 / Illustrious Anime",
        prompt_family=PromptFamily.PONY,
        flow_id="sdxl_pony",
        default_negative_prompt="score_4, score_5, score_6, source_furry, low quality, bad hands, missing limbs, monochrome",
        quality_presets={
            QualityPresetLevel.FAST: QualityPreset(steps=20, cfg=6.0, sampler_name="euler_ancestral", scheduler="normal"),
            QualityPresetLevel.STANDARD: QualityPreset(steps=28, cfg=7.0, sampler_name="euler_ancestral", scheduler="karras"),
            QualityPresetLevel.HIGH: QualityPreset(steps=38, cfg=7.5, sampler_name="dpmpp_2m_sde", scheduler="karras"),
            QualityPresetLevel.MAXIMUM: QualityPreset(steps=50, cfg=8.0, sampler_name="dpmpp_2m_sde", scheduler="karras"),
        },
        aspect_ratios=[
            AspectRatioOption(ratio="1:1", width=1024, height=1024, label="Square (1:1)"),
            AspectRatioOption(ratio="3:4", width=896, height=1152, label="Portrait (3:4)"),
            AspectRatioOption(ratio="4:3", width=1152, height=896, label="Landscape (4:3)"),
            AspectRatioOption(ratio="9:16", width=704, height=1216, label="Wallpaper (9:16)"),
            AspectRatioOption(ratio="16:9", width=1216, height=704, label="Cinematic (16:9)"),
        ],
        examples=[
            ProfileExample(
                title="Anime Magician",
                prompt="score_9, score_8_up, anime girl wizard with luminous staff, glowing magical runes, starry night sky, cherry blossoms",
                image_url="/static/assets/examples/anime_wizard.jpg",
            ),
        ],
        required_resources=[
            ProfileResourceDependency(
                resource_type=ResourceType.CHECKPOINT,
                folder="checkpoints",
                filename="v1-5-pruned-emaonly.safetensors",
                display_name="Anime Checkpoint",
            )
        ],
    ),
    "universal": ApprovedProfile(
        id="universal",
        name="Universal",
        tagline="State-of-the-art general-purpose image generation",
        description="Powered by Flux.1 architecture for exceptional prompt adherence, complex multi-subject scenes, and legible text rendering.",
        strengths=[
            "Exceptional natural language prompt comprehension",
            "Accurate in-image text and typography rendering",
            "Complex multi-element scene compositions and diverse aesthetics",
        ],
        weaknesses=[
            "Higher VRAM requirement for fast execution",
            "Slower sampling on legacy GPUs",
        ],
        vram_min_gb=12.0,
        vram_rec_gb=16.0,
        technical_model="Flux.1 [dev] / Schnell Component Pipeline",
        prompt_family=PromptFamily.FLUX,
        flow_id="flux",
        default_negative_prompt=None,
        quality_presets={
            QualityPresetLevel.FAST: QualityPreset(steps=15, cfg=1.0, sampler_name="euler", scheduler="simple", guidance=3.0),
            QualityPresetLevel.STANDARD: QualityPreset(steps=28, cfg=1.0, sampler_name="euler", scheduler="simple", guidance=3.5),
            QualityPresetLevel.HIGH: QualityPreset(steps=40, cfg=1.0, sampler_name="euler", scheduler="simple", guidance=4.0),
            QualityPresetLevel.MAXIMUM: QualityPreset(steps=55, cfg=1.0, sampler_name="euler", scheduler="simple", guidance=4.5),
        },
        aspect_ratios=[
            AspectRatioOption(ratio="1:1", width=1024, height=1024, label="Square (1:1)"),
            AspectRatioOption(ratio="3:4", width=896, height=1152, label="Portrait (3:4)"),
            AspectRatioOption(ratio="4:3", width=1152, height=896, label="Landscape (4:3)"),
            AspectRatioOption(ratio="9:16", width=704, height=1216, label="Mobile (9:16)"),
            AspectRatioOption(ratio="16:9", width=1216, height=704, label="Cinema (16:9)"),
        ],
        examples=[
            ProfileExample(
                title="Futuristic City Signage",
                prompt="A cybernetic barista serving coffee in a glass cafe with neon signage spelling 'ANTIGRAVITY', photorealistic, 8k",
                image_url="/static/assets/examples/flux_cafe.jpg",
            ),
        ],
        required_resources=[
            ProfileResourceDependency(
                resource_type=ResourceType.DIFFUSION_MODEL,
                folder="diffusion_models",
                filename="flux1-dev.safetensors",
                display_name="Flux.1 Diffusion Model",
            ),
            ProfileResourceDependency(
                resource_type=ResourceType.TEXT_ENCODER,
                folder="text_encoders",
                filename="clip_l.safetensors",
                display_name="CLIP-L Encoder",
            ),
            ProfileResourceDependency(
                resource_type=ResourceType.TEXT_ENCODER,
                folder="text_encoders",
                filename="t5xxl_fp16.safetensors",
                display_name="T5XXL Encoder",
            ),
            ProfileResourceDependency(
                resource_type=ResourceType.VAE,
                folder="vae",
                filename="ae.safetensors",
                display_name="Flux VAE",
            ),
        ],
    ),
}


def get_simple_workflow_path(flow_id: str, custom_dir: Path | None = None) -> Path:
    """Resolve the workflow.json path for a flow ID."""
    base_dir = custom_dir or SIMPLE_WORKFLOWS_DIR
    flow_path = base_dir / flow_id / "workflow.json"
    if not flow_path.is_file():
        # Check flat structure fallback (e.g. simple_workflows/sdxl_pony.json)
        flat_path = base_dir / f"{flow_id}.json"
        if flat_path.is_file():
            return flat_path
    return flow_path


def load_simple_workflow_json(flow_id: str, custom_dir: Path | None = None) -> dict[str, Any]:
    """Load the ComfyUI workflow graph JSON for a flow ID."""
    path = get_simple_workflow_path(flow_id, custom_dir)
    if not path.is_file():
        raise FileNotFoundError(f"Simple Mode workflow not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_profile_health(
    profile: ApprovedProfile,
    inventory: Any | None = None,
) -> dict[str, Any]:
    """Check health and installation status of an approved profile."""
    if not inventory or not hasattr(inventory, "models"):
        return {
            "status": "ready",
            "missing_resources": [],
            "message": "Ready to generate",
        }

    missing: list[dict[str, Any]] = []
    for dep in profile.required_resources:
        available_files = inventory.models.get(dep.folder, [])
        # Check if the exact filename or any matching model exists in the target folder
        found = any(
            f.casefold() == dep.filename.casefold() or dep.filename.casefold() in f.casefold()
            for f in available_files
        )
        if not found:
            missing.append({
                "resource_type": dep.resource_type.value,
                "folder": dep.folder,
                "filename": dep.filename,
                "display_name": dep.display_name,
                "download_url": dep.download_url,
            })

    if not missing:
        return {
            "status": "ready",
            "missing_resources": [],
            "message": "Ready to generate",
        }

    return {
        "status": "ready" if not missing else "not_installed",
        "missing_resources": missing,
        "message": f"Missing {len(missing)} resource(s)" if missing else "Ready",
    }


def serialize_approved_profile(
    profile: ApprovedProfile,
    inventory: Any | None = None,
) -> dict[str, Any]:
    """Serialize approved profile for frontend UI."""
    health = check_profile_health(profile, inventory)
    return {
        "id": profile.id,
        "name": profile.name,
        "tagline": profile.tagline,
        "description": profile.description,
        "strengths": profile.strengths,
        "weaknesses": profile.weaknesses,
        "vram_min_gb": profile.vram_min_gb,
        "vram_rec_gb": profile.vram_rec_gb,
        "technical_model": profile.technical_model,
        "prompt_family": profile.prompt_family.value,
        "flow_id": profile.flow_id,
        "default_negative_prompt": profile.default_negative_prompt,
        "quality_presets": {
            k.value: {
                "steps": v.steps,
                "cfg": v.cfg,
                "sampler_name": v.sampler_name,
                "scheduler": v.scheduler,
                "guidance": v.guidance,
            }
            for k, v in profile.quality_presets.items()
        },
        "aspect_ratios": [
            {
                "ratio": ar.ratio,
                "width": ar.width,
                "height": ar.height,
                "label": ar.label,
            }
            for ar in profile.aspect_ratios
        ],
        "examples": [
            {
                "title": ex.title,
                "prompt": ex.prompt,
                "image_url": ex.image_url,
            }
            for ex in profile.examples
        ],
        "health": health,
    }


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
    """
    Compile a ready-to-run ComfyUI API workflow graph for the specified profile and parameters.
    """
    workflow = load_simple_workflow_json(profile.flow_id, custom_dir)
    preset = profile.quality_presets.get(quality, profile.quality_presets[QualityPresetLevel.STANDARD])

    # Find aspect ratio dimensions
    width, height = 1024, 1024
    for opt in profile.aspect_ratios:
        if opt.ratio == aspect_ratio:
            width, height = opt.width, opt.height
            break

    import random
    effective_seed = seed if seed >= 0 else random.randint(0, 1125899906842624)
    effective_negative = negative_prompt or profile.default_negative_prompt or ""

    # Inject values based on standard node conventions or flow structure
    for node_id, node in workflow.items():
        class_type = node.get("class_type", "")
        inputs = node.get("inputs", {})

        # KSampler node
        if class_type in {"KSampler", "KSamplerAdvanced"}:
            if "steps" in inputs:
                inputs["steps"] = preset.steps
            if "cfg" in inputs:
                inputs["cfg"] = preset.cfg
            if "sampler_name" in inputs:
                inputs["sampler_name"] = preset.sampler_name
            if "scheduler" in inputs:
                inputs["scheduler"] = preset.scheduler
            if "seed" in inputs:
                inputs["seed"] = effective_seed

        # Latent image dimensions
        elif class_type in {"EmptyLatentImage", "EmptySD3LatentImage"}:
            if "width" in inputs:
                inputs["width"] = width
            if "height" in inputs:
                inputs["height"] = height
            if "batch_size" in inputs:
                inputs["batch_size"] = max(1, min(batch_size, 4))

        # Flux Guidance
        elif class_type == "FluxGuidance":
            if "guidance" in inputs:
                inputs["guidance"] = preset.guidance

        # Text encoders
        elif class_type == "CLIPTextEncode":
            # If there are multiple text encoders, check context / node mapping
            # In SDXL/Pony flow: node 6 is positive, node 7 is negative
            if node_id == "6" or "positive" in str(inputs.get("text", "")).lower() or node_id == "3":
                inputs["text"] = positive_prompt
            elif node_id == "7" or "negative" in str(inputs.get("text", "")).lower():
                inputs["text"] = effective_negative

    return workflow
