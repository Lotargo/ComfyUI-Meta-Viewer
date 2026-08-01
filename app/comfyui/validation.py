from __future__ import annotations

import re
import shlex
from typing import Sequence


def validate_extra_args(extra_args: str | Sequence[str] | None) -> list[str]:
    """Validate extra arguments to prevent command injection and shell execution risks.

    Returns a list of safe token strings.
    Raises ValueError if any unsafe characters or tokens are detected.
    """
    if not extra_args:
        return []

    if isinstance(extra_args, str):
        # Use shlex.split to parse the string into tokens safely
        try:
            tokens = shlex.split(extra_args) if extra_args.strip() else []
        except Exception as exc:
            raise ValueError(f"Invalid extra arguments string: {exc}")
    else:
        # It's a sequence of arguments
        try:
            tokens = [str(t) for t in extra_args]
        except Exception as exc:
            raise ValueError(f"Invalid extra arguments sequence: {exc}")

    # Regex for strictly safe characters
    # Allowed: alphanumeric, hyphen, underscore, dot, forward slash, backslash, colon, equal, plus, comma, space, at, tilde
    safe_pattern = re.compile(r"^[a-zA-Z0-9\-_./\\:=+, @~]*$")

    for token in tokens:
        if not safe_pattern.match(token):
            raise ValueError(
                f"Unsafe character detected in extra argument token: {repr(token)}. "
                "Only alphanumeric characters and basic symbols (-_./\\:=+, @~) are allowed."
            )

    return tokens
