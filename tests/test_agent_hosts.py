from unittest.mock import MagicMock, patch
import pytest

from app.ai.execution.adapters import (
    AntigravityAgentHostAdapter,
    ClaudeCodeAgentHostAdapter,
)
from app.ai.execution.antigravity import AntigravityPromptExecutionError, AntigravityPromptExecutor
from app.ai.execution.claude_code import ClaudeCodePromptExecutionError, ClaudeCodePromptExecutor
from app.ai.execution.router import ExecutionRouter
from app.ai.prompting import PromptFamily, PromptOperation, PromptScenario, PromptTask


def test_claude_code_executor_profile_validation():
    executor = ClaudeCodePromptExecutor()
    task = PromptTask(
        operation=PromptOperation.GENERATE,
        family=PromptFamily.FLUX,
        scenario=PromptScenario.SINGLE_CHARACTER,
    )
    with pytest.raises(ClaudeCodePromptExecutionError) as exc_info:
        executor.execute(
            profile={"kind": "openai_compatible"},
            task=task,
            user_input="test prompt",
        )
    assert exc_info.value.code == "invalid_profile"


def test_antigravity_executor_profile_validation():
    executor = AntigravityPromptExecutor()
    task = PromptTask(
        operation=PromptOperation.GENERATE,
        family=PromptFamily.FLUX,
        scenario=PromptScenario.SINGLE_CHARACTER,
    )
    with pytest.raises(AntigravityPromptExecutionError) as exc_info:
        executor.execute(
            profile={"kind": "cli", "cli_type": "opencode"},
            task=task,
            user_input="test prompt",
        )
    assert exc_info.value.code == "invalid_profile"


def test_router_selects_claude_and_antigravity():
    router = ExecutionRouter()

    claude_profile = {"id": "p1", "kind": "cli", "cli_type": "claude_code"}
    antigravity_profile = {"id": "p2", "kind": "cli", "cli_type": "antigravity"}

    claude_adapter = router._select_adapter(claude_profile)
    assert isinstance(claude_adapter, ClaudeCodeAgentHostAdapter)

    antigravity_adapter = router._select_adapter(antigravity_profile)
    assert isinstance(antigravity_adapter, AntigravityAgentHostAdapter)
