from __future__ import annotations

import base64
import io
import json
import re
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps
Image.MAX_IMAGE_PIXELS = None
from PIL.ExifTags import TAGS

from .schemas import ImageMetadata

SUPPORTED = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
PNG_METADATA_KEYS = {b"parameters", b"prompt", b"workflow"}
JPEG_METADATA_MARKERS = {0xE1, 0xED, 0xFE}  # APP1 (EXIF/XMP), APP13, COM
WEBP_METADATA_CHUNKS = {b"EXIF", b"XMP ", b"META"}
EXIF_TEXT_TAGS = {
    "ImageDescription",
    "UserComment",
    "XPTitle",
    "XPComment",
    "XPSubject",
    "XMLPacket",
}


def _payload_has_generation_markers(payload: bytes) -> bool:
    """Recognize common generation metadata without parsing image pixels."""
    normalized = payload.replace(b"\x00", b"").lower()

    # ComfyUI API prompt and UI workflow JSON.
    if b'"class_type"' in normalized and b'"inputs"' in normalized:
        return True
    if b'"nodes"' in normalized and (
        b'"links"' in normalized or b'"last_node_id"' in normalized
    ):
        return True

    # Automatic1111/Fooocus-style parameter strings.
    settings_markers = (
        b"negative prompt:",
        b"steps:",
        b"sampler:",
        b"cfg scale:",
        b"seed:",
        b"size:",
        b"model hash:",
        b"denoising strength:",
    )
    if sum(marker in normalized for marker in settings_markers) >= 2:
        return True

    # Structured JSON used by NovelAI, InvokeAI, and similar exporters.
    prompt_markers = (
        b'"prompt"',
        b'"positive_prompt"',
        b'"negative_prompt"',
        b'"uc"',
    )
    json_settings = (
        b'"steps"',
        b'"sampler"',
        b'"seed"',
        b'"scale"',
        b'"cfg_scale"',
        b'"model"',
    )
    return (
        any(marker in normalized for marker in prompt_markers)
        and sum(marker in normalized for marker in json_settings) >= 2
    )


def _iter_jpeg_metadata_payloads(data: bytes):
    if not data.startswith(b"\xff\xd8"):
        return

    offset = 2
    data_length = len(data)
    while offset < data_length:
        if data[offset] != 0xFF:
            return
        while offset < data_length and data[offset] == 0xFF:
            offset += 1
        if offset >= data_length:
            return

        marker = data[offset]
        offset += 1
        if marker in {0xD9, 0xDA}:  # EOI or start of compressed pixels
            return
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > data_length:
            return

        segment_length = struct.unpack_from(">H", data, offset)[0]
        if segment_length < 2:
            return
        segment_end = offset + segment_length
        if segment_end > data_length:
            return
        if marker in JPEG_METADATA_MARKERS:
            yield data[offset + 2 : segment_end]
        offset = segment_end


def _iter_webp_metadata_payloads(data: bytes):
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return

    offset = 12
    data_length = len(data)
    while offset + 8 <= data_length:
        chunk_type = data[offset : offset + 4]
        chunk_length = struct.unpack_from("<I", data, offset + 4)[0]
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_length
        if chunk_end > data_length:
            return
        if chunk_type in WEBP_METADATA_CHUNKS:
            yield data[chunk_start:chunk_end]
        offset = chunk_end + (chunk_length & 1)


