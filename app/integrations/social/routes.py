from __future__ import annotations

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


@social_blueprint.route("/api/social/status", methods=["GET"])
def social_status_all():
    store = _store()
    result: dict = {}
    for provider in PROVIDERS:
        publisher = PUBLISHERS[provider]
        result[provider] = {
            "label": publisher.label,
            "implemented": publisher.implemented,
            **store.status(provider).to_dict(),
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
        **_store().status(resolved).to_dict(),
    })


def _dispatch_publish(request_data: PublishRequest):
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
