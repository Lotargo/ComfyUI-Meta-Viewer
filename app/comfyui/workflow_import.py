from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .sampling_options import CORE_SAMPLER_OPTIONS, CORE_SCHEDULER_OPTIONS
from .workflow_models import WorkflowTemplateManifest


SAMPLER_NODE_TYPES = {"KSampler", "KSamplerAdvanced"}
IMAGE_OUTPUT_NODE_TYPES = {"SaveImage", "PreviewImage"}
VIDEO_OUTPUT_NODE_TYPES = {
    "SaveAnimatedPNG",
    "SaveAnimatedWEBP",
    "VHS_VideoCombine",
}


@dataclass(frozen=True)
class WorkflowImportPlan:
    source_format: str
    manifest: WorkflowTemplateManifest
    workflow: dict[str, Any]
    mappings: list[dict[str, str]]
    warnings: list[str]
    ready: bool

    def api_dict(self) -> dict[str, Any]:
        return {
            "source_format": self.source_format,
            "manifest": self.manifest.model_dump(mode="json"),
            "mappings": self.mappings,
            "warnings": self.warnings,
            "ready": self.ready,
        }


def is_api_workflow(payload: Any) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False
    return all(
        isinstance(node_id, str)
        and isinstance(node, dict)
        and isinstance(node.get("class_type"), str)
        and isinstance(node.get("inputs"), dict)
        for node_id, node in payload.items()
    )


def unwrap_api_workflow(payload: Any) -> dict[str, Any] | None:
    if is_api_workflow(payload):
        return payload
    if not isinstance(payload, dict):
        return None
    for key in ("prompt", "workflow", "workflow_data"):
        candidate = payload.get(key)
        if is_api_workflow(candidate):
            return candidate
    return None


def analyze_api_workflow(filename: str, workflow: dict[str, Any]) -> WorkflowImportPlan:
    nodes = workflow
    samplers = _nodes_of_type(nodes, SAMPLER_NODE_TYPES)
    output_nodes = [
        node_id
        for node_id, node in nodes.items()
        if node["class_type"] in IMAGE_OUTPUT_NODE_TYPES | VIDEO_OUTPUT_NODE_TYPES
        or node["class_type"].startswith("Save")
    ]
    warnings: list[str] = []
    blockers: list[str] = []
    mappings: list[dict[str, str]] = []

    if not samplers:
        blockers.append("No standard KSampler or KSamplerAdvanced node was found.")
    elif len(samplers) > 1:
        blockers.append(
            "Multiple sampler pipelines were found; choose their semantic roles in the mapping wizard."
        )
    if not output_nodes:
        blockers.append("No supported output node was found.")

    sampler_id, sampler = samplers[0] if samplers else (None, None)
    fields: list[dict[str, Any]] = []
    if sampler_id is not None and sampler is not None:
        _add_prompt_fields(nodes, sampler_id, sampler, fields, mappings, blockers)
        _add_sampler_fields(sampler_id, sampler, fields, mappings)
        _add_latent_fields(nodes, sampler, fields, mappings)

    _add_reference_fields(nodes, fields, mappings)
    _add_output_fields(nodes, output_nodes, fields, mappings)
    resource_slots, loader_family, component_policy = _resource_contract(nodes, mappings)
    if loader_family == "custom":
        blockers.append(
            "No standard checkpoint or diffusion-model loader was found."
        )

    media_type = "video" if any(
        nodes[node_id]["class_type"] in VIDEO_OUTPUT_NODE_TYPES for node_id in output_nodes
    ) else "image"
    if media_type == "video":
        category = "video"
    elif any(node["class_type"] == "LoadImage" for node in nodes.values()):
        category = "reference"
    elif len(samplers) > 1:
        category = "advanced"
    else:
        category = "simple"

    template_id, template_name = _template_identity(filename)
    if blockers:
        warnings.extend(blockers)
    manifest = WorkflowTemplateManifest.model_validate({
        "schema_version": "2",
        "id": template_id,
        "name": template_name,
        "version": "1.0.0",
        "category": category,
        "media_type": media_type,
        "supported_ecosystems": ["other"],
        "loader_family": loader_family,
        "component_policy": component_policy,
        "workflow": "workflow.json",
        "description": "Imported from a ComfyUI API workflow.",
        "capability_notes": [
            "Standard semantic bindings were detected from graph connections and node inputs."
        ],
        "limitation_notes": [
            "Model ecosystem is unknown until the imported template is reviewed."
        ],
        "required_nodes": list(dict.fromkeys(node["class_type"] for node in nodes.values())),
        "resource_slots": resource_slots,
        "fields": fields,
        "output_nodes": output_nodes or [next(iter(nodes))],
    })
    return WorkflowImportPlan(
        source_format="api_workflow",
        manifest=manifest,
        workflow=workflow,
        mappings=mappings,
        warnings=warnings,
        ready=not blockers,
    )


