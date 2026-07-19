"""Execution adapters for compiled prompt tasks."""

from .direct import (
    DirectPromptExecutionError,
    DirectPromptExecutionResult,
    DirectPromptExecutor,
)
from .opencode import (
    OpenCodePromptExecutionError,
    OpenCodePromptExecutionResult,
    OpenCodePromptExecutor,
)

__all__ = [
    "DirectPromptExecutionError",
    "DirectPromptExecutionResult",
    "DirectPromptExecutor",
    "OpenCodePromptExecutionError",
    "OpenCodePromptExecutionResult",
    "OpenCodePromptExecutor",
]
