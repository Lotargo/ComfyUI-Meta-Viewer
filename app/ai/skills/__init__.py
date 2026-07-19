from __future__ import annotations

from pathlib import Path

SKILLS_DIR = Path(__file__).parent


def load_skill(name: str) -> str:
    """Load the complete system prompt for a model family.

    Args:
        name: One of "flux", "sdxl", or "pony".

    Returns:
        The full system-prompt text ready to be sent as
        the ``system`` message to an LLM.
    """
    path = SKILLS_DIR / f"{name}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"AI skill '{name}' not found.")
    return path.read_text(encoding="utf-8")
