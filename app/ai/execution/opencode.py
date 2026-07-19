from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..cli import CLIIntegrationError, find_executable, run_command
from ..prompting import (
    InstructionBundle,
    PromptCompiler,
    PromptCompilerError,
    PromptContractError,
    PromptResult,
    PromptTask,
    parse_prompt_result,
)


MAX_USER_INPUT_CHARS = 100_000
MAX_IMAGE_BYTES = 20 * 1024 * 1024
SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
OPENCODE_AGENT_NAME = "cmv-prompt-smoke"


class OpenCodePromptExecutionError(RuntimeError):
    """Normalized failure raised by the managed OpenCode execution path."""

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


@dataclass(frozen=True)
class OpenCodePromptExecutionResult:
    result: PromptResult
    bundle: InstructionBundle
    latency_ms: int
    raw_response_sha256: str
    transport: str = "opencode"
    agent: str = OPENCODE_AGENT_NAME

    def metadata(self) -> dict[str, Any]:
        return {
            "transport": self.transport,
            "agent": self.agent,
            "latency_ms": self.latency_ms,
            "raw_response_sha256": self.raw_response_sha256,
            "bundle": self.bundle.metadata(),
        }


class OpenCodePromptExecutor:
    """Execute a PromptTask through an authenticated OpenCode CLI profile.

    This is the managed CLI form of the agent-host integration. A temporary,
    isolated OpenCode project is created for every run. The temporary primary
    agent has all tool permissions denied, while OpenCode still owns provider
    authentication, model selection, session execution, and JSON event output.
    """

    def __init__(self, compiler: PromptCompiler | None = None):
        self.compiler = compiler or PromptCompiler()

    def execute(
        self,
        *,
        profile: dict[str, Any],
        task: PromptTask,
        user_input: str,
        image_path: str | Path | None = None,
    ) -> OpenCodePromptExecutionResult:
        self._validate_profile(profile)
        cleaned_input = self._validate_user_input(user_input)
        validated_image = self._validate_image_path(image_path)
        if validated_image is not None and profile.get("multimodal") is not True:
            raise OpenCodePromptExecutionError(
                "This OpenCode profile is not marked as multimodal.",
                code="incompatible_format",
                stage="input",
            )

        try:
            bundle = self.compiler.compile(task)
        except PromptCompilerError as exc:
            raise OpenCodePromptExecutionError(
                str(exc),
                code="prompt_compile_error",
                stage="compile",
                technical_error=str(exc),
            ) from exc

        executable = find_executable("opencode", profile.get("executable"))
        if executable is None:
            raise OpenCodePromptExecutionError(
                "OpenCode was not found in PATH or at the configured executable path.",
                code="cli_unavailable",
                stage="host",
            )

        try:
            with tempfile.TemporaryDirectory(prefix="cmv-opencode-smoke-") as temp_dir:
                workspace = Path(temp_dir)
                self._write_isolated_config(workspace)
                task_file = workspace / "cmv-task.md"
                task_file.write_text(
                    self._render_task_package(bundle, cleaned_input),
                    encoding="utf-8",
                    newline="\n",
                )

                file_args = [f"--file={task_file}"]
                if validated_image is not None:
                    copied_image = workspace / f"input{validated_image.suffix.lower()}"
                    shutil.copyfile(validated_image, copied_image)
                    file_args.append(f"--file={copied_image}")

                prompt = (
                    "Use the attached CMV task package as the authoritative task. "
                    "Do not use tools, subagents, skills, file browsing, shell commands, "
                    "or network access. Return only the strict JSON object required by "
                    "the task package, with no Markdown fences or commentary."
                )
                args = [
                    executable,
                    "--pure",
                    "run",
                    "--model",
                    profile["model"],
                    "--format",
                    "json",
                    "--agent",
                    OPENCODE_AGENT_NAME,
                    "--title",
                    "ComfyUI Meta Viewer prompt smoke",
                    prompt,
                    *file_args,
                ]
                command = run_command(
                    args,
                    timeout=profile["timeout_seconds"],
                    cwd=workspace,
                )
        except CLIIntegrationError as exc:
            raise OpenCodePromptExecutionError(
                str(exc),
                code=exc.code,
                stage="host",
                technical_error=str(exc),
            ) from exc
        except OSError as exc:
            raise OpenCodePromptExecutionError(
                f"Cannot prepare the isolated OpenCode task: {exc}",
                code="host_workspace_error",
                stage="host",
                technical_error=str(exc),
            ) from exc

        combined_output = "\n".join(
            part for part in (command.stdout, command.stderr) if part
        )
        if command.returncode != 0:
            lowered = combined_output.casefold()
            code = (
                "cli_authentication"
                if any(
                    marker in lowered
                    for marker in ("auth", "login", "credential", "access denied")
                )
                else "provider_error"
            )
            raise OpenCodePromptExecutionError(
                combined_output or "OpenCode request failed.",
                code=code,
                stage="host",
                technical_error=combined_output[:16_000] or None,
            )

        raw_text = self._parse_json_events(command.stdout)
        if not raw_text:
            raise OpenCodePromptExecutionError(
                "OpenCode returned no assistant text in its JSON event stream.",
                code="incompatible_format",
                stage="host",
                technical_error=combined_output[:16_000] or None,
            )

        try:
            result = parse_prompt_result(raw_text)
        except PromptContractError as exc:
            raise OpenCodePromptExecutionError(
                str(exc),
                code=exc.code,
                stage="contract",
                technical_error=exc.technical_error,
            ) from exc

        return OpenCodePromptExecutionResult(
            result=result,
            bundle=bundle,
            latency_ms=command.elapsed_ms,
            raw_response_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        )

    @staticmethod
    def _validate_profile(profile: dict[str, Any]) -> None:
        if profile.get("kind") != "cli" or profile.get("cli_type") != "opencode":
            raise OpenCodePromptExecutionError(
                "This operation requires an OpenCode CLI profile.",
                code="incompatible_profile",
                stage="input",
            )
        if not isinstance(profile.get("model"), str) or not profile["model"].strip():
            raise OpenCodePromptExecutionError(
                "The OpenCode profile has no model ID.",
                code="invalid_profile",
                stage="input",
            )

    @staticmethod
    def _validate_user_input(value: str) -> str:
        if not isinstance(value, str):
            raise OpenCodePromptExecutionError(
                "Prompt task input must be text.",
                code="invalid_input",
                stage="input",
            )
        cleaned = value.strip()
        if not cleaned:
            raise OpenCodePromptExecutionError(
                "Prompt task input cannot be empty.",
                code="invalid_input",
                stage="input",
            )
        if len(cleaned) > MAX_USER_INPUT_CHARS:
            raise OpenCodePromptExecutionError(
                "Prompt task input is too large.",
                code="input_too_large",
                stage="input",
            )
        return cleaned

    @staticmethod
    def _validate_image_path(value: str | Path | None) -> Path | None:
        if value is None:
            return None
        path = Path(value).expanduser().resolve(strict=False)
        if not path.is_file():
            raise OpenCodePromptExecutionError(
                f"Image file does not exist: {path}",
                code="image_not_found",
                stage="input",
            )
        if path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
            raise OpenCodePromptExecutionError(
                "OpenCode smoke images must be PNG, JPEG, WEBP, or GIF.",
                code="unsupported_image",
                stage="input",
            )
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise OpenCodePromptExecutionError(
                f"Cannot inspect image file: {path}: {exc}",
                code="image_read_error",
                stage="input",
                technical_error=str(exc),
            ) from exc
        if size <= 0:
            raise OpenCodePromptExecutionError(
                "The selected image is empty.",
                code="invalid_image",
                stage="input",
            )
        if size > MAX_IMAGE_BYTES:
            raise OpenCodePromptExecutionError(
                "Image input is too large.",
                code="image_too_large",
                stage="input",
            )
        return path

    @staticmethod
    def _write_isolated_config(workspace: Path) -> None:
        config = {
            "$schema": "https://opencode.ai/config.json",
            "share": "disabled",
            "agent": {
                OPENCODE_AGENT_NAME: {
                    "description": "Generate one CMV PromptResult without tools.",
                    "mode": "primary",
                    "permission": {"*": "deny"},
                    "prompt": (
                        "You execute deterministic ComfyUI Meta Viewer prompt tasks. "
                        "Use only the supplied task package and attachments. Return strict JSON only."
                    ),
                }
            },
        }
        (workspace / "opencode.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    @staticmethod
    def _render_task_package(bundle: InstructionBundle, user_input: str) -> str:
        return (
            "# CMV managed OpenCode task\n\n"
            "The instruction bundle below is authoritative. Do not inspect the project or "
            "seek additional context.\n\n"
            f"{bundle.render()}\n"
            "USER TASK INPUT\n"
            f"{user_input}\n"
        )

    @staticmethod
    def _parse_json_events(output: str) -> str:
        text_parts: list[str] = []
        for line in output.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            part = event.get("part")
            text = part.get("text") if isinstance(part, dict) else None
            if not isinstance(text, str):
                text = event.get("text")
            if isinstance(text, str) and text:
                text_parts.append(text)
        return "".join(text_parts).strip()
