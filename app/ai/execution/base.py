from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import Field

from ..prompting import InstructionBundle, PromptResult, PromptTask
from ..prompting.models import StrictModel


class ExecutionMode(str, Enum):
    DIRECT = "direct"
    AGENT_HOST = "agent_host"


class ExecutionCapabilities(StrictModel):
    mode: ExecutionMode
    supports_images: bool = False
    image_inputs: tuple[str, ...] = ()
    supports_json_output: bool = True
    supports_streaming: bool = False
    supports_cancellation: bool = False
    supports_session_resume: bool = False
    supports_skills: bool = False
    supports_mcp: bool = False
    supports_subagents: bool = False


@dataclass(frozen=True)
class PreparedPromptExecution:
    profile: dict[str, Any]
    task: PromptTask
    bundle: InstructionBundle
    user_input: str
    api_key: str | None = None
    image_data_url: str | None = None
    image_path: Path | None = None


@dataclass(frozen=True)
class AdapterExecutionResult:
    result: PromptResult
    bundle: InstructionBundle
    metadata: dict[str, Any]


class AdapterExecutionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        stage: str,
        technical_error: str | None = None,
    ):
        self.code = code
        self.stage = stage
        self.technical_error = technical_error
        super().__init__(message)


@runtime_checkable
class PromptExecutionAdapter(Protocol):
    adapter_id: str
    capabilities: ExecutionCapabilities

    def supports_profile(self, profile: dict[str, Any]) -> bool: ...

    def execute(self, prepared: PreparedPromptExecution) -> AdapterExecutionResult: ...

    def cancel(self, run_id: str) -> None: ...


class PromptExecutionOutcome(StrictModel):
    job_id: int
    adapter_id: str = Field(min_length=1, max_length=120)
    result: PromptResult
    bundle: InstructionBundle
    metadata: dict[str, Any]


__all__ = [
    "AdapterExecutionError",
    "AdapterExecutionResult",
    "ExecutionCapabilities",
    "ExecutionMode",
    "PreparedPromptExecution",
    "PromptExecutionAdapter",
    "PromptExecutionOutcome",
]
