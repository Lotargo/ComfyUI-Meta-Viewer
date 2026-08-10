from __future__ import annotations

import os
from typing import cast

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from .base import SocialNotImplementedError, SocialPublisher
from .contract import (
    PROVIDERS,
    Provider,
    PublishRequest,
    SocialContractError,
    validate_publish_payload,
)
from .instagram import InstagramPublisher
from .secrets import SocialSecretStore
from .telegram import TelegramPublisher
from .vk import VKPublisher

social_blueprint = Blueprint("social", __name__)

PUBLISHERS: dict[str, SocialPublisher] = {
    "telegram": TelegramPublisher(),
    "vk": VKPublisher(),
    "instagram": InstagramPublisher(),
}


def _store() -> SocialSecretStore:
    return SocialSecretStore()


def _tg() -> TelegramPublisher:
    publisher = PUBLISHERS["telegram"]
    return publisher if isinstance(publisher, TelegramPublisher) else TelegramPublisher()


def _vk() -> VKPublisher:
    publisher = PUBLISHERS["vk"]
    return publisher if isinstance(publisher, VKPublisher) else VKPublisher()


def _publisher_status(provider: str) -> dict | None:
    """Best-effort live status for implemented publishers (identity info)."""
    publisher = PUBLISHERS[provider]
    try:
        status = publisher.status()
    except SocialNotImplementedError:
        return None
    if not isinstance(status, dict):
        return None
    return status


def _validation_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        loc = ".".join(str(part) for part in first.get("loc", ()))
        message = first.get("msg", str(exc))
        return f"{loc}: {message}" if loc else message
    return str(exc)


def _json_object() -> dict:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise SocialContractError("A JSON object is required.")
    return payload


def _provider_or_404(provider: str) -> Provider | None:
    if provider not in PROVIDERS:
        return None
    return cast(Provider, provider)


def _telegram_enabled() -> bool:
    """Telegram is an optional adapter (registration-required), hidden by default.

    Opt in per deployment with SOCIAL_TELEGRAM_ENABLED=1 (or true/yes/on).
    """
    value = os.environ.get("SOCIAL_TELEGRAM_ENABLED", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _provider_enabled(provider: str) -> bool:
    if provider == "telegram":
        return _telegram_enabled()
    return True


def _telegram_not_enabled():
    return _json_error({
        "error": (
            "The Telegram adapter is not enabled. "
            "Set SOCIAL_TELEGRAM_ENABLED=1 to enable it."
        ),
        "code": "not_enabled",
    }, 404)


@social_blueprint.route("/api/social/status", methods=["GET"])
def social_status_all():
    store = _store()
    result: dict = {}
    for provider in PROVIDERS:
        publisher = PUBLISHERS[provider]
        result[provider] = {
            "label": publisher.label,
            "implemented": publisher.implemented,
            "enabled": _provider_enabled(provider),
            **store.status(provider).to_dict(),
            "publisher": _publisher_status(provider),
        }
    return jsonify({"providers": result})


@social_blueprint.route("/api/social/<provider>/status", methods=["GET"])
def social_provider_status(provider: str):
    resolved = _provider_or_404(provider)
    if resolved is None:
        return jsonify({
            "error": f"Unknown provider {provider!r}",
            "code": "unknown_provider",
        }), 404
    publisher = PUBLISHERS[resolved]
    return jsonify({
        "provider": resolved,
        "label": publisher.label,
        "implemented": publisher.implemented,
        "enabled": _provider_enabled(resolved),
        **_store().status(resolved).to_dict(),
        "publisher": _publisher_status(resolved),
    })


def _dispatch_publish(request_data: PublishRequest):
    if request_data.provider == "telegram" and not _telegram_enabled():
        return _telegram_not_enabled()
    publisher = PUBLISHERS[request_data.provider]
    try:
        result = publisher.publish(request_data)
    except SocialNotImplementedError as exc:
        return jsonify({
            "error": str(exc),
            "code": "not_implemented",
            "provider": request_data.provider,
        }), 501
    return jsonify(result.model_dump())


@social_blueprint.route("/api/social/publish", methods=["POST"])
def social_publish():
    try:
        request_data = validate_publish_payload(_json_object())
    except (ValidationError, SocialContractError) as exc:
        return jsonify({
            "error": _validation_message(exc),
            "code": "invalid_payload",
        }), 400
    return _dispatch_publish(request_data)


@social_blueprint.route("/api/social/<provider>/publish", methods=["POST"])
def social_provider_publish(provider: str):
    resolved = _provider_or_404(provider)
    if resolved is None:
        return jsonify({
            "error": f"Unknown provider {provider!r}",
            "code": "unknown_provider",
        }), 404
    try:
        request_data = validate_publish_payload(_json_object(), provider=resolved)
    except (ValidationError, SocialContractError) as exc:
        return jsonify({
            "error": _validation_message(exc),
            "code": "invalid_payload",
        }), 400
    return _dispatch_publish(request_data)


def _json_error(payload: dict, status: int):
    return jsonify(payload), status


@social_blueprint.route("/api/social/telegram/auth/start", methods=["POST"])
def telegram_auth_start():
    if not _telegram_enabled():
        return _telegram_not_enabled()
    body = request.get_json(silent=True) or {}
    phone = body.get("phone") if isinstance(body, dict) else None
    code, payload = _tg().auth_start(phone=phone)
    return _json_error(payload, code)


@social_blueprint.route("/api/social/telegram/auth/state", methods=["GET"])
def telegram_auth_state():
    if not _telegram_enabled():
        return _telegram_not_enabled()
    return jsonify(_tg().auth_state())


@social_blueprint.route("/api/social/telegram/auth/qr.png", methods=["GET"])
def telegram_auth_qr_png():
    if not _telegram_enabled():
        return _telegram_not_enabled()
    publisher = _tg()
    state = publisher.auth_state()
    if state.get("state") != "qr_waiting" or not state.get("qr_url"):
        return _json_error({
            "error": "No QR code is pending.",
            "code": "not_in_flow",
        }, 409)
    try:
        import qrcode
    except ImportError:
        return _json_error({
            "error": "qrcode is not installed.",
            "code": "missing_dependency",
        }, 500)
    qr = qrcode.QRCode(box_size=8, border=1)
    qr.add_data(state["qr_url"])
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    import io

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return (
        buffer.getvalue(),
        200,
        {"Content-Type": "image/png", "Cache-Control": "no-store"},
    )


@social_blueprint.route("/api/social/telegram/auth/code", methods=["POST"])
def telegram_auth_code():
    if not _telegram_enabled():
        return _telegram_not_enabled()
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("code"), str):
        return _json_error({
            "error": "code is required.",
            "code": "invalid_payload",
        }, 400)
    code, payload = _tg().auth_submit_code(body["code"])
    return _json_error(payload, code)


