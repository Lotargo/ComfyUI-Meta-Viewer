from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import database as db


class ImageFileActionError(RuntimeError):
    code = "image_file_action_failed"
    status_code = 400


class ImageRecordNotFoundError(ImageFileActionError):
    code = "image_not_found"
    status_code = 404


class ImageHasNoLocalFileError(ImageFileActionError):
    code = "no_local_file"
    status_code = 409


class ImageLocalFileUnavailableError(ImageFileActionError):
    code = "local_file_unavailable"
    status_code = 404


class FileManagerUnavailableError(ImageFileActionError):
    code = "file_manager_unavailable"
    status_code = 503


def get_local_image_path(image_id: int) -> Path:
    """Resolve a physical source path from an indexed image ID only."""
    source = db.get_image_source_info(image_id)
    if not source:
        raise ImageRecordNotFoundError("Image not found")
    if source.get("has_original_data"):
        raise ImageHasNoLocalFileError(
            "This image is stored inside the app and has no local file path"
        )

    raw_path = source.get("path")
    if not raw_path:
        raise ImageLocalFileUnavailableError("Local file path is unavailable")
    path = Path(raw_path)
    if not path.is_file():
        raise ImageLocalFileUnavailableError("Local image file is unavailable")
    return path.resolve()


def _file_manager_command(path: Path, platform: str | None = None) -> list[str]:
    active_platform = platform or sys.platform
    if active_platform.startswith("win"):
        return ["explorer.exe", f"/select,{path}"]
    if active_platform == "darwin":
        return ["open", "-R", str(path)]

    xdg_open = shutil.which("xdg-open")
    if not xdg_open:
        raise FileManagerUnavailableError(
            "No supported desktop file manager launcher was found"
        )
    return [xdg_open, str(path.parent)]


def reveal_in_file_manager(path: Path) -> None:
    command = _file_manager_command(path)
    popen_options: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform.startswith("win"):
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if create_no_window:
            popen_options["creationflags"] = create_no_window
    else:
        popen_options["start_new_session"] = True

    try:
        subprocess.Popen(command, **popen_options)
    except OSError as exc:
        raise FileManagerUnavailableError(
            "The system file manager could not be opened"
        ) from exc


def reveal_image_file(image_id: int) -> Path:
    path = get_local_image_path(image_id)
    reveal_in_file_manager(path)
    return path
