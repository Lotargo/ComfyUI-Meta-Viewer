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
from .opencode_judge import (
    OpenCodeIntentJudgeExecutionError,
    OpenCodeIntentJudgeExecutionResult,
    OpenCodeIntentJudgeExecutor,
)

__all__ = [
    "DirectPromptExecutionError",
    "DirectPromptExecutionResult",
    "DirectPromptExecutor",
    "OpenCodePromptExecutionError",
    "OpenCodePromptExecutionResult",
    "OpenCodePromptExecutor",
    "OpenCodeIntentJudgeExecutionError",
    "OpenCodeIntentJudgeExecutionResult",
    "OpenCodeIntentJudgeExecutor",
]
