from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .cli import CLIIntegrationError, run_cli_test, sanitize_output
from .profiles import AIProfileStore


TEST_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR42mOQaMgD"
    "AAG6AQf4Lfx6AAAAAElFTkSuQmCC"
)
CONTENT_REJECTED_MESSAGE = (
    "Провайдер или выбранная модель отклонили изображение из-за ограничений "
    "обработки контента. Выберите другой настроенный профиль и повторите попытку."
)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class AIProviderRequestError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        technical_error: str | None = None,
    ):
        self.code = code
        self.technical_error = technical_error
        super().__init__(message)


@dataclass(frozen=True)
class OpenAICompatibleResponse:
    text: str
    latency_ms: int


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, _request, _fp, _code, _message, _headers, _new_url):
        return None


def _open_url(request: urllib.request.Request, *, timeout: int):
    # Refuse redirects so an Authorization header cannot be forwarded to another origin.
    return urllib.request.build_opener(_NoRedirectHandler()).open(
        request, timeout=timeout
    )


def _redact(value: str, api_key: str | None = None) -> str:
    sanitized = sanitize_output(value, maximum=16_000)
    if api_key:
        sanitized = sanitized.replace(api_key, "[redacted]")
    return sanitized


def _extract_error(body: bytes, api_key: str | None) -> tuple[str, str]:
    raw = body.decode("utf-8", errors="replace")[:64_000]
    message = raw
    code = ""
    try:
        payload = json.loads(raw)
        error = payload.get("error", payload) if isinstance(payload, dict) else payload
        if isinstance(error, dict):
            message = str(error.get("message") or error.get("detail") or raw)
            code = str(error.get("code") or error.get("type") or "")
        elif isinstance(error, str):
            message = error
    except json.JSONDecodeError:
        pass
    return _redact(message, api_key), _redact(code, api_key)


def _classify_provider_error(status: int, message: str, provider_code: str) -> str:
    combined = f"{provider_code} {message}".lower()
    if any(
        marker in combined
        for marker in (
            "content_policy",
            "content policy",
            "moderation",
            "safety policy",
            "unsafe content",
            "blocked_reason",
        )
    ):
        return "content_rejected"
    if status in {401, 403} or any(
        marker in combined
        for marker in ("invalid api key", "authentication", "unauthorized")
    ):
        return "authentication_error"
    if any(
        marker in combined
        for marker in (
            "image input is not supported",
            "does not support image",
            "unsupported image",
            "vision is not supported",
            "multimodal is not supported",
            "invalid image",
        )
    ):
        return "incompatible_format"
    return "provider_error"


def _response_text(payload: Any) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIProviderRequestError(
            "The provider returned an incompatible response format.",
            code="incompatible_format",
            technical_error=_redact(json.dumps(payload, ensure_ascii=False)[:16_000]),
        ) from exc
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        return "".join(parts).strip()
    raise AIProviderRequestError(
        "The provider returned an incompatible response format.",
        code="incompatible_format",
    )


def _chat_completions_endpoint(base_url: str) -> str:
    endpoint = base_url.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint = f"{endpoint}/chat/completions"
    return endpoint


def run_openai_compatible_chat(
    profile: dict[str, Any],
    *,
    api_key: str | None,
    messages: list[dict[str, Any]],
) -> OpenAICompatibleResponse:
    """Execute one non-streaming OpenAI-compatible chat completion.

    Provider-specific optional request fields come from ``extra_body``. Critical
    fields are always replaced by the selected profile and caller messages so a
    saved profile cannot silently redirect the model, inject messages, or enable
    streaming in a code path that expects one bounded JSON response.
    """
    if profile.get("kind", "openai_compatible") != "openai_compatible":
        raise AIProviderRequestError(
            "This operation requires an OpenAI-compatible profile.",
            code="incompatible_profile",
        )
    if not isinstance(messages, list) or not messages:
        raise AIProviderRequestError(
            "At least one chat message is required.",
            code="incompatible_format",
        )

    body = dict(profile.get("extra_body") or {})
    body.update({
        "model": profile["model"],
        "messages": messages,
        "stream": False,
    })
    endpoint = _chat_completions_endpoint(profile["base_url"])
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    started = time.monotonic()
    try:
        with _open_url(request, timeout=profile["timeout_seconds"]) as response:
            raw = response.read(MAX_RESPONSE_BYTES)
    except urllib.error.HTTPError as exc:
        message, provider_code = _extract_error(exc.read(64_000), api_key)
        code = _classify_provider_error(exc.code, message, provider_code)
        user_message = CONTENT_REJECTED_MESSAGE if code == "content_rejected" else message
        raise AIProviderRequestError(
            user_message or f"Provider returned HTTP {exc.code}.",
            code=code,
            technical_error=f"HTTP {exc.code}: {message}"[:16_000],
        ) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise AIProviderRequestError(
            f"The provider did not respond within {profile['timeout_seconds']} seconds.",
            code="timeout",
        ) from exc
    except urllib.error.URLError as exc:
        reason = _redact(str(exc.reason), api_key)
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            code = "timeout"
            message = (
                f"The provider did not respond within "
                f"{profile['timeout_seconds']} seconds."
            )
        else:
            code = "network_error"
            message = f"Cannot connect to the provider: {reason}"
        raise AIProviderRequestError(
            message, code=code, technical_error=reason
        ) from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AIProviderRequestError(
            "The provider returned invalid JSON.",
            code="incompatible_format",
            technical_error=_redact(raw.decode("utf-8", errors="replace"), api_key),
        ) from exc
    result = _response_text(payload)
    if not result:
        raise AIProviderRequestError(
            "The provider returned an empty response.", code="incompatible_format"
        )
    return OpenAICompatibleResponse(
        text=result,
        latency_ms=round((time.monotonic() - started) * 1000),
    )


def run_openai_compatible_test(
    profile: dict[str, Any],
    *,
    api_key: str | None,
    multimodal: bool = False,
) -> dict[str, Any]:
    if multimodal and not profile["multimodal"]:
        raise AIProviderRequestError(
            "This profile is not marked as multimodal.", code="incompatible_format"
        )
    prompt = "Reply with exactly CMV_OK and no other text."
    if multimodal:
        content: str | list[dict[str, Any]] = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{TEST_PNG_BASE64}",
                    "detail": "low",
                },
            },
        ]
    else:
        content = prompt

    response = run_openai_compatible_chat(
        profile,
        api_key=api_key,
        messages=[{"role": "user", "content": content}],
    )
    return {
        "ok": True,
        "transport": "openai_compatible",
        "latency_ms": response.latency_ms,
        "response_preview": response.text[:500],
    }


def test_profile(
    store: AIProfileStore,
    profile: dict[str, Any],
    *,
    multimodal: bool = False,
) -> dict[str, Any]:
    try:
        if profile["kind"] == "cli":
            return run_cli_test(profile, multimodal=multimodal)
        return run_openai_compatible_test(
            profile,
            api_key=store.resolve_api_key(profile),
            multimodal=multimodal,
        )
    except CLIIntegrationError as exc:
        raise AIProviderRequestError(
            str(exc), code=exc.code, technical_error=str(exc)
        ) from exc
