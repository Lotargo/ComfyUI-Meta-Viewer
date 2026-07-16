from __future__ import annotations

import base64
import io
import json
import re
import struct
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps
Image.MAX_IMAGE_PIXELS = None
from PIL.ExifTags import TAGS

from .schemas import ImageMetadata

SUPPORTED = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


def read_png_text_chunks(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    with open(path, "rb") as f:
        sig = f.read(8)
        if sig != b"\x89PNG\r\n\x1a\n":
            return result
        while True:
            raw = f.read(8)
            if len(raw) < 8:
                break
            length = struct.unpack(">I", raw[:4])[0]
            chunk_type = raw[4:8]
            data = f.read(length)
            f.read(4)
            if chunk_type == b"tEXt":
                sep = data.find(b"\x00")
                if sep != -1:
                    key = data[:sep].decode("latin-1", errors="replace")
                    val = data[sep + 1 :].decode("latin-1", errors="replace")
                    result[key] = val
            elif chunk_type == b"iTXt":
                sep = data.find(b"\x00")
                if sep != -1:
                    key = data[:sep].decode("utf-8", errors="replace")
                    rest = data[sep + 1 :]
                    null2 = rest.find(b"\x00")
                    if null2 != -1:
                        val = rest[null2 + 1 :].decode("utf-8", errors="replace")
                        result[key] = val
    return result


def extract_exif(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {}
    try:
        img = Image.open(path)
        raw_exif = img.getexif()
        if raw_exif:
            for tag_id, val in raw_exif.items():
                tag = TAGS.get(tag_id, str(tag_id))
                if isinstance(val, bytes):
                    continue
                info[tag] = str(val)
    except Exception:
        pass
    return info


def _parse_params_text(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    text = text.strip()
    if not text:
        return result

    lines = text.split("\n")
    first_line = lines[0].strip() if lines else ""

    prompt_match = re.match(r"^(.*?)(?:\s*Negative prompt:\s*)", first_line, re.DOTALL)
    if prompt_match:
        result["positive_prompt"] = prompt_match.group(1).strip()
    else:
        neg_idx = first_line.find("Negative prompt:")
        if neg_idx >= 0:
            result["positive_prompt"] = first_line[:neg_idx].strip()
        else:
            sep = first_line.rfind(",")
            if sep > 0:
                result["positive_prompt"] = first_line[:sep].strip()
            else:
                result["positive_prompt"] = first_line

    neg_match = re.search(r"Negative prompt:\s*(.*?)(?:\s*Steps:|$)", text, re.DOTALL)
    if neg_match:
        result["negative_prompt"] = neg_match.group(1).strip()

    settings_match = re.search(r"Steps:\s*(\d+)", text)
    if settings_match:
        settings_start = settings_match.start()
        if not result.get("positive_prompt"):
            prompt_part = text[:settings_start]
            neg_split = prompt_part.rfind("Negative prompt:")
            if neg_split >= 0:
                result["positive_prompt"] = prompt_part[:neg_split].strip()
                result["negative_prompt"] = prompt_part[neg_split + len("Negative prompt:") :].strip()
            else:
                result["positive_prompt"] = prompt_part.strip()

    settings_text = text[settings_match.start():] if settings_match else text

    patterns = {
        "Steps": r"Steps:\s*(\d+)",
        "Sampler": r"Sampler:\s*([^,\n]+)",
        "Schedule": r"Schedule:\s*([^,\n]+)",
        "CFG scale": r"CFG scale:\s*([\d.]+)",
        "Seed": r"Seed:\s*(\d+)",
        "Size": r"Size:\s*(\d+x\d+)",
        "Model": r"Model:\s*([^,\n]+)",
        "Model hash": r"Model hash:\s*([a-fA-F0-9]+)",
        "Denoising strength": r"Denoising strength:\s*([\d.]+)",
        "Clip skip": r"Clip skip:\s*(\d+)",
        "ENSD": r"ENSD:\s*([\d.]+)",
        "Version": r"Version:\s*([^,\n]+)",
        "RNG": r"RNG:\s*([^,\n]+)",
        "VAE": r"VAE:\s*([^,\n]+)",
        "Lora hashes": r"Lora hashes:\s*([^,\n]+)",
    }

    settings: dict[str, Any] = {}
    for name, pat in patterns.items():
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if name in ("Steps", "Seed", "Clip skip"):
                try:
                    val = int(val)
                except ValueError:
                    pass
            elif name in ("CFG scale", "Denoising strength", "ENSD"):
                try:
                    val = float(val)
                except ValueError:
                    pass
            settings[name] = val

    if settings:
        result["generation_settings"] = settings

    return result


CLASSIFY = {
    "CheckpointLoaderSimple": "Models",
    "CheckpointLoader": "Models",
    "UNETLoader": "Models",
    "VAELoader": "Models",
    "CLIPLoader": "Models",
    "DualCLIPLoader": "Models",
    "CLIPTextEncode": "Prompts",
    "CLIPTextEncodeSDXL": "Prompts",
    "CLIPTextEncodeFlux": "Prompts",
    "CLIPTextEncodeSD3": "Prompts",
    "KSampler": "Sampler",
    "KSamplerAdvanced": "Sampler",
    "SamplerCustom": "Sampler",
    "SamplerCustomAdvanced": "Sampler",
    "BasicScheduler": "Sampler",
    "KSamplerSelect": "Sampler",
    "EmptyLatentImage": "Image Settings",
    "EmptySD3LatentImage": "Image Settings",
    "LatentUpscale": "Image Settings",
    "ImageScale": "Image Settings",
    "ImageScaleBy": "Image Settings",
    "VAEDecode": "Post Processing",
    "VAEDecodeTiled": "Post Processing",
    "VAEEncode": "Post Processing",
    "SaveImage": "Post Processing",
    "PreviewImage": "Post Processing",
    "LoraLoader": "LoRA",
    "LoraLoaderModelOnly": "LoRA",
    "ModelSamplingFlux": "Sampler",
    "FluxGuidance": "Sampler",
    "BasicGuider": "Sampler",
    "BasicCFGGuider": "Sampler",
    "RepeatLatentBatch": "Image Settings",
    "SetLatentNoiseMask": "Post Processing",
    "LatentComposite": "Post Processing",
    "LatentBatch": "Post Processing",
}

SKIP_TYPES = {"Reroute", "Primitive", "Note", "SetNode", "GetNode"}


def _parse_api_workflow(prompt_json: dict) -> dict[str, Any]:
    nodes_map: dict[str, dict] = {}
    for k, v in prompt_json.items():
        if str(k).isdigit() and isinstance(v, dict):
            nodes_map[str(k)] = v

    if not nodes_map:
        return {}

    categories: dict[str, list[dict]] = {}
    visited: set[str] = set()

    for nid, node in nodes_map.items():
        class_type = node.get("class_type", "")
        if class_type in SKIP_TYPES:
            continue
        cat = CLASSIFY.get(class_type, "Other")
        if cat == "Other" and "CLIPTextEncode" in class_type:
            cat = "Prompts"
        entry = _build_api_node_entry(nid, node, nodes_map)
        if entry:
            categories.setdefault(cat, []).append(entry)

    return {"workflow_nodes": categories}


def _build_api_node_entry(nid: str, node: dict, nodes_map: dict) -> dict[str, Any] | None:
    class_type = node.get("class_type", "Unknown")
    inputs = node.get("inputs", {})
    if not isinstance(inputs, dict):
        return None

    title = node.get("_meta", {}).get("title", class_type)
    simple_inputs: dict[str, Any] = {}

    for k, v in inputs.items():
        if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0].isdigit():
            ref_id = str(v[0])
            ref_slot = v[1]
            upstream = nodes_map.get(ref_id)
            if upstream:
                up_title = upstream.get("_meta", {}).get("title", upstream.get("class_type", "?"))
                simple_inputs[k] = f"[{up_title} #{ref_id}]"
            else:
                simple_inputs[k] = f"[#{ref_id}:{ref_slot}]"
        else:
            simple_inputs[k] = v

    return {
        "node_id": nid,
        "class_type": class_type,
        "title": title,
        "inputs": simple_inputs,
    }


def _parse_ui_workflow(workflow_json: dict) -> dict[str, Any]:
    nodes = workflow_json.get("nodes", [])
    if not nodes:
        return {}

    id_to_title: dict[str, str] = {}
    for n in nodes:
        nid = str(n.get("id", ""))
        ntype = n.get("type", "")
        widgets = n.get("widgets_values", [])
        if widgets and isinstance(widgets, list):
            id_to_title[ntype] = str(widgets[0]) if widgets[0] else ntype

    categories: dict[str, list[dict]] = {}
    for n in nodes:
        nid = str(n.get("id", ""))
        ntype = n.get("type", "")
        if ntype in SKIP_TYPES:
            continue
        cat = CLASSIFY.get(ntype, "Other")
        if cat == "Other" and "CLIPTextEncode" in ntype:
            cat = "Prompts"

        title_parts = [ntype]
        widgets = n.get("widgets_values", [])
        if widgets and isinstance(widgets, list):
            title_parts.append(str(widgets[0]) if widgets[0] else ntype)

        inputs_list = n.get("inputs", [])
        display_inputs: dict[str, Any] = {}
        if isinstance(inputs_list, list):
            for inp in inputs_list:
                if isinstance(inp, dict):
                    name = inp.get("name", "")
                    link = inp.get("link")
                    slot_type = inp.get("type", "")
                    if link is not None:
                        display_inputs[name] = f"[link:{slot_type}]"
                    else:
                        display_inputs[name] = slot_type

        if widgets and isinstance(widgets, list):
            input_defs = n.get("inputs", [])
            widget_names = []
            if isinstance(input_defs, list):
                widget_names = [i.get("name", f"widget_{idx}") for idx, i in enumerate(input_defs) if not i.get("link")]
            for idx, wval in enumerate(widgets):
                wname = widget_names[idx] if idx < len(widget_names) else f"param_{idx}"
                display_inputs[wname] = wval

        entry = {
            "node_id": nid,
            "class_type": ntype,
            "title": " / ".join(title_parts),
            "inputs": display_inputs,
        }
        categories.setdefault(cat, []).append(entry)

    return {"workflow_nodes": categories}


def parse_workflow_json(prompt_json: dict | None, workflow_json: dict | None) -> dict[str, Any]:
    result: dict[str, Any] = {}

    if prompt_json and isinstance(prompt_json, dict):
        api_result = _parse_api_workflow(prompt_json)
        if api_result:
            result.update(api_result)

    if workflow_json and isinstance(workflow_json, dict):
        if not result.get("workflow_nodes"):
            ui_result = _parse_ui_workflow(workflow_json)
            if ui_result:
                result.update(ui_result)

    return result


def extract_metadata(path: Path) -> ImageMetadata:
    meta: dict[str, Any] = {"file": path.name, "path": str(path)}

    img = Image.open(path)
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    meta["format"] = img.format
    meta["size"] = list(img.size)
    meta["mode"] = img.mode

    text_chunks: dict[str, str] = {}
    if path.suffix.lower() == ".png":
        text_chunks = read_png_text_chunks(path)

    exif = extract_exif(path)
    if exif:
        meta["exif"] = exif

    prompt_json = None
    prompt_raw = text_chunks.get("prompt", "")
    if prompt_raw:
        try:
            prompt_json = json.loads(prompt_raw)
        except (json.JSONDecodeError, TypeError):
            pass

    workflow_json = None
    workflow_raw = text_chunks.get("workflow", "")
    if workflow_raw:
        try:
            workflow_json = json.loads(workflow_raw)
        except (json.JSONDecodeError, TypeError):
            pass

    parameters_text = text_chunks.get("parameters", "")
    if parameters_text and not prompt_json:
        meta["prompt_parameters"] = _parse_params_text(parameters_text)

    if prompt_json and isinstance(prompt_json, dict):
        generated = _generate_params_from_api(prompt_json)
        if generated:
            meta["prompt_parameters"] = generated

    wf = parse_workflow_json(prompt_json, workflow_json)
    if wf:
        meta["workflow"] = wf

    if prompt_json:
        meta["prompt_api_json"] = prompt_json
    if workflow_json:
        meta["workflow_ui_json"] = workflow_json

    return ImageMetadata.model_validate(meta)


def _generate_params_from_api(prompt_json: dict) -> dict[str, Any]:
    result: dict[str, Any] = {}
    nodes: dict[str, dict] = {}
    for k, v in prompt_json.items():
        if str(k).isdigit() and isinstance(v, dict):
            nodes[str(k)] = v

    pos_roots = set()
    neg_roots = set()
    for nid, node in nodes.items():
        ct = node.get("class_type", "")
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        if "Sampler" in ct or "Guider" in ct:
            pos_link = inputs.get("positive")
            if isinstance(pos_link, list) and len(pos_link) > 0:
                pos_roots.add(str(pos_link[0]))
            neg_link = inputs.get("negative")
            if isinstance(neg_link, list) and len(neg_link) > 0:
                neg_roots.add(str(neg_link[0]))

    def get_upstream_nodes(start_nids: set[str]) -> set[str]:
        visited = set()
        queue = list(start_nids)
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            node = nodes.get(curr)
            if not node:
                continue
            inputs = node.get("inputs", {})
            if isinstance(inputs, dict):
                for val in inputs.values():
                    if isinstance(val, list) and len(val) >= 1 and str(val[0]).isdigit():
                        queue.append(str(val[0]))
        return visited

    pos_nodes = get_upstream_nodes(pos_roots)
    neg_nodes = get_upstream_nodes(neg_roots)

    positive_parts: list[str] = []
    negative_parts: list[str] = []

    for nid, node in nodes.items():
        ct = node.get("class_type", "")
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue

        if "CLIPTextEncode" in ct:
            title = node.get("_meta", {}).get("title", "").lower()
            text_val = inputs.get("text", "")
            if isinstance(text_val, str) and text_val:
                is_neg = False
                if nid in neg_nodes and nid not in pos_nodes:
                    is_neg = True
                elif nid in pos_nodes:
                    is_neg = False
                else:
                    if "negative" in title:
                        is_neg = True
                
                if is_neg:
                    negative_parts.append(text_val)
                else:
                    positive_parts.append(text_val)

        elif ct in ("KSampler", "KSamplerAdvanced"):
            for sk in ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"):
                if sk in inputs:
                    result[sk] = inputs[sk]

        elif ct in ("EmptyLatentImage", "EmptySD3LatentImage"):
            w = inputs.get("width")
            h = inputs.get("height")
            if w is not None and h is not None:
                result["size"] = f"{w}x{h}"

        elif ct in ("CheckpointLoaderSimple", "CheckpointLoader", "UNETLoader"):
            ckpt = inputs.get("ckpt_name") or inputs.get("unet_name")
            if ckpt:
                result["model"] = ckpt

        elif ct == "VAELoader":
            vae = inputs.get("vae_name")
            if vae:
                result["vae"] = vae

        elif ct in ("LoraLoader", "LoraLoaderModelOnly"):
            lora_name = inputs.get("lora_name", "")
            strength = inputs.get("strength_model", inputs.get("strength", 1.0))
            result.setdefault("loras", []).append({"name": lora_name, "strength": strength})

        elif ct == "ModelSamplingFlux":
            for k in ("max_shift", "base_shift", "width", "height"):
                if k in inputs:
                    result[k] = inputs[k]

        elif ct == "FluxGuidance":
            guidance = inputs.get("guidance")
            if guidance is not None:
                result["guidance"] = guidance

    if positive_parts:
        result["positive_prompt"] = "\n".join(positive_parts)
    if negative_parts:
        result["negative_prompt"] = "\n".join(negative_parts)

    if "steps" in result:
        result["Steps"] = result.pop("steps")
    if "seed" in result:
        result["Seed"] = result.pop("seed")
    if "cfg" in result:
        result["CFG scale"] = result.pop("cfg")
    if "sampler_name" in result:
        result["Sampler"] = result.pop("sampler_name")
    if "scheduler" in result:
        result["Schedule"] = result.pop("scheduler")
    if "denoise" in result:
        result["Denoising strength"] = result.pop("denoise")

    return result


def scan_directory(dir_path: Path) -> list[ImageMetadata]:
    results: list[ImageMetadata] = []
    files = sorted(
        f for f in dir_path.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED
    )
    for f in files:
        try:
            results.append(extract_metadata(f))
        except Exception as e:
            results.append(ImageMetadata(file=f.name, path=str(f), error=str(e)))
    return results


def scan_paths(paths: list[str]) -> list[ImageMetadata]:
    results: list[ImageMetadata] = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            results.extend(scan_directory(pp))
        elif pp.is_file() and pp.suffix.lower() in SUPPORTED:
            try:
                results.append(extract_metadata(pp))
            except Exception as e:
                results.append(ImageMetadata(file=pp.name, path=str(pp), error=str(e)))
    return results


def _thumbnail_image(path: str | Path, max_size: int = 1024) -> tuple[bytes, str] | None:
    try:
        img = Image.open(str(path))
        img = ImageOps.exif_transpose(img)
        img.thumbnail((max_size, max_size))
        buf = io.BytesIO()
        fmt = "JPEG" if img.mode == "RGB" else "PNG"
        if img.mode in ("RGBA", "P", "LA"):
            fmt = "PNG"
        if img.mode not in ("RGB", "RGBA", "L", "P", "LA"):
            img = img.convert("RGB")
            fmt = "JPEG"
        img.save(buf, format=fmt, quality=90)
        return buf.getvalue(), fmt.lower()
    except Exception:
        return None


def make_thumbnail_b64(path: str | Path, max_size: int = 1024) -> str | None:
    result = _thumbnail_image(path, max_size)
    if result is None:
        return None
    data, fmt = result
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/{fmt};base64,{b64}"


def make_thumbnail_bytes(path: str | Path, max_size: int = 1024) -> bytes | None:
    result = _thumbnail_image(path, max_size)
    if result is None:
        return None
    data, _ = result
    return data


def make_thumbnail_bytes_from_bytes(data: bytes, max_size: int = 1024) -> bytes | None:
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        img.thumbnail((max_size, max_size))
        buf = io.BytesIO()
        fmt = "JPEG" if img.mode == "RGB" else "PNG"
        if img.mode in ("RGBA", "P", "LA"):
            fmt = "PNG"
        if img.mode not in ("RGB", "RGBA", "L", "P", "LA"):
            img = img.convert("RGB")
            fmt = "JPEG"
        img.save(buf, format=fmt, quality=90)
        return buf.getvalue()
    except Exception:
        return None