@social_blueprint.route("/api/social/telegram/auth/password", methods=["POST"])
def telegram_auth_password():
    if not _telegram_enabled():
        return _telegram_not_enabled()
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("password"), str):
        return _json_error({
            "error": "password is required.",
            "code": "invalid_payload",
        }, 400)
    code, payload = _tg().auth_submit_password(body["password"])
    return _json_error(payload, code)


@social_blueprint.route("/api/social/telegram/auth/cancel", methods=["POST"])
def telegram_auth_cancel():
    if not _telegram_enabled():
        return _telegram_not_enabled()
    code, payload = _tg().auth_cancel()
    return _json_error(payload, code)


@social_blueprint.route("/api/social/telegram/auth/disconnect", methods=["POST"])
def telegram_auth_disconnect():
    if not _telegram_enabled():
        return _telegram_not_enabled()
    code, payload = _tg().auth_disconnect()
    return _json_error(payload, code)


@social_blueprint.route("/api/social/vk/auth/start", methods=["POST"])
def vk_auth_start():
    code, payload = _vk().auth_start()
    return _json_error(payload, code)


@social_blueprint.route("/api/social/vk/auth/callback", methods=["GET"])
def vk_auth_callback():
    """Browser OAuth callback for VK ID. Exchange the code, then redirect
    back to the settings page so the browser window can close itself."""
    publisher = _vk()
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")
    if error or not code:
        publisher.auth_disconnect()
        return _json_error({
            "error": error or "VK authorization was cancelled.",
            "code": "auth_cancelled",
        }, 400)
    status, payload = publisher.auth_submit_code(code, state=state)
    if status != 200:
        return _json_error(payload, status)
    return (
        (
            "<!doctype html><html><body style='font-family:system-ui;"
            "padding:2rem'><h2>Authorization complete</h2><p>You can close "
            "this tab and return to ComfyUI Meta Viewer.</p></body></html>"
        ),
        200,
        {"Content-Type": "text/html; charset=utf-8"},
    )


@social_blueprint.route("/api/social/vk/auth/disconnect", methods=["POST"])
def vk_auth_disconnect():
    code, payload = _vk().auth_disconnect()
    return _json_error(payload, code)