def has_generation_metadata(data: bytes, file_name: str) -> bool:
    """Detect generation metadata in PNG/JPEG/WebP without decoding pixels."""
    suffix = Path(file_name).suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return any(
            _payload_has_generation_markers(payload)
            for payload in _iter_jpeg_metadata_payloads(data)
        )
    if suffix == ".webp":
        return any(
            _payload_has_generation_markers(payload)
            for payload in _iter_webp_metadata_payloads(data)
        )
    if suffix != ".png" or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return False

    offset = 8
    data_length = len(data)
    while offset + 12 <= data_length:
        chunk_length = struct.unpack_from(">I", data, offset)[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_length
        next_offset = chunk_end + 4
        if next_offset > data_length:
            return False

        if chunk_type in {b"tEXt", b"iTXt"}:
            chunk_data = data[chunk_start:chunk_end]
            separator = chunk_data.find(b"\x00")
            if separator > 0:
                key = chunk_data[:separator].strip().lower()
                if key in PNG_METADATA_KEYS:
                    return True

        if chunk_type == b"IEND":
            break
        offset = next_offset

    return False


def _decode_metadata_bytes(value: bytes) -> str:
    """Decode EXIF/XMP text, including EXIF UserComment and Windows XP tags."""
    raw = value
    preferred_encodings: list[str] = []
    if raw.startswith(b"ASCII\x00\x00\x00"):
        raw = raw[8:]
        preferred_encodings.append("utf-8")
    elif raw.startswith(b"UNICODE\x00"):
        raw = raw[8:]
        preferred_encodings.extend(("utf-16-le", "utf-16-be"))
    elif raw.startswith(b"JIS\x00\x00\x00\x00\x00"):
        raw = raw[8:]
        preferred_encodings.append("shift_jis")

    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        preferred_encodings.insert(0, "utf-16")
    elif raw.count(b"\x00") > max(1, len(raw) // 4):
        # XPComment/XPTitle are commonly UTF-16LE without a BOM.
        preferred_encodings.extend(("utf-16-le", "utf-16-be"))
    preferred_encodings.extend(("utf-8", "latin-1"))

    candidates: list[str] = []
    for encoding in dict.fromkeys(preferred_encodings):
        try:
            decoded = raw.decode(encoding).strip("\x00\ufeff\ufffe \t\r\n")
        except (UnicodeDecodeError, LookupError):
            continue
        if decoded:
            candidates.append(decoded)

    if not candidates:
        return ""

    def text_score(text: str) -> float:
        lower = text.lower()
        generation_markers = (
            "negative prompt:",
            "steps:",
            "sampler:",
            '"class_type"',
            '"nodes"',
        )
        marker_score = sum(marker in lower for marker in generation_markers) * 5
        printable_score = sum(
            char.isprintable() or char in "\r\n\t" for char in text
        ) / max(1, len(text))
        ascii_score = sum(char.isascii() and char.isprintable() for char in text) / max(
            1, len(text)
        )
        return marker_score + printable_score + ascii_score

    return max(
        candidates,
        key=text_score,
    )


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
                if sep == -1:
                    continue
                key = data[:sep].decode("utf-8", errors="replace")
                rest = data[sep + 1 :]
                if len(rest) < 2:
                    continue
                compression_flag = rest[0]
                rest = rest[2:]

                language_end = rest.find(b"\x00")
                if language_end == -1:
                    continue
                rest = rest[language_end + 1 :]

                translated_end = rest.find(b"\x00")
                if translated_end == -1:
                    continue
                text_data = rest[translated_end + 1 :]
                if compression_flag == 1:
                    try:
                        text_data = zlib.decompress(text_data)
                    except zlib.error:
                        continue
                result[key] = text_data.decode("utf-8", errors="replace")
    return result


def extract_exif(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {}
    try:
        with Image.open(path) as img:
            raw_exif = img.getexif()
            if raw_exif:
                for tag_id, val in raw_exif.items():
                    tag = TAGS.get(tag_id, str(tag_id))
                    if isinstance(val, bytes):
                        if tag not in EXIF_TEXT_TAGS:
                            continue
                        decoded = _decode_metadata_bytes(val)
                        if decoded:
                            info[tag] = decoded
                        continue
                    info[tag] = str(val)
    except Exception:
        pass
    return info


def _flatten_metadata_value(
    prefix: str,
    value: Any,
    result: dict[str, str],
    *,
    depth: int = 0,
) -> None:
    if depth > 5:
        return
    if isinstance(value, bytes):
        decoded = _decode_metadata_bytes(value)
        if decoded:
            result[prefix] = decoded
        return
    if isinstance(value, str):
        value = value.strip("\x00 \t\r\n")
        if value:
            result[prefix] = value
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            _flatten_metadata_value(
                child_prefix,
                nested,
                result,
                depth=depth + 1,
            )
        return
    if isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _flatten_metadata_value(
                f"{prefix}.{index}",
                nested,
                result,
                depth=depth + 1,
            )


def _flatten_xmp_xml(prefix: str, raw_xml: str, result: dict[str, str]) -> None:
    if len(raw_xml) > 1_000_000:
        return
    try:
        root = ET.fromstring(raw_xml)
    except (ET.ParseError, ValueError):
        return

    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if element.text and element.text.strip():
            result[f"{prefix}.{tag}"] = element.text.strip()
        for key, value in element.attrib.items():
            attr = key.rsplit("}", 1)[-1]
            if value.strip():
                result[f"{prefix}.{tag}.{attr}"] = value.strip()


def extract_embedded_text(path: Path) -> dict[str, str]:
    """Collect comment/XMP fields that Pillow exposes for JPEG and WebP."""
    result: dict[str, str] = {}
    try:
        with Image.open(path) as img:
            for key, value in img.info.items():
                key_lower = str(key).lower()
                if not any(
                    marker in key_lower
                    for marker in (
                        "comment",
                        "description",
                        "xmp",
                        "parameters",
                        "prompt",
                        "workflow",
                    )
                ):
                    continue
                source_key = f"image_info.{key}"
                _flatten_metadata_value(source_key, value, result)
                decoded = result.get(source_key)
                if decoded and "<" in decoded:
                    _flatten_xmp_xml(source_key, decoded, result)
    except Exception:
        pass
    return result


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


def _json_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value.startswith("{"):
        return None
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _looks_like_api_prompt(value: dict[str, Any]) -> bool:
    return any(
        str(key).isdigit()
        and isinstance(node, dict)
        and "class_type" in node
        and "inputs" in node
        for key, node in value.items()
    )


def _looks_like_ui_workflow(value: dict[str, Any]) -> bool:
    return isinstance(value.get("nodes"), list)


def _params_from_generation_json(value: dict[str, Any]) -> dict[str, Any]:
    lowered = {str(key).lower(): nested for key, nested in value.items()}
    result: dict[str, Any] = {}

    for key in ("positive_prompt", "positive", "prompt", "description"):
        prompt = lowered.get(key)
        if isinstance(prompt, str) and prompt.strip():
            result["positive_prompt"] = prompt.strip()
            break
    for key in ("negative_prompt", "negative", "uc"):
        prompt = lowered.get(key)
        if isinstance(prompt, str) and prompt.strip():
            result["negative_prompt"] = prompt.strip()
            break

    settings_map = {
        "steps": "Steps",
        "sampler": "Sampler",
        "scheduler": "Schedule",
        "schedule": "Schedule",
        "cfg_scale": "CFG scale",
        "scale": "CFG scale",
        "seed": "Seed",
        "model": "Model",
        "model_hash": "Model hash",
        "denoising_strength": "Denoising strength",
        "clip_skip": "Clip skip",
    }
    settings: dict[str, Any] = {}
    for source_key, target_key in settings_map.items():
        setting = lowered.get(source_key)
        if isinstance(setting, (str, int, float)) and not isinstance(setting, bool):
            settings[target_key] = setting

    width = lowered.get("width")
    height = lowered.get("height")
    if isinstance(width, (str, int)) and isinstance(height, (str, int)):
        settings["Size"] = f"{width}x{height}"
    size = lowered.get("size")
    if "Size" not in settings and isinstance(size, str) and size.strip():
        settings["Size"] = size.strip()

    # Avoid presenting arbitrary descriptive JSON as generation parameters.
    if len(settings) < 2 and not (
        result.get("positive_prompt") and result.get("negative_prompt")
    ):
        return {}
    if settings:
        result["generation_settings"] = settings
    return result


def _collect_generation_metadata(
    text_sources: dict[str, str],
) -> tuple[
    dict[str, Any] | None,
    dict[str, Any] | None,
    str | None,
    dict[str, Any],
]:
    prompt_json: dict[str, Any] | None = None
    workflow_json: dict[str, Any] | None = None
    parameters_text: str | None = None
    structured_params: dict[str, Any] = {}

    def inspect_json(value: dict[str, Any], depth: int = 0) -> None:
        nonlocal prompt_json, workflow_json, parameters_text, structured_params
        if depth > 3:
            return
        if _looks_like_api_prompt(value):
            prompt_json = prompt_json or value
            return
        if _looks_like_ui_workflow(value):
            workflow_json = workflow_json or value

        parsed_params = _params_from_generation_json(value)
        if parsed_params:
            structured_params.update(parsed_params)

        for key in ("prompt", "workflow", "parameters", "metadata", "generation"):
            nested = value.get(key)
            nested_json = _json_dict(nested)
            if nested_json is not None:
                inspect_json(nested_json, depth + 1)
            elif key == "parameters" and isinstance(nested, str) and nested.strip():
                parameters_text = parameters_text or nested.strip()

    for source_key, text in text_sources.items():
        if not isinstance(text, str) or not text.strip():
            continue
        clean_text = text.strip()
        source_name = source_key.rsplit(".", 1)[-1].lower()
        if "parameters" in source_name:
            # A named field extracted from PNG/XMP is more precise than a
            # generation-looking raw container payload found earlier.
            parameters_text = clean_text

        parsed = _json_dict(clean_text)
        if parsed is not None:
            inspect_json(parsed)

        if parameters_text is None and _payload_has_generation_markers(
            clean_text.encode("utf-8", errors="ignore")
        ):
            parameters_text = clean_text

    return prompt_json, workflow_json, parameters_text, structured_params


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

    with Image.open(path) as source_img:
        image_format = source_img.format
        try:
            img = ImageOps.exif_transpose(source_img)
        except Exception:
            img = source_img
        meta["format"] = image_format
        meta["size"] = list(img.size)
        meta["mode"] = img.mode

    text_chunks: dict[str, str] = {}
    if path.suffix.lower() == ".png":
        text_chunks = read_png_text_chunks(path)

    exif = extract_exif(path)
    if exif:
        meta["exif"] = exif

    text_sources = dict(text_chunks)
    text_sources.update({f"exif.{key}": value for key, value in exif.items()})
    text_sources.update(extract_embedded_text(path))
    (
        prompt_json,
        workflow_json,
        parameters_text,
        structured_params,
    ) = _collect_generation_metadata(text_sources)

    prompt_parameters = dict(structured_params)
    if parameters_text:
        prompt_parameters.update(_parse_params_text(parameters_text))
        meta["raw_parameters"] = parameters_text

    if prompt_json and isinstance(prompt_json, dict):
        generated = _generate_params_from_api(prompt_json)
        if generated:
            prompt_parameters.update(generated)

    if prompt_parameters:
        meta["prompt_parameters"] = prompt_parameters

    wf = parse_workflow_json(prompt_json, workflow_json)
    if wf:
        meta["workflow"] = wf

    if prompt_json:
        meta["prompt_api_json"] = prompt_json
    if workflow_json:
        meta["workflow_ui_json"] = workflow_json

    return ImageMetadata.model_validate(meta)


def extract_metadata_from_bytes(data: bytes, file_name: str) -> ImageMetadata:
    """Extract metadata from a database-backed original on first access."""
    suffix = Path(file_name).suffix.lower()
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="comfy-meta-",
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_file.write(data)
            temp_path = Path(temp_file.name)

        metadata = extract_metadata(temp_path)
        return metadata.model_copy(update={
            "file": file_name,
            "path": f"database://{file_name}",
        })
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


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
