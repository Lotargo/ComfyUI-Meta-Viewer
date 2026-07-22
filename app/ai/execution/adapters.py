from __future__ import annotations

from .base import (
    AdapterExecutionError,
    AdapterExecutionResult,
    ExecutionCapabilities,
    ExecutionMode,
    PreparedPromptExecution,
)
from .direct import DirectPromptExecutionError, DirectPromptExecutor
from .opencode import OpenCodePromptExecutionError, OpenCodePromptExecutor


class DirectOpenAICompatibleAdapter:
    adapter_id = "openai_compatible"
    capabilities = ExecutionCapabilities(
        mode=ExecutionMode.DIRECT,
        supports_images=True,
        image_inputs=("data_url",),
        supports_json_output=True,
    )

    def __init__(self, executor: DirectPromptExecutor | None = None):
        self.executor = executor or DirectPromptExecutor()

    @staticmethod
    def supports_profile(profile: dict) -> bool:
        return profile.get("kind", "openai_compatible") == "openai_compatible"

    def execute(self, prepared: PreparedPromptExecution) -> AdapterExecutionResult:
        try:
            executed = self.executor.execute(
                profile=prepared.profile,
                api_key=prepared.api_key,
                task=prepared.task,
                user_input=prepared.user_input,
                image_data_url=prepared.image_data_url,
                bundle=prepared.bundle,
            )
        except DirectPromptExecutionError as exc:
            raise AdapterExecutionError(
                str(exc),
                code=exc.code,
                stage=exc.stage,
                technical_error=exc.technical_error,
            ) from exc
        return AdapterExecutionResult(
            result=executed.result,
            bundle=executed.bundle,
            metadata=executed.metadata(),
        )

    def cancel(self, run_id: str) -> None:
        raise AdapterExecutionError(
            f"Direct execution run '{run_id}' cannot be cancelled by this adapter.",
            code="cancellation_unsupported",
            stage="cancel",
        )


class OpenCodeAgentHostAdapter:
    adapter_id = "opencode"
    capabilities = ExecutionCapabilities(
        mode=ExecutionMode.AGENT_HOST,
        supports_images=True,
        image_inputs=("file_path",),
        supports_json_output=True,
        supports_skills=True,
        supports_mcp=True,
        supports_subagents=True,
    )

    def __init__(self, executor: OpenCodePromptExecutor | None = None):
        self.executor = executor or OpenCodePromptExecutor()

    @staticmethod
    def supports_profile(profile: dict) -> bool:
        return profile.get("kind") == "cli" and profile.get("cli_type") == "opencode"

    def execute(self, prepared: PreparedPromptExecution) -> AdapterExecutionResult:
        try:
            executed = self.executor.execute(
                profile=prepared.profile,
                task=prepared.task,
                user_input=prepared.user_input,
                image_path=prepared.image_path,
                bundle=prepared.bundle,
            )
        except OpenCodePromptExecutionError as exc:
            raise AdapterExecutionError(
                str(exc),
                code=exc.code,
                stage=exc.stage,
                technical_error=exc.technical_error,
            ) from exc
        return AdapterExecutionResult(
            result=executed.result,
            bundle=executed.bundle,
            metadata=executed.metadata(),
        )

    def cancel(self, run_id: str) -> None:
        raise AdapterExecutionError(
            f"Managed OpenCode run '{run_id}' cannot be cancelled after dispatch.",
            code="cancellation_unsupported",
            stage="cancel",
        )


__all__ = ["DirectOpenAICompatibleAdapter", "OpenCodeAgentHostAdapter"]
