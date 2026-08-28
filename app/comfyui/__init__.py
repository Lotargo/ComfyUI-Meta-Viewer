from __future__ import annotations

from .editor_routes import editor_blueprint
from .routes import comfyui_blueprint
from .simple_routes import simple_blueprint
from .simple_download_probe import install_simple_download_probe

install_simple_download_probe()

__all__ = [
    "comfyui_blueprint",
    "editor_blueprint",
    "simple_blueprint",
]
