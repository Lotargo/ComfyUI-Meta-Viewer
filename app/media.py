from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Literal

from .extractor import SUPPORTED as IMAGE_EXTENSIONS


VIDEO_MIME_TYPES = {
    ".mp4": "video/mp4",
    ".m4v": "video/x-m4v",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
}
VIDEO_EXTENSIONS = frozenset(VIDEO_MIME_TYPES)
SUPPORTED_MEDIA_EXTENSIONS = frozenset(IMAGE_EXTENSIONS) | VIDEO_EXTENSIONS

IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
}


class MediaToolUnavailableError(RuntimeError):
    def __init__(self, tool: str):
        self.tool = tool
        super().__init__(
            f"{tool} is not installed or is not available on PATH"
        )


class VideoProcessingError(RuntimeError):
    pass


@dataclass(frozen=True)
class VideoProbeResult:
    format: str | None
    width: int
    height: int
    pixel_format: str | None
    duration: float | None
    frame_rate: float | None
    codec: str | None
    metadata: dict[str, Any]


def media_type_for_path(path: str | Path) -> Literal["image", "video"] | None:
    suffix = Path(path).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    return None


def mime_type_for_path(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    return IMAGE_MIME_TYPES.get(
        suffix,
        VIDEO_MIME_TYPES.get(suffix, "application/octet-stream"),
    )


@contextmanager
def temporary_media_file(data: bytes, file_name: str) -> Iterator[Path]:
    """Expose an uploaded media BLOB as a short-lived file for FFmpeg tools."""
    suffix = Path(file_name).suffix.lower()
    with tempfile.TemporaryDirectory(prefix="comfy-meta-upload-") as directory:
        path = Path(directory) / f"asset{suffix}"
        path.write_bytes(data)
        yield path


def _subprocess_options() -> dict[str, Any]:
    if not sys.platform.startswith("win"):
        return {}
    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return {"creationflags": create_no_window} if create_no_window else {}


def _tool_path(name: str, explicit_path: str | None) -> str:
    executable = explicit_path or shutil.which(name)
    if not executable:
        raise MediaToolUnavailableError(name)
    return executable


def _optional_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _frame_rate(value: Any) -> float | None:
    if not value or value in ("0/0", "N/A"):
        return None
    if isinstance(value, str) and "/" in value:
        numerator, denominator = value.split("/", 1)
        try:
            denominator_value = float(denominator)
            if denominator_value == 0:
                return None
            return float(numerator) / denominator_value
        except ValueError:
            return None
    return _optional_float(value)


def probe_video(
    path: str | Path,
    *,
    ffprobe_path: str | None = None,
    timeout: float = 30.0,
) -> VideoProbeResult:
    """Read video stream and container metadata with ffprobe JSON output."""
    executable = _tool_path("ffprobe", ffprobe_path)
    command = [
        executable,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(Path(path)),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            **_subprocess_options(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VideoProcessingError(f"ffprobe could not inspect the video: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "unknown ffprobe error"
        raise VideoProcessingError(f"ffprobe could not inspect the video: {detail[:500]}")
    try:
        payload = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise VideoProcessingError("ffprobe returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise VideoProcessingError("ffprobe returned an unexpected JSON document")

    streams = payload.get("streams")
    video_stream = next(
        (
            stream
            for stream in streams or []
            if isinstance(stream, dict) and stream.get("codec_type") == "video"
        ),
        None,
    )
    if video_stream is None:
        raise VideoProcessingError("The file does not contain a video stream")

    format_info = payload.get("format") or {}
    duration = _optional_float(video_stream.get("duration"))
    if duration is None:
        duration = _optional_float(format_info.get("duration"))
    frame_rate = _frame_rate(
        video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
    )
    container = format_info.get("format_name")
    codec = video_stream.get("codec_name")
    pixel_format = video_stream.get("pix_fmt")

    embedded_metadata = {
        "source": "ffprobe",
        "status": "available",
        "container": container,
        "duration": duration,
        "format_tags": format_info.get("tags") or {},
        "video_stream": {
            "codec": codec,
            "codec_long_name": video_stream.get("codec_long_name"),
            "profile": video_stream.get("profile"),
            "width": int(video_stream.get("width") or 0),
            "height": int(video_stream.get("height") or 0),
            "pixel_format": pixel_format,
            "frame_rate": frame_rate,
            "bit_rate": _optional_float(video_stream.get("bit_rate")),
            "tags": video_stream.get("tags") or {},
        },
    }
    return VideoProbeResult(
        format=str(container).split(",", 1)[0] if container else None,
        width=int(video_stream.get("width") or 0),
        height=int(video_stream.get("height") or 0),
        pixel_format=str(pixel_format) if pixel_format else None,
        duration=duration,
        frame_rate=frame_rate,
        codec=str(codec) if codec else None,
        metadata=embedded_metadata,
    )


def make_video_thumbnail(
    path: str | Path,
    *,
    duration: float | None = None,
    ffmpeg_path: str | None = None,
    timeout: float = 45.0,
) -> bytes:
    """Decode one bounded-size JPEG preview frame with ffmpeg."""
    executable = _tool_path("ffmpeg", ffmpeg_path)
    seek_seconds = min(5.0, max(0.0, (duration or 0.0) * 0.1))
    command = [executable, "-v", "error"]
    if seek_seconds:
        command.extend(("-ss", f"{seek_seconds:.3f}"))
    command.extend((
        "-i",
        str(Path(path)),
        "-map",
        "0:v:0",
        "-frames:v",
        "1",
        "-vf",
        "scale=640:-2:force_original_aspect_ratio=decrease",
        "-an",
        "-sn",
        "-f",
        "image2pipe",
        "-c:v",
        "mjpeg",
        "pipe:1",
    ))
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=timeout,
            **_subprocess_options(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VideoProcessingError(f"ffmpeg could not create a video preview: {exc}") from exc
    if completed.returncode != 0 or not completed.stdout:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise VideoProcessingError(
            f"ffmpeg could not create a video preview: {detail[:500] or 'no frame was returned'}"
        )
    return bytes(completed.stdout)


def media_tool_status() -> dict[str, dict[str, str | bool | None]]:
    status: dict[str, dict[str, str | bool | None]] = {}
    for name in ("ffmpeg", "ffprobe"):
        path = shutil.which(name)
        status[name] = {"available": bool(path), "path": path}
    return status
