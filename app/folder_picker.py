from __future__ import annotations

from pathlib import Path

from .paths import normalize_existing_directory


class FolderPickerUnavailable(RuntimeError):
    """Raised when the OS folder picker cannot be displayed."""


def choose_folder() -> Path | None:
    """Open the native Tk folder dialog, with a caller-provided text fallback."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise FolderPickerUnavailable("Tk folder picker is not installed") from exc

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(parent=root, title="Select Folder")
    except Exception as exc:
        raise FolderPickerUnavailable(f"Folder picker is unavailable: {exc}") from exc
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass

    if not selected:
        return None
    return normalize_existing_directory(selected)
