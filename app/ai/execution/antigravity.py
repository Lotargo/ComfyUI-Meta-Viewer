from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any

logger = logging.getLogger("cmv.ai.antigravity")

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


class AntigravityPromptExecutionError(RuntimeError):
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
class AntigravityPromptExecutionResult:
    result: PromptResult
    bundle: InstructionBundle
    latency_ms: int
    raw_response_sha256: str
    transport: str = "antigravity"
    agent: str = "antigravity-cli"
    response_normalizations: tuple[str, ...] = ()

    def metadata(self) -> dict[str, Any]:
        return {
            "transport": self.transport,
            "agent": self.agent,
            "latency_ms": self.latency_ms,
            "raw_response_sha256": self.raw_response_sha256,
            "response_normalizations": list(self.response_normalizations),
            "bundle": self.bundle.metadata(),
        }


def _clean_markdown_fence(text: str) -> tuple[str, bool]:
    cleaned = text.strip()
    unwrapped = False
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().endswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
        unwrapped = True
    elif "```json" in cleaned:
        start = cleaned.find("```json") + 7
        end = cleaned.find("```", start)
        if end != -1:
            cleaned = cleaned[start:end].strip()
            unwrapped = True
    elif "```" in cleaned:
        start = cleaned.find("```") + 3
        end = cleaned.find("```", start)
        if end != -1:
            cleaned = cleaned[start:end].strip()
            unwrapped = True
    return cleaned, unwrapped


class AntigravityPromptExecutor:
    """Execute a PromptTask through the Antigravity CLI interface (agy)."""

    def __init__(self, compiler: PromptCompiler | None = None):
        self.compiler = compiler or PromptCompiler()

    def execute(
        self,
        *,
        profile: dict[str, Any],
        task: PromptTask,
        user_input: str,
        image_path: str | Path | None = None,
        bundle: InstructionBundle | None = None,
        on_output_chunk: Any = None,
    ) -> AntigravityPromptExecutionResult:
        if profile.get("kind") != "cli" or profile.get("cli_type") != "antigravity":
            raise AntigravityPromptExecutionError(
                "Profile must be a CLI profile with cli_type='antigravity'.",
                code="invalid_profile",
                stage="preflight",
            )

        executable = (
            find_executable("antigravity", profile.get("custom_path"))
            or find_executable("antigravity")
        )
        if executable is None:
            logger.error("[Antigravity] Binary (agy) not found on PATH or custom_path")
            raise AntigravityPromptExecutionError(
                "Antigravity CLI binary (agy) is not installed or not found on PATH.",
                code="antigravity_not_found",
                stage="preflight",
            )

        instruction_bundle = bundle or self.compiler.compile(task)
        prompt_text = f"{instruction_bundle.render()}\n\nUSER PROMPT:\n{user_input}"

        timeout_sec = profile.get("timeout_seconds") or 300
        start_time = time.perf_counter()

        cmd = [
            executable,
            "--print",
            prompt_text,
            "--dangerously-skip-permissions",
            "--sandbox",
        ]
        model = profile.get("model")
        if model:
            clean_model = str(model).split("\t")[0].strip()
            cmd.extend(["--model", clean_model])

        logger.info("[Antigravity] Executing command: %s (model=%s, timeout=%s)", executable, model, timeout_sec)

        try:
            completed = run_command(cmd, timeout=timeout_sec, on_output_chunk=on_output_chunk)
        except CLIIntegrationError as exc:
            logger.error("[Antigravity] CLI execution error: %s", exc)
            raise AntigravityPromptExecutionError(
                f"Antigravity CLI execution failed: {exc}",
                code="execution_failed",
                stage="execution",
                technical_error=str(exc),
            ) from exc

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        raw_output = completed.stdout.strip()

        logger.info("[Antigravity] Completed in %dms with code %d", elapsed_ms, completed.returncode)
        if completed.stderr:
            logger.warning("[Antigravity] STDERR: %s", completed.stderr)

        if completed.returncode != 0 and not raw_output:
            logger.error("[Antigravity] Process exited with error code %d: %s", completed.returncode, completed.stderr)
            raise AntigravityPromptExecutionError(
                f"Antigravity CLI exited with code {completed.returncode}: {completed.stderr}",
                code="cli_error",
                stage="execution",
                technical_error=completed.stderr,
            )

        raw_sha256 = hashlib.sha256(raw_output.encode("utf-8")).hexdigest()

        cleaned_output, was_unwrapped = _clean_markdown_fence(raw_output)
        normalizations = ("unwrapped_markdown_code_block",) if was_unwrapped else ()

        try:
            parsed_result = parse_prompt_result(cleaned_output)
        except (PromptContractError, PromptCompilerError) as exc:
            logger.error("[Antigravity] Output parsing failed: %s. Raw output: %s", exc, raw_output[:300])
            raise AntigravityPromptExecutionError(
                f"Failed to parse Antigravity output into PromptResult: {exc}",
                code="contract_violation",
                stage="normalization",
                technical_error=raw_output,
            ) from exc

        return AntigravityPromptExecutionResult(
            result=parsed_result,
            bundle=instruction_bundle,
            latency_ms=elapsed_ms,
            raw_response_sha256=raw_sha256,
            response_normalizations=normalizations,
        )


__all__ = [
    "AntigravityPromptExecutionError",
    "AntigravityPromptExecutionResult",
    "AntigravityPromptExecutor",
]