def _nodes_of_type(
    nodes: dict[str, Any], class_types: set[str]
) -> list[tuple[str, dict[str, Any]]]:
    return [
        (node_id, node)
        for node_id, node in nodes.items()
        if node["class_type"] in class_types
    ]


def _edge_node(value: Any) -> str | None:
    if (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], (str, int))
        and isinstance(value[1], int)
    ):
        return str(value[0])
    return None


def _add_prompt_fields(
    nodes: dict[str, Any],
    sampler_id: str,
    sampler: dict[str, Any],
    fields: list[dict[str, Any]],
    mappings: list[dict[str, str]],
    blockers: list[str],
) -> None:
    positive_encoder_id = _find_prompt_encoder(
        nodes, _edge_node(sampler["inputs"].get("positive"))
    )
    negative_encoder_id = _find_prompt_encoder(
        nodes, _edge_node(sampler["inputs"].get("negative"))
    )
    if positive_encoder_id is None:
        blockers.append(
            f"The positive input on sampler node {sampler_id} is not connected "
            "to a supported prompt encoder."
        )
    encoders = [
        ("positive_prompt", "Positive prompt", positive_encoder_id, False),
        ("negative_prompt", "What to avoid", negative_encoder_id, True),
    ]
    for field_id, label, encoder_id, advanced in encoders:
        if encoder_id is None:
            continue
        if field_id == "negative_prompt" and encoder_id == positive_encoder_id:
            continue
        encoder = nodes[encoder_id]
        input_names = [
            input_name
            for input_name in ("text", "text_g", "text_l")
            if input_name in encoder["inputs"]
        ]
        if not input_names:
            if field_id == "positive_prompt":
                blockers.append(
                    f"Prompt encoder node {encoder_id} has no supported text input."
                )
            continue
        text_value = encoder["inputs"].get(input_names[0], "")
        bindings = [{"node_id": encoder_id, "input": input_name} for input_name in input_names]
        fields.append({
            "id": field_id,
            "label": label,
            "kind": "textarea",
            "section": "Prompt",
            "default": text_value if isinstance(text_value, str) else "",
            "required": field_id == "positive_prompt",
            "advanced": advanced,
            "bindings": bindings,
        })
        mappings.extend(_mapping(field_id, encoder_id, input_name) for input_name in input_names)


def _find_prompt_encoder(
    nodes: dict[str, Any], start_node_id: str | None
) -> str | None:
    if start_node_id is None:
        return None
    pending = [start_node_id]
    visited: set[str] = set()
    matches: list[str] = []
    while pending:
        node_id = pending.pop(0)
        if node_id in visited:
            continue
        visited.add(node_id)
        node = nodes.get(node_id)
        if not node:
            continue
        if node["class_type"] in {"CLIPTextEncode", "CLIPTextEncodeSDXL"}:
            matches.append(node_id)
            continue
        pending.extend(
            source_id
            for value in node["inputs"].values()
            if (source_id := _edge_node(value)) is not None
        )
    return matches[0] if len(matches) == 1 else None


