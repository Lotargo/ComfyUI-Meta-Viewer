from __future__ import annotations

from pathlib import Path

FAMILY_BASE_DIR = Path(__file__).parents[1] / "prompting" / "content" / "profiles"
FAMILY_BASES = {
    "flux": FAMILY_BASE_DIR / "flux" / "base.md",
    "sdxl": FAMILY_BASE_DIR / "sdxl" / "base.md",
    "pony": FAMILY_BASE_DIR / "pony" / "base.md",
}


def load_skill(name: str) -> str:
    """Compatibility loader for a canonical model-family base.

    Args:
        name: One of "flux", "sdxl", or "pony".

    Returns:
        The family-base instruction text. New code should compile a complete
        ``InstructionBundle`` instead of sending this layer by itself.
    """
    path = FAMILY_BASES.get(name)
    if path is None or not path.is_file():
        raise FileNotFoundError(f"AI skill '{name}' not found.")
    return path.read_text(encoding="utf-8")
