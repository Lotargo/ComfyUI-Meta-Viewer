from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..cli import CLIIntegrationError, find_executable, run_command
from ..judging import (
    IntentJudgeContractError,
    IntentJudgeResult,
    parse_intent_judge_result,
)
from ..prompting import PromptResult
from .opencode import OpenCodePromptExecutor


OPENCODE_JUDGE_AGENT_NAME = "cmv-intent-judge"
MAX_JUDGE_INPUT_CHARS = 120_000


class OpenCodeIntentJudgeExecutionError(RuntimeError):
    """Normalized failure raised by the managed OpenCode judge path."""

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
class OpenCodeIntentJudgeExecutionResult:
    result: IntentJudgeResult
    latency_ms: int
    raw_response_sha256: str
    transport: str = "opencode"
    agent: str = OPENCODE_JUDGE_AGENT_NAME
    response_normalizations: tuple[str, ...] = ()

    def metadata(self) -> dict[str, Any]:
        return {
            "transport": self.transport,
            "agent": self.agent,
            "latency_ms": self.latency_ms,
            "raw_response_sha256": self.raw_response_sha256,
            "response_normalizations": list(self.response_normalizations),
        }


class OpenCodeIntentJudgeExecutor:
    """Evaluate one generated prompt through an isolated, tool-denied OpenCode agent."""

    def execute(
        self,
        *,
        profile: dict[str, Any],
        family: str,
        user_request: str,
        candidate: PromptResult,
        required_intents: tuple[str, ...] = (),
    ) -> OpenCodeIntentJudgeExecutionResult:
        try:
            OpenCodePromptExecutor._validate_profile(profile)
            timeout_seconds = OpenCodePromptExecutor._resolve_timeout(profile)
        except Exception as exc:
            if hasattr(exc, "code") and hasattr(exc, "stage"):
                raise OpenCodeIntentJudgeExecutionError(
                    str(exc),
                    code=getattr(exc, "code"),
                    stage=getattr(exc, "stage"),
                    technical_error=getattr(exc, "technical_error", None),
                ) from exc
            raise

        cleaned_family = self._clean_text(family, "Model family", maximum=80)
        cleaned_request = self._clean_text(
            user_request,
            "User request",
            maximum=MAX_JUDGE_INPUT_CHARS,
        )
        cleaned_intents = tuple(
            self._clean_text(item, "Required intent", maximum=120)
            for item in required_intents
        )
        executable = find_executable("opencode", profile.get("executable"))
        if executable is None:
            raise OpenCodeIntentJudgeExecutionError(
                "OpenCode was not found in PATH or at the configured executable path.",
                code="cli_unavailable",
                stage="judge_host",
            )

        try:
            with tempfile.TemporaryDirectory(prefix="cmv-opencode-judge-") as temp_dir:
                workspace = Path(temp_dir)
                self._write_isolated_config(workspace)
                task_file = workspace / "cmv-judge-task.md"
                task_file.write_text(
                    self._render_judge_package(
                        family=cleaned_family,
                        user_request=cleaned_request,
                        candidate=candidate,
                        required_intents=cleaned_intents,
                    ),
                    encoding="utf-8",
                    newline="\n",
                )
                prompt = (
                    "Evaluate the attached candidate independently using the exact rubric. "
                    "Assume it came from an unknown system. Do not use tools or external context. "
                    "Return only the required strict JSON object without Markdown fences."
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
                    OPENCODE_JUDGE_AGENT_NAME,
                    "--title",
                    "ComfyUI Meta Viewer intent judge",
                    prompt,
                    f"--file={task_file}",
                ]
                command = run_command(
                    args,
                    timeout=timeout_seconds,
                    cwd=workspace,
                )
        except CLIIntegrationError as exc:
            raise OpenCodeIntentJudgeExecutionError(
                str(exc),
                code=exc.code,
                stage="judge_host",
                technical_error=str(exc),
            ) from exc
        except OSError as exc:
            raise OpenCodeIntentJudgeExecutionError(
                f"Cannot prepare the isolated OpenCode judge task: {exc}",
                code="judge_workspace_error",
                stage="judge_host",
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
                else "judge_provider_error"
            )
            raise OpenCodeIntentJudgeExecutionError(
                combined_output or "OpenCode judge request failed.",
                code=code,
                stage="judge_host",
                technical_error=combined_output[:16_000] or None,
            )

        raw_text = OpenCodePromptExecutor._parse_json_events(command.stdout)
        if not raw_text:
            raise OpenCodeIntentJudgeExecutionError(
                "OpenCode returned no judge text in its JSON event stream.",
                code="incompatible_judge_format",
                stage="judge_host",
                technical_error=combined_output[:16_000] or None,
            )
        normalized_text, response_normalizations = (
            OpenCodePromptExecutor._normalize_response(raw_text)
        )
        try:
            result = parse_intent_judge_result(normalized_text)
        except IntentJudgeContractError as exc:
            raise OpenCodeIntentJudgeExecutionError(
                str(exc),
                code=exc.code,
                stage="judge_contract",
                technical_error=exc.technical_error,
            ) from exc

        return OpenCodeIntentJudgeExecutionResult(
            result=result,
            latency_ms=command.elapsed_ms,
            raw_response_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            response_normalizations=response_normalizations,
        )

    @staticmethod
    def _clean_text(value: str, field: str, *, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip():
            raise OpenCodeIntentJudgeExecutionError(
                f"{field} is required.",
                code="invalid_judge_input",
                stage="judge_input",
            )
        cleaned = value.strip()
        if len(cleaned) > maximum:
            raise OpenCodeIntentJudgeExecutionError(
                f"{field} is too large.",
                code="judge_input_too_large",
                stage="judge_input",
            )
        return cleaned

    @staticmethod
    def _write_isolated_config(workspace: Path) -> None:
        config = {
            "$schema": "https://opencode.ai/config.json",
            "share": "disabled",
            "agent": {
                OPENCODE_JUDGE_AGENT_NAME: {
                    "description": "Score one generated image prompt without tools.",
                    "mode": "primary",
                    "permission": {"*": "deny"},
                    "prompt": (
                        "You are a strict image-prompt evaluator. Judge independently, "
                        "do not reward verbosity, and return strict JSON only."
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
    def _family_policy(family: str) -> str:
        normalized = family.casefold()
        if normalized == "flux":
            return (
                "- FLUX family rule: an empty negative_prompt is correct and must not be "
                "penalized or listed as a weakness. Do not request a negative prompt.\n"
                "- Judge the positive prompt as coherent natural-language scene direction; "
                "do not require tag-style syntax."
            )
        if normalized == "sdxl":
            return (
                "- SDXL family rule: accept a coherent natural-language, tag-oriented, "
                "or hybrid positive prompt. Do not require magic quality tokens.\n"
                "- A targeted negative prompt is allowed but not mandatory; judge it for "
                "relevance rather than length."
            )
        if normalized == "pony":
            return (
                "- Pony base-family project default: expect the complete score_9 through "
                "score_4_up prefix, one appropriate source_* tag, and the safe modifier's "
                "rating_safe tag.\n"
                "- Pony may use tags, concise natural language, or a coherent hybrid. An "
                "empty negative_prompt is acceptable for the base family."
            )
        return "- Apply the normal conventions of the named model family."

    @classmethod
    def _render_judge_package(
        cls,
        *,
        family: str,
        user_request: str,
        candidate: PromptResult,
        required_intents: tuple[str, ...] = (),
    ) -> str:
        intent_lines = (
            "\n".join(f"- {item}" for item in required_intents)
            if required_intents
            else "- Infer the requested intent dimensions from the original request."
        )
        return f"""# CMV intent benchmark judge task

Evaluate the candidate as if it came from an unknown system. The original request is intentionally short and incomplete. Reward useful visual decisions that preserve its intent. Do not reward length by itself. Penalize restatement, contradictions, generic quality slogans, and details that distort the user's goal.

MODEL FAMILY
{family}

FAMILY-SPECIFIC POLICY
{cls._family_policy(family)}

REQUIRED INTENT DIMENSIONS
{intent_lines}

Evaluate every required intent dimension independently. A vague repetition of an adjective is weaker than translating it into visible choices. If any required dimension is not visually translated, mention it in weaknesses and do not award more than 10/15 for atmosphere_translation.

ORIGINAL HUMAN REQUEST
{user_request}

CANDIDATE POSITIVE PROMPT
{candidate.positive_prompt}

CANDIDATE NEGATIVE PROMPT
{candidate.negative_prompt or '<empty>'}

SCORING RUBRIC — exactly 100 points
- intent_fidelity: 0-20. Preserve subject, setting, adulthood, action, and every requested mood direction without contradiction.
- useful_visual_expansion: 0-20. Add concrete, useful visual decisions rather than merely paraphrasing the request.
- atmosphere_translation: 0-15. Translate each required mood direction into visible choices such as palette, texture, framing, depth, styling, and light.
- composition_and_camera: 0-10. Provide a coherent framing or camera strategy appropriate to the request.
- lighting: 0-10. Provide motivated light with useful direction, quality, contrast, or colour relationships.
- environment_and_materials: 0-10. Make the setting and surfaces visually specific and relevant.
- coherence_and_model_fit: 0-10. Produce one coherent prompt suited to the named model family and its family-specific policy.
- restraint_and_consistency: 0-5. Avoid contradictions, gratuitous invention, repetition, and generic quality slogans.

Return exactly this JSON object and no other text:
{{
  "schema_version": "1",
  "scores": {{
    "intent_fidelity": 0,
    "useful_visual_expansion": 0,
    "atmosphere_translation": 0,
    "composition_and_camera": 0,
    "lighting": 0,
    "environment_and_materials": 0,
    "coherence_and_model_fit": 0,
    "restraint_and_consistency": 0
  }},
  "strengths": ["up to five concise evidence-based observations"],
  "weaknesses": ["up to five concise evidence-based observations"],
  "rationale": "A concise explanation grounded in the original request and candidate."
}}
"""