def _add_sampler_fields(
    sampler_id: str,
    sampler: dict[str, Any],
    fields: list[dict[str, Any]],
    mappings: list[dict[str, str]],
) -> None:
    inputs = sampler["inputs"]
    specifications = (
        ("seed", "Seed", "seed" if "seed" in inputs else "noise_seed", "seed", -1, 1125899906842624, 1),
        ("steps", "Quality steps", "steps", "number", 1, 200, 1),
        ("cfg", "Prompt strength (CFG)", "cfg", "number", 0, 30, 0.1),
        ("denoise", "Denoise", "denoise", "number", 0, 1, 0.01),
    )
    for field_id, label, input_name, kind, minimum, maximum, step in specifications:
        value = inputs.get(input_name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            fields.append({
                "id": field_id,
                "label": label,
                "kind": kind,
                "section": "Sampling",
                "default": value,
                "minimum": minimum,
                "maximum": maximum,
                "step": step,
                "advanced": True,
                "bindings": [{"node_id": sampler_id, "input": input_name}],
            })
            mappings.append(_mapping(field_id, sampler_id, input_name))

    for field_id, label, input_name, options in (
        ("sampler", "Sampling method", "sampler_name", CORE_SAMPLER_OPTIONS),
        ("scheduler", "Sampling schedule", "scheduler", CORE_SCHEDULER_OPTIONS),
    ):
        value = inputs.get(input_name)
        if not isinstance(value, str):
            continue
        known_options = [{"value": item, "label": option_label} for item, option_label in options]
        if value not in {option["value"] for option in known_options}:
            known_options.insert(0, {"value": value, "label": value})
        fields.append({
            "id": field_id,
            "label": label,
            "kind": "select",
            "section": "Sampling",
            "default": value,
            "advanced": True,
            "options": known_options,
            "bindings": [{"node_id": sampler_id, "input": input_name}],
        })
        mappings.append(_mapping(field_id, sampler_id, input_name))


def _add_latent_fields(
    nodes: dict[str, Any],
    sampler: dict[str, Any],
    fields: list[dict[str, Any]],
    mappings: list[dict[str, str]],
) -> None:
    latent_id = _edge_node(sampler["inputs"].get("latent_image"))
    latent = nodes.get(latent_id or "")
    if not latent or latent.get("class_type") not in {
        "EmptyLatentImage",
        "EmptySD3LatentImage",
    }:
        return
    for field_id, label, minimum, maximum, step in (
        ("width", "Width", 64, 8192, 8),
        ("height", "Height", 64, 8192, 8),
        ("batch_size", "Batch size", 1, 16, 1),
    ):
        value = latent["inputs"].get(field_id)
        if not isinstance(value, int) or isinstance(value, bool):
            continue
        fields.append({
            "id": field_id,
            "label": label,
            "kind": "number",
            "section": "Image",
            "default": value,
            "minimum": minimum,
            "maximum": maximum,
            "step": step,
            "advanced": True,
            "bindings": [{"node_id": latent_id, "input": field_id}],
        })
        mappings.append(_mapping(field_id, latent_id, field_id))


def _add_reference_fields(
    nodes: dict[str, Any],
    fields: list[dict[str, Any]],
    mappings: list[dict[str, str]],
) -> None:
    loaders = _nodes_of_type(nodes, {"LoadImage"})
    if len(loaders) != 1:
        return
    node_id, node = loaders[0]
    value = node["inputs"].get("image", "")
    fields.append({
        "id": "reference_image",
        "label": "Reference image",
        "kind": "image",
        "section": "Reference",
        "default": value if isinstance(value, str) else "",
        "required": True,
        "bindings": [{"node_id": node_id, "input": "image"}],
    })
    mappings.append(_mapping("reference_image", node_id, "image"))


def _add_output_fields(
    nodes: dict[str, Any],
    output_nodes: list[str],
    fields: list[dict[str, Any]],
    mappings: list[dict[str, str]],
) -> None:
    if len(output_nodes) != 1:
        return
    node_id = output_nodes[0]
    value = nodes[node_id]["inputs"].get("filename_prefix")
    if not isinstance(value, str):
        return
    fields.append({
        "id": "filename_prefix",
        "label": "Filename prefix",
        "kind": "text",
        "section": "Output",
        "default": value,
        "advanced": True,
        "bindings": [{"node_id": node_id, "input": "filename_prefix"}],
    })
    mappings.append(_mapping("filename_prefix", node_id, "filename_prefix"))


def _resource_contract(
    nodes: dict[str, Any], mappings: list[dict[str, str]]
) -> tuple[dict[str, Any], str, dict[str, str]]:
    slots: dict[str, Any] = {}
    has_checkpoint = False
    has_diffusion = False
    has_gguf = False
    has_clip = False
    has_vae = False

    for node_id, node in nodes.items():
        class_type = node["class_type"]
        inputs = node["inputs"]
        if class_type in {"CheckpointLoaderSimple", "CheckpointLoader"} and "ckpt_name" in inputs:
            has_checkpoint = True
            _add_resource_slot(slots, mappings, "checkpoint", "Checkpoint", ["checkpoint"], node_id, "ckpt_name")
        elif class_type in {"UNETLoader", "UnetLoader", "UNETLoaderGGUF", "UnetLoaderGGUF"}:
            input_name = "unet_name" if "unet_name" in inputs else "diffusion_model"
            if input_name not in inputs:
                continue
            has_diffusion = True
            is_gguf = "gguf" in class_type.casefold() or str(inputs[input_name]).casefold().endswith(".gguf")
            has_gguf = has_gguf or is_gguf
            accepts = ["diffusion_model_gguf"] if is_gguf else ["diffusion_model"]
            _add_resource_slot(slots, mappings, "diffusion_model", "Diffusion model", accepts, node_id, input_name)
        elif class_type in {"CLIPLoader", "CLIPLoaderGGUF", "DualCLIPLoader", "DualCLIPLoaderGGUF"}:
            has_clip = True
            for input_name in ("clip_name", "clip_name1", "clip_name2"):
                if input_name not in inputs:
                    continue
                value = str(inputs[input_name])
                is_gguf = "gguf" in class_type.casefold() or value.casefold().endswith(".gguf")
                has_gguf = has_gguf or is_gguf
                slot_id = "text_encoder" if input_name == "clip_name" else input_name
                accepts = ["text_encoder_gguf"] if is_gguf else ["text_encoder"]
                _add_resource_slot(slots, mappings, slot_id, "Text encoder", accepts, node_id, input_name)
        elif class_type == "VAELoader" and "vae_name" in inputs:
            has_vae = True
            _add_resource_slot(slots, mappings, "vae", "VAE", ["vae"], node_id, "vae_name")
        elif class_type in {"LoraLoader", "LoraLoaderModelOnly"} and "lora_name" in inputs:
            _add_resource_slot(
                slots,
                mappings,
                "lora",
                "LoRA network",
                ["lora", "locon", "dora"],
                node_id,
                "lora_name",
            )

    if has_checkpoint and has_diffusion:
        family = "hybrid"
    elif has_checkpoint:
        family = "checkpoint"
    elif has_gguf:
        family = "gguf"
    elif has_diffusion:
        family = "separate_components"
    else:
        family = "custom"
    return slots, family, {
        "clip": "required" if has_clip else "embedded",
        "vae": "required" if has_vae else "embedded",
    }


def _add_resource_slot(
    slots: dict[str, Any],
    mappings: list[dict[str, str]],
    slot_id: str,
    label: str,
    accepts: list[str],
    node_id: str,
    input_name: str,
) -> None:
    unique_id = slot_id
    suffix = 2
    while unique_id in slots:
        unique_id = f"{slot_id}_{suffix}"
        suffix += 1
    slots[unique_id] = {
        "label": label,
        "accepts": accepts,
        "required": True,
        "binding": {"kind": "node_input", "node_id": node_id, "input": input_name},
    }
    mappings.append(_mapping(unique_id, node_id, input_name, kind="resource"))


def _mapping(
    semantic_id: str, node_id: str, input_name: str, *, kind: str = "field"
) -> dict[str, str]:
    return {
        "kind": kind,
        "semantic_id": semantic_id,
        "node_id": node_id,
        "input": input_name,
        "confidence": "high",
    }


def _template_identity(filename: str) -> tuple[str, str]:
    stem = Path(filename or "imported-workflow.json").stem
    name = re.sub(r"[_-]+", " ", stem).strip() or "Imported workflow"
    name = name[:160]
    ascii_stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    template_id = re.sub(r"[^a-z0-9]+", "-", ascii_stem.casefold()).strip("-")
    if not template_id or not template_id[0].isalpha():
        template_id = f"imported-{template_id}" if template_id else "imported-workflow"
    if len(template_id) < 2:
        template_id += "-workflow"
    return template_id[:80].rstrip("-"), name


__all__ = [
    "WorkflowImportPlan",
    "analyze_api_workflow",
    "is_api_workflow",
    "unwrap_api_workflow",
]
