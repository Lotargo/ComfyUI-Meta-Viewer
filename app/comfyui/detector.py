from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.paths import normalize_path


class ComfyUIDetectionError(RuntimeError):
    """Raised when ComfyUI installation detection fails."""


@dataclass(frozen=True)
class ComfyUIDetectionResult:
    root_path: Path
    comfy_dir: Path | None = None
    main_py: Path | None = None
    interpreter: Path | None = None
    is_portable: bool = False
    is_valid: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_path": str(self.root_path),
            "comfy_dir": str(self.comfy_dir) if self.comfy_dir else None,
            "main_py": str(self.main_py) if self.main_py else None,
            "interpreter": str(self.interpreter) if self.interpreter else None,
            "is_portable": self.is_portable,
            "is_valid": self.is_valid,
            "error": self.error,
        }


def detect_comfyui(
    path: str | Path,
    custom_python: str | Path | None = None,
) -> ComfyUIDetectionResult:
    """Validate ComfyUI installation directory structure and resolve Python interpreter.

    Supported directory structures:
    1) Selected directory contains `main.py` directly.
    2) Selected directory contains nested `ComfyUI/main.py`.

    If multiple ambiguous nested main.py are found or structure doesn't match, return invalid result with error.
    """
    if not path:
        return ComfyUIDetectionResult(
            root_path=Path(""),
            is_valid=False,
            error="Path is empty",
        )

    root_path = normalize_path(path)
    if not root_path.exists():
        return ComfyUIDetectionResult(
            root_path=root_path,
            is_valid=False,
            error=f"Directory does not exist: {root_path}",
        )
    if not root_path.is_dir():
        return ComfyUIDetectionResult(
            root_path=root_path,
            is_valid=False,
            error=f"Path is not a directory: {root_path}",
        )

    main_direct = root_path / "main.py"
    main_nested = root_path / "ComfyUI" / "main.py"

    comfy_dir: Path | None = None
    main_py: Path | None = None

    if main_direct.is_file() and main_nested.is_file():
        return ComfyUIDetectionResult(
            root_path=root_path,
            is_valid=False,
            error="Ambiguous ComfyUI installation: main.py found in root and nested ComfyUI directory",
        )
    elif main_direct.is_file():
        comfy_dir = root_path
        main_py = main_direct
    elif main_nested.is_file():
        comfy_dir = root_path / "ComfyUI"
        main_py = main_nested
    else:
        return ComfyUIDetectionResult(
            root_path=root_path,
            is_valid=False,
            error="Invalid directory structure: main.py not found in selected folder or nested ComfyUI subfolder",
        )

    interpreter, is_portable = find_python_interpreter(
        root_path=root_path,
        comfy_dir=comfy_dir,
        custom_python=custom_python,
    )

    if interpreter is None:
        return ComfyUIDetectionResult(
            root_path=root_path,
            comfy_dir=comfy_dir,
            main_py=main_py,
            is_portable=is_portable,
            is_valid=False,
            error="Python interpreter not found for this ComfyUI installation",
        )

    return ComfyUIDetectionResult(
        root_path=root_path,
        comfy_dir=comfy_dir,
        main_py=main_py,
        interpreter=interpreter,
        is_portable=is_portable,
        is_valid=True,
        error=None,
    )


def find_python_interpreter(
    root_path: Path,
    comfy_dir: Path,
    custom_python: str | Path | None = None,
) -> tuple[Path | None, bool]:
    """Find Python interpreter for ComfyUI.

    Returns (interpreter_path, is_portable_flag).
    """
    if custom_python:
        custom_path = normalize_path(custom_python)
        if custom_path.is_file():
            return custom_path, False

    is_windows = sys.platform == "win32" or os.name == "nt"

    candidates_portable = [
        root_path / "python_embeded" / "python.exe",
        root_path.parent / "python_embeded" / "python.exe",
        comfy_dir / "python_embeded" / "python.exe",
        comfy_dir.parent / "python_embeded" / "python.exe",
    ]

    for cand in candidates_portable:
        if cand.is_file():
            return cand, True

    if is_windows:
        relative_venvs = [
            Path(".venv/Scripts/python.exe"),
            Path("venv/Scripts/python.exe"),
        ]
    else:
        relative_venvs = [
            Path(".venv/bin/python"),
            Path("venv/bin/python"),
        ]

    search_dirs = [comfy_dir, root_path]
    if comfy_dir.parent != root_path:
        search_dirs.append(comfy_dir.parent)

    for base in search_dirs:
        for rel in relative_venvs:
            cand = base / rel
            if cand.is_file():
                return cand, False

    return None, False
