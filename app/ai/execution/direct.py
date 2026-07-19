from __future__ import annotations

import base64
import binascii
import hashlib
import re
from dataclasses import dataclass
from typing import Any

from ..prompting import (
    InstructionBundle,
    PromptCompiler,
    PromptCompilerError,
    PromptContractError,
    PromptResult,
    PromptTask,
    parse_prompt_result,
)
from ..transport import AIProviderRequestError, run_openai_compatible_chat


MAX_USER_INPUT_CHARS = 100_000
MAX_IMAGE_BYTES = 20 * 1024 * 1024
_IMAGE_DATA_URL_RE = re.compile(
    r"^data:image/(?P<subtype>png|jpeg|jpg|webp|gif);base64,(?P<payload>[A-Za-z0-9+/=\r\n]+)$",
    re.IGNORECASE,
)


class DirectPromptExecutionError(RuntimeError):
    """Normalized error raised by the direct model execution path."""

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
class DirectPromptExecutionResult:
    result: PromptResult
    bundle: InstructionBundle
    latency_ms: int
    raw_response_sha256: str
    transport: str = "openai_compatible"

    def metadata(self) -> dict[str, Any]:
        return {
            "transport": self.transport,
            "latency_ms": self.latency_ms,
            "raw_response_sha256": self.raw_response_sha256,
            "bundle": self.bundle.metadata(),
        }


class DirectPromptExecutor:
    """Compile and execute one PromptTask through an OpenAI-compatible profile.

    The executor owns no provider credentials and persists no state. Callers pass
    a resolved profile plus its API key, then store the returned normalized result
    and metadata in the job/draft layer.
    """

    def __init__(self, compiler: PromptCompiler | None = None):
        self.compiler = compiler or PromptCompiler()

    def execute(
        self,
        *,
        profile: dict[str, Any],
        api_key: str | None,
        task: PromptTask,
        user_input: str,
        image_data_url: str | None = None,
    ) -> DirectPromptExecutionResult:
        if profile.get("kind", "openai_compatible") != "openai_compatible":
            raise DirectPromptExecutionError(
                "This operation requires an OpenAI-compatible profile.",
                code="incompatible_profile",
                stage="input",
            )
        cleaned_input = self._validate_user_input(user_input)
        cleaned_image = self._validate_image_data_url(image_data_url)
        if cleaned_image is not None and profile.get("multimodal") is not True:
            raise DirectPromptExecutionError(
                "This profile is not marked as multimodal.",
                code="incompatible_format",
                stage="input",
            )

        try:
            bundle = self.compiler.compile(task)
        except PromptCompilerError as exc:
            raise DirectPromptExecutionError(
                str(exc),
                code="prompt_compile_error",
                stage="compile",
                technical_error=str(exc),
            ) from exc

        user_text = "USER TASK INPUT\n" + cleaned_input
        if cleaned_image is None:
            user_content: str | list[dict[str, Any]] = user_text
        else:
            user_content = [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {"url": cleaned_image, "detail": "auto"},
                },
            ]

        try:
            response = run_openai_compatible_chat(
                profile,
                api_key=api_key,
                messages=[
                    {"role": "system", "content": bundle.render()},
                    {"role": "user", "content": user_content},
                ],
            )
        except AIProviderRequestError as exc:
            raise DirectPromptExecutionError(
                str(exc),
                code=exc.code,
                stage="transport",
                technical_error=exc.technical_error,
            ) from exc

        try:
            result = parse_prompt_result(response.text)
        except PromptContractError as exc:
            raise DirectPromptExecutionError(
                str(exc),
                code=exc.code,
                stage="contract",
                technical_error=exc.technical_error,
            ) from exc

        return DirectPromptExecutionResult(
            result=result,
            bundle=bundle,
            latency_ms=response.latency_ms,
            raw_response_sha256=hashlib.sha256(
                response.text.encode("utf-8")
            ).hexdigest(),
        )

    @staticmethod
    def _validate_user_input(value: str) -> str:
        if not isinstance(value, str):
            raise DirectPromptExecutionError(
                "Prompt task input must be text.",
                code="invalid_input",
                stage="input",
            )
        cleaned = value.strip()
        if not cleaned:
            raise DirectPromptExecutionError(
                "Prompt task input cannot be empty.",
                code="invalid_input",
                stage="input",
            )
        if len(cleaned) > MAX_USER_INPUT_CHARS:
            raise DirectPromptExecutionError(
                "Prompt task input is too large.",
                code="input_too_large",
                stage="input",
            )
        return cleaned

    @staticmethod
    def _validate_image_data_url(value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise DirectPromptExecutionError(
                "Image input must be a base64 data URL.",
                code="invalid_image",
                stage="input",
            )
        cleaned = value.strip()
        match = _IMAGE_DATA_URL_RE.fullmatch(cleaned)
        if match is None:
            raise DirectPromptExecutionError(
                "Image input must be a supported base64 image data URL.",
                code="invalid_image",
                stage="input",
            )
        try:
            decoded = base64.b64decode(
                re.sub(r"\s+", "", match.group("payload")),
                validate=True,
            )
        except (binascii.Error, ValueError) as exc:
            raise DirectPromptExecutionError(
                "Image input contains invalid base64 data.",
                code="invalid_image",
                stage="input",
                technical_error=str(exc),
            ) from exc
        if not decoded:
            raise DirectPromptExecutionError(
                "Image input is empty.",
                code="invalid_image",
                stage="input",
            )
        if len(decoded) > MAX_IMAGE_BYTES:
            raise DirectPromptExecutionError(
                "Image input is too large.",
                code="image_too_large",
                stage="input",
            )
        return cleaned
