"""Execution adapters for compiled prompt tasks."""

from ..managed_process import run_managed_command
from . import opencode as _opencode_module
from . import opencode_judge as _opencode_judge_module
from .direct import (
    DirectPromptExecutionError,
    DirectPromptExecutionResult,
    DirectPromptExecutor,
)
from .adapters import DirectOpenAICompatibleAdapter, OpenCodeAgentHostAdapter
from .base import (
    AdapterExecutionError,
    AdapterExecutionResult,
    ExecutionCapabilities,
    ExecutionMode,
    PreparedPromptExecution,
    PromptExecutionAdapter,
    PromptExecutionOutcome,
)
from .intent_judge_policy import install_intent_judge_policy
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
from .router import ExecutionRouter, ExecutionRouterError

# OpenCode npm shims may leave descendant Node processes alive after their parent
# exits. Bind both managed adapters to the Job Object aware runner at package load.
_opencode_module.run_command = run_managed_command
_opencode_judge_module.run_command = run_managed_command

# Keep the public judge executor stable while benchmark-specific evaluation policy
# remains replaceable and independently testable.
install_intent_judge_policy(OpenCodeIntentJudgeExecutor)

__all__ = [
    "AdapterExecutionError",
    "AdapterExecutionResult",
    "DirectPromptExecutionError",
    "DirectPromptExecutionResult",
    "DirectPromptExecutor",
    "DirectOpenAICompatibleAdapter",
    "ExecutionCapabilities",
    "ExecutionMode",
    "ExecutionRouter",
    "ExecutionRouterError",
    "OpenCodePromptExecutionError",
    "OpenCodePromptExecutionResult",
    "OpenCodePromptExecutor",
    "OpenCodeAgentHostAdapter",
    "OpenCodeIntentJudgeExecutionError",
    "OpenCodeIntentJudgeExecutionResult",
    "OpenCodeIntentJudgeExecutor",
    "PreparedPromptExecution",
    "PromptExecutionAdapter",
    "PromptExecutionOutcome",
]
