from __future__ import annotations

import builtins
import sys
from importlib.util import find_spec
from types import ModuleType
from typing import Any


class Text:
    """Small plain-text replacement for the subset of Rich used by smoke tools."""

    def __init__(self, text: Any = "", *, style: str | None = None) -> None:
        self.plain = str(text)
        self.style = style

    def __str__(self) -> str:
        return self.plain


class Table:
    """Readable ASCII table used when the optional Rich package is unavailable."""

    def __init__(
        self,
        *args: Any,
        title: str | None = None,
        show_header: bool = True,
        **kwargs: Any,
    ) -> None:
        del args, kwargs
        self.title = title
        self.show_header = show_header
        self._columns: list[str] = []
        self._rows: list[list[str]] = []

    def add_column(self, header: str = "", **kwargs: Any) -> None:
        del kwargs
        self._columns.append(str(header))

    def add_row(self, *values: Any, **kwargs: Any) -> None:
        del kwargs
        self._rows.append([_cell(value) for value in values])

    def __str__(self) -> str:
        column_count = max(
            [len(self._columns), *(len(row) for row in self._rows)],
            default=0,
        )
        if column_count == 0:
            return self.title or ""

        headers = [*self._columns, *([""] * (column_count - len(self._columns)))]
        rows = [
            [*row, *([""] * (column_count - len(row)))]
            for row in self._rows
        ]
        width_rows = rows + ([headers] if self.show_header else [])
        widths = [
            max((len(row[index]) for row in width_rows), default=0)
            for index in range(column_count)
        ]

        def render_row(row: list[str]) -> str:
            return " | ".join(
                value.ljust(widths[index]) for index, value in enumerate(row)
            ).rstrip()

        lines: list[str] = []
        if self.title:
            lines.append(self.title)
        if self.show_header and any(headers):
            lines.append(render_row(headers))
            lines.append("-+-".join("-" * width for width in widths))
        lines.extend(render_row(row) for row in rows)
        return "\n".join(lines)


class Panel:
    """Simple titled block compatible with the calls used by the smoke CLIs."""

    def __init__(
        self,
        renderable: Any,
        *,
        title: str | None = None,
        border_style: str | None = None,
        **kwargs: Any,
    ) -> None:
        del border_style, kwargs
        self.renderable = renderable
        self.title = title

    def __str__(self) -> str:
        body = str(self.renderable)
        if not self.title:
            return body
        rule = "-" * max(8, len(self.title) + 4)
        return f"{rule}\n{self.title}\n{rule}\n{body}\n{rule}"


class _Status:
    def __init__(self, console: Console, message: str) -> None:
        self.console = console
        self.message = message

    def __enter__(self) -> _Status:
        self.console.print(self.message)
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        del exc_type, exc, traceback
        return False

    def update(self, message: str, **kwargs: Any) -> None:
        del kwargs
        self.message = message
        self.console.print(message)


class Console:
    """Minimal Console API; Rich remains preferred when it is installed."""

    def __init__(self, *args: Any, no_color: bool = False, **kwargs: Any) -> None:
        del args, no_color, kwargs

    def print(self, *objects: Any, sep: str = " ", end: str = "\n", **kwargs: Any) -> None:
        del kwargs
        builtins.print(*(str(obj) for obj in objects), sep=sep, end=end)

    def status(self, message: str, **kwargs: Any) -> _Status:
        del kwargs
        return _Status(self, message)


def _cell(value: Any) -> str:
    return str(value).replace("\r\n", "\n").replace("\n", " / ")


def install_rich_fallback() -> None:
    """Expose a tiny Rich-compatible API only when third-party Rich is absent."""

    if "rich" in sys.modules or find_spec("rich") is not None:
        return

    rich_module = ModuleType("rich")
    rich_module.__path__ = []  # type: ignore[attr-defined]

    modules = {
        "console": ("Console", Console),
        "panel": ("Panel", Panel),
        "table": ("Table", Table),
        "text": ("Text", Text),
    }
    sys.modules["rich"] = rich_module

    for module_name, (symbol_name, symbol) in modules.items():
        module = ModuleType(f"rich.{module_name}")
        setattr(module, symbol_name, symbol)
        setattr(rich_module, module_name, module)
        sys.modules[f"rich.{module_name}"] = module
