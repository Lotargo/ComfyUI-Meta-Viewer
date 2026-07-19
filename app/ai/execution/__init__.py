"""Execution adapters for compiled prompt tasks."""

from ..managed_process import run_managed_command
from . import opencode as _opencode_module
from . import opencode_judge as _opencode_judge_module
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

# OpenCode npm shims may leave descendant Node processes alive after their parent
# exits. Bind both managed adapters to the Job Object aware runner at package load.
_opencode_module.run_command = run_managed_command
_opencode_judge_module.run_command = run_managed_command

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
