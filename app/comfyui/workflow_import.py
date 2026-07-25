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
    candidates: dict[str, list[dict[str, Any]]]
    warnings: list[str]
    ready: bool

    def api_dict(self) -> dict[str, Any]:
        return {
            "source_format": self.source_format,
            "manifest": self.manifest.model_dump(mode="json"),
            "mappings": self.mappings,
            "candidates": self.candidates,
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


def analyze_api_workflow(
    filename: str,
    workflow: dict[str, Any],
    mapping_overrides: dict[str, Any] | None = None,
) -> WorkflowImportPlan:
    nodes = workflow
    mapping = mapping_overrides or {}
    samplers = _nodes_of_type(nodes, SAMPLER_NODE_TYPES)
    detected_output_nodes = [
        node_id
        for node_id, node in nodes.items()
        if node["class_type"] in IMAGE_OUTPUT_NODE_TYPES | VIDEO_OUTPUT_NODE_TYPES
        or node["class_type"].startswith("Save")
    ]
    warnings: list[str] = []
    blockers: list[str] = []
    mappings: list[dict[str, str]] = []

    sampler_id = _selected_node_id(
        mapping.get("sampler_node_id"),
        [node_id for node_id, _node in samplers],
        label="sampler",
    )
    if not samplers:
        blockers.append("No standard KSampler or KSamplerAdvanced node was found.")
    elif sampler_id is None and len(samplers) > 1:
        blockers.append(
            "Multiple sampler pipelines were found; choose their semantic roles in the mapping wizard."
        )
    elif sampler_id is None:
        sampler_id = samplers[0][0]

    selected_output_id = _selected_node_id(
        mapping.get("output_node_id"),
        detected_output_nodes,
        label="output",
    )
    if not detected_output_nodes:
        blockers.append("No supported output node was found.")
    elif selected_output_id is None and len(detected_output_nodes) > 1:
        blockers.append("Multiple output nodes were found; choose the primary output.")
    elif selected_output_id is None:
        selected_output_id = detected_output_nodes[0]
    output_nodes = [selected_output_id] if selected_output_id is not None else detected_output_nodes

    sampler = nodes.get(sampler_id or "")
    fields: list[dict[str, Any]] = []
    if sampler_id is not None and sampler is not None:
        _add_prompt_fields(
            nodes,
            sampler_id,
            sampler,
            fields,
            mappings,
            blockers,
            positive_binding=mapping.get("positive_binding"),
            negative_binding=mapping.get("negative_binding"),
        )
        _add_sampler_fields(sampler_id, sampler, fields, mappings)
        _add_latent_fields(nodes, sampler, fields, mappings)

    _add_reference_fields(nodes, fields, mappings)
    _add_output_fields(nodes, output_nodes, fields, mappings)
    prompt_candidates = _prompt_candidates(nodes)
    model_candidates = _unknown_model_inputs(nodes)
    manual_model_roles = mapping.get("model_roles") or {}
    if not isinstance(manual_model_roles, dict):
        raise ValueError("model_roles mapping must be an object")
    resource_slots, loader_family, component_policy = _resource_contract(
        nodes,
        mappings,
        manual_roles=manual_model_roles,
        allowed_manual_inputs={item["value"] for item in model_candidates},
    )
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
    _apply_field_options(fields, mapping.get("field_options"))
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
        candidates={
            "samplers": [
                _node_candidate(node_id, node, ambiguous=len(samplers) > 1)
                for node_id, node in samplers
            ],
            "prompt_inputs": prompt_candidates,
            "outputs": [
                _node_candidate(
                    node_id,
                    nodes[node_id],
                    ambiguous=len(detected_output_nodes) > 1,
                )
                for node_id in detected_output_nodes
            ],
            "model_inputs": model_candidates,
        },
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


def _selected_node_id(value: Any, available: list[str], *, label: str) -> str | None:
    if value in (None, ""):
        return None
    selected = str(value)
    if selected not in available:
        raise ValueError(f"Selected {label} node '{selected}' is not an available candidate")
    return selected


def _node_candidate(
    node_id: str, node: dict[str, Any], *, ambiguous: bool
) -> dict[str, Any]:
    return {
        "value": node_id,
        "node_id": node_id,
        "class_type": node["class_type"],
        "label": f"Node {node_id} · {node['class_type']}",
        "confidence": "ambiguous" if ambiguous else "high",
    }


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
    *,
    positive_binding: Any = None,
    negative_binding: Any = None,
) -> None:
    positive_manual = _resolve_input_binding(nodes, positive_binding, label="positive prompt")
    negative_disabled = negative_binding == "__none__"
    negative_manual = _resolve_input_binding(
        nodes,
        negative_binding,
        label="negative prompt",
    )
    positive_encoder_id = None if positive_manual else _find_prompt_encoder(
        nodes, _edge_node(sampler["inputs"].get("positive"))
    )
    negative_encoder_id = None if negative_manual or negative_disabled else _find_prompt_encoder(
        nodes, _edge_node(sampler["inputs"].get("negative"))
    )
    if positive_manual:
        _add_manual_prompt_field(
            nodes,
            fields,
            mappings,
            field_id="positive_prompt",
            label="Positive prompt",
            binding=positive_manual,
            required=True,
            advanced=False,
        )
    if positive_encoder_id is None:
        if not positive_manual:
            blockers.append(
                f"The positive input on sampler node {sampler_id} is not connected "
                "to a supported prompt encoder."
            )
    if negative_manual:
        _add_manual_prompt_field(
            nodes,
            fields,
            mappings,
            field_id="negative_prompt",
            label="What to avoid",
            binding=negative_manual,
            required=False,
            advanced=True,
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


def _resolve_input_binding(
    nodes: dict[str, Any],
    value: Any,
    *,
    label: str,
) -> tuple[str, str] | None:
    if value in (None, "", "__none__"):
        return None
    if not isinstance(value, str) or ":" not in value:
        raise ValueError(f"Selected {label} binding is invalid")
    node_id, input_name = value.split(":", 1)
    node = nodes.get(node_id)
    if node is None or input_name not in node["inputs"]:
        raise ValueError(f"Selected {label} binding '{value}' does not exist")
    current = node["inputs"][input_name]
    if not isinstance(current, str):
        raise ValueError(f"Selected {label} binding '{value}' is not a text input")
    return node_id, input_name


def _add_manual_prompt_field(
    nodes: dict[str, Any],
    fields: list[dict[str, Any]],
    mappings: list[dict[str, str]],
    *,
    field_id: str,
    label: str,
    binding: tuple[str, str],
    required: bool,
    advanced: bool,
) -> None:
    node_id, input_name = binding
    fields.append({
        "id": field_id,
        "label": label,
        "kind": "textarea",
        "section": "Prompt",
        "default": nodes[node_id]["inputs"][input_name],
        "required": required,
        "advanced": advanced,
        "bindings": [{"node_id": node_id, "input": input_name}],
    })
    mappings.append(
        _mapping(field_id, node_id, input_name, confidence="manual")
    )


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


def _prompt_candidates(nodes: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for node_id, node in nodes.items():
        class_type = node["class_type"]
        for input_name, value in node["inputs"].items():
            if not isinstance(value, str):
                continue
            if input_name not in {"text", "text_g", "text_l", "prompt"}:
                continue
            candidates.append({
                "value": f"{node_id}:{input_name}",
                "node_id": node_id,
                "input": input_name,
                "class_type": class_type,
                "label": f"Node {node_id} · {class_type}.{input_name}",
                "confidence": "candidate",
            })
    return candidates


def _known_resource_input_pairs(nodes: dict[str, Any]) -> set[tuple[str, str]]:
    known: set[tuple[str, str]] = set()
    for node_id, node in nodes.items():
        class_type = node["class_type"]
        input_names: tuple[str, ...] = ()
        if class_type in {"CheckpointLoaderSimple", "CheckpointLoader"}:
            input_names = ("ckpt_name",)
        elif class_type in {"UNETLoader", "UnetLoader", "UNETLoaderGGUF", "UnetLoaderGGUF"}:
            input_names = ("unet_name", "diffusion_model")
        elif class_type in {"CLIPLoader", "CLIPLoaderGGUF", "DualCLIPLoader", "DualCLIPLoaderGGUF"}:
            input_names = ("clip_name", "clip_name1", "clip_name2")
        elif class_type == "VAELoader":
            input_names = ("vae_name",)
        elif class_type in {"LoraLoader", "LoraLoaderModelOnly"}:
            input_names = ("lora_name",)
        known.update(
            (node_id, input_name)
            for input_name in input_names
            if input_name in node["inputs"]
        )
    return known


def _unknown_model_inputs(nodes: dict[str, Any]) -> list[dict[str, Any]]:
    known = _known_resource_input_pairs(nodes)
    candidates: list[dict[str, Any]] = []
    for node_id, node in nodes.items():
        class_type = node["class_type"]
        if "loader" not in class_type.casefold():
            continue
        for input_name, current_value in node["inputs"].items():
            if (node_id, input_name) in known or not isinstance(current_value, str):
                continue
            normalized = input_name.casefold()
            if not any(token in normalized for token in ("name", "model", "ckpt", "unet", "clip", "vae")):
                continue
            candidates.append({
                "value": f"{node_id}:{input_name}",
                "node_id": node_id,
                "input": input_name,
                "class_type": class_type,
                "current_value": current_value,
                "label": f"Node {node_id} · {class_type}.{input_name}",
                "confidence": "unknown",
            })
    return candidates


def _apply_field_options(fields: list[dict[str, Any]], value: Any) -> None:
    if value in (None, {}):
        return
    if not isinstance(value, dict):
        raise ValueError("field_options mapping must be an object")
    available = {field["id"] for field in fields}
    for field_id, options in value.items():
        if field_id not in available:
            continue
        if not isinstance(options, dict):
            raise ValueError(f"Field options for '{field_id}' must be an object")
        field = next(item for item in fields if item["id"] == field_id)
        for option in ("advanced", "hidden"):
            if option in options:
                if not isinstance(options[option], bool):
                    raise ValueError(f"Field option '{field_id}.{option}' must be boolean")
                field[option] = options[option]


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
    nodes: dict[str, Any],
    mappings: list[dict[str, str]],
    *,
    manual_roles: dict[str, Any] | None = None,
    allowed_manual_inputs: set[str] | None = None,
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

    role_contracts = {
        "checkpoint": ("checkpoint", "Checkpoint", ["checkpoint"]),
        "diffusion_model": ("diffusion_model", "Diffusion model", ["diffusion_model"]),
        "diffusion_model_gguf": (
            "diffusion_model",
            "Diffusion model (GGUF)",
            ["diffusion_model_gguf"],
        ),
        "text_encoder": ("text_encoder", "Text encoder", ["text_encoder"]),
        "text_encoder_gguf": (
            "text_encoder",
            "Text encoder (GGUF)",
            ["text_encoder_gguf"],
        ),
        "vae": ("vae", "VAE", ["vae"]),
        "lora": ("lora", "LoRA network", ["lora", "locon", "dora"]),
    }
    for binding, raw_role in (manual_roles or {}).items():
        if allowed_manual_inputs is not None and binding not in allowed_manual_inputs:
            raise ValueError(f"Manual model binding '{binding}' is not an available candidate")
        role = str(raw_role or "").strip()
        if role in {"", "ignore"}:
            continue
        contract = role_contracts.get(role)
        if contract is None:
            raise ValueError(f"Unknown manual model role '{role}'")
        node_id, input_name = binding.split(":", 1)
        slot_id, label, accepts = contract
        _add_resource_slot(
            slots,
            mappings,
            slot_id,
            label,
            accepts,
            node_id,
            input_name,
            confidence="manual",
        )
        if role == "checkpoint":
            has_checkpoint = True
        elif role in {"diffusion_model", "diffusion_model_gguf"}:
            has_diffusion = True
            has_gguf = has_gguf or role == "diffusion_model_gguf"
        elif role in {"text_encoder", "text_encoder_gguf"}:
            has_clip = True
            has_gguf = has_gguf or role == "text_encoder_gguf"
        elif role == "vae":
            has_vae = True

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
    *,
    confidence: str = "high",
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
    mappings.append(
        _mapping(
            unique_id,
            node_id,
            input_name,
            kind="resource",
            confidence=confidence,
        )
    )


def _mapping(
    semantic_id: str,
    node_id: str,
    input_name: str,
    *,
    kind: str = "field",
    confidence: str = "high",
) -> dict[str, str]:
    return {
        "kind": kind,
        "semantic_id": semantic_id,
        "node_id": node_id,
        "input": input_name,
        "confidence": confidence,
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
