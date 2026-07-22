from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from ..job_store import AIJobStore, AIJobStoreError, PromptDraft
from ..prompting import PromptCompiler, PromptCompilerError, PromptTask
from .adapters import DirectOpenAICompatibleAdapter, OpenCodeAgentHostAdapter
from .base import (
    AdapterExecutionError,
    PreparedPromptExecution,
    PromptExecutionAdapter,
    PromptExecutionOutcome,
)


class ExecutionRouterError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        stage: str,
        job_id: int | None = None,
        technical_error: str | None = None,
    ):
        self.code = code
        self.stage = stage
        self.job_id = job_id
        self.technical_error = technical_error
        super().__init__(message)


class ExecutionRouter:
    """Route a PromptTask by adapter capabilities and persist one normalized result."""

    def __init__(
        self,
        *,
        adapters: Iterable[PromptExecutionAdapter] | None = None,
        compiler: PromptCompiler | None = None,
        job_store: AIJobStore | None = None,
    ):
        self.adapters = tuple(
            adapters
            if adapters is not None
            else (DirectOpenAICompatibleAdapter(), OpenCodeAgentHostAdapter())
        )
        if not self.adapters:
            raise ValueError("ExecutionRouter requires at least one adapter.")
        adapter_ids = [adapter.adapter_id for adapter in self.adapters]
        if len(adapter_ids) != len(set(adapter_ids)):
            raise ValueError("ExecutionRouter adapter IDs must be unique.")
        self.compiler = compiler or PromptCompiler()
        self.job_store = job_store or AIJobStore()

    def capabilities_for(self, profile: dict[str, Any]):
        return self._select_adapter(profile).capabilities

    def execute(
        self,
        *,
        profile: dict[str, Any],
        task: PromptTask,
        user_input: str,
        api_key: str | None = None,
        image_data_url: str | None = None,
        image_path: str | Path | None = None,
        asset_id: int | None = None,
    ) -> PromptExecutionOutcome:
        adapter = self._select_adapter(profile)
        normalized_path = Path(image_path) if image_path is not None else None
        image_kind = self._image_kind(
            image_data_url=image_data_url,
            image_path=normalized_path,
        )
        if image_kind is not None and image_kind not in adapter.capabilities.image_inputs:
            raise ExecutionRouterError(
                f"Adapter '{adapter.adapter_id}' does not accept {image_kind} image input.",
                code="incompatible_image_input",
                stage="route",
            )

        try:
            job = self.job_store.create(
                task=task,
                execution_backend=adapter.adapter_id,
                provider_profile_id=self._profile_text(profile, "id"),
                model_id=self._profile_text(profile, "model"),
                asset_id=asset_id,
                user_input=user_input,
            )
        except AIJobStoreError as exc:
            raise ExecutionRouterError(
                "The AI job could not be created.",
                code="persistence_error",
                stage="persistence",
                technical_error=str(exc),
            ) from exc
        try:
            bundle = self.compiler.compile(task)
            self.job_store.mark_running(job.id, bundle)
        except (PromptCompilerError, AIJobStoreError) as exc:
            self._record_failure(job.id, str(exc))
            raise ExecutionRouterError(
                str(exc),
                code="prompt_compile_error" if isinstance(exc, PromptCompilerError) else "persistence_error",
                stage="compile" if isinstance(exc, PromptCompilerError) else "persistence",
                job_id=job.id,
                technical_error=str(exc),
            ) from exc

        prepared = PreparedPromptExecution(
            profile=profile,
            task=task,
            bundle=bundle,
            user_input=user_input,
            api_key=api_key,
            image_data_url=image_data_url,
            image_path=normalized_path,
        )
        try:
            executed = adapter.execute(prepared)
        except AdapterExecutionError as exc:
            technical_error = exc.technical_error or str(exc)
            self._record_failure(job.id, technical_error)
            raise ExecutionRouterError(
                str(exc),
                code=exc.code,
                stage=exc.stage,
                job_id=job.id,
                technical_error=technical_error,
            ) from exc

        try:
            self.job_store.save_draft(
                job.id,
                PromptDraft(
                    schema_version=executed.result.schema_version,
                    positive_prompt=executed.result.positive_prompt,
                    negative_prompt=executed.result.negative_prompt,
                    versions=executed.bundle.versions,
                ),
            )
            snapshot = self.job_store.complete(
                job.id,
                result=executed.result,
                execution_metadata=executed.metadata,
                bundle=executed.bundle,
            )
        except AIJobStoreError as exc:
            self._record_failure(job.id, str(exc))
            raise ExecutionRouterError(
                "The model result could not be persisted.",
                code="persistence_error",
                stage="persistence",
                job_id=job.id,
                technical_error=str(exc),
            ) from exc

        return PromptExecutionOutcome(
            job_id=snapshot.job.id,
            adapter_id=adapter.adapter_id,
            result=executed.result,
            bundle=executed.bundle,
            metadata=executed.metadata,
        )

    def _select_adapter(self, profile: dict[str, Any]) -> PromptExecutionAdapter:
        if not isinstance(profile, dict):
            raise ExecutionRouterError(
                "Execution profile must be an object.",
                code="invalid_profile",
                stage="route",
            )
        matches = tuple(
            adapter for adapter in self.adapters if adapter.supports_profile(profile)
        )
        if not matches:
            raise ExecutionRouterError(
                "No prompt execution adapter supports this profile.",
                code="unsupported_backend",
                stage="route",
            )
        if len(matches) > 1:
            raise ExecutionRouterError(
                "More than one prompt execution adapter matched this profile.",
                code="ambiguous_backend",
                stage="route",
            )
        return matches[0]

    @staticmethod
    def _image_kind(
        *, image_data_url: str | None, image_path: Path | None
    ) -> str | None:
        if image_data_url is not None and image_path is not None:
            raise ExecutionRouterError(
                "Provide either image_data_url or image_path, not both.",
                code="ambiguous_image_input",
                stage="route",
            )
        if image_data_url is not None:
            return "data_url"
        if image_path is not None:
            return "file_path"
        return None

    @staticmethod
    def _profile_text(profile: dict[str, Any], key: str) -> str | None:
        value = profile.get(key)
        return value if isinstance(value, str) and value.strip() else None

    def _record_failure(self, job_id: int, technical_error: str) -> None:
        try:
            self.job_store.fail(job_id, technical_error[:16_000])
        except AIJobStoreError:
            pass


__all__ = ["ExecutionRouter", "ExecutionRouterError"]
