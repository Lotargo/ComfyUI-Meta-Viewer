from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

from .cli import CLIIntegrationError, discover_cli_integrations, list_cli_models
from .profiles import AIProfileStore, AIProfileStoreError
from .secrets import SecretStoreError
from .transport import AIProviderRequestError, test_profile


ai_blueprint = Blueprint("ai", __name__)


def _store() -> AIProfileStore:
    return AIProfileStore(
        Path(current_app.config["CONFIG_FILE"]),
        secret_store=current_app.config.get("AI_SECRET_STORE"),
    )


def _json_object() -> dict:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise AIProfileStoreError("A JSON object is required.")
    return payload


@ai_blueprint.errorhandler(AIProfileStoreError)
def profile_error(error: AIProfileStoreError):
    if error.code == "profile_not_found":
        status = 404
    elif error.code == "missing_credentials":
        status = 409
    else:
        status = 400
    return jsonify({"error": str(error), "code": error.code}), status


@ai_blueprint.errorhandler(SecretStoreError)
def secret_store_error(error: SecretStoreError):
    return jsonify({"error": str(error), "code": "secret_store_unavailable"}), 503


@ai_blueprint.errorhandler(CLIIntegrationError)
def cli_error(error: CLIIntegrationError):
    status = 404 if error.code == "cli_unavailable" else 422
    return jsonify({"error": str(error), "code": error.code}), status


@ai_blueprint.route("/settings/ai")
def ai_settings_page():
    return render_template("ai_settings.html")


@ai_blueprint.route("/api/ai/profiles", methods=["GET", "POST"])
def ai_profiles():
    store = _store()
    if request.method == "GET":
        return jsonify(store.list())
    return jsonify({"profile": store.create(_json_object())}), 201


@ai_blueprint.route("/api/ai/profiles/<profile_id>", methods=["PATCH", "DELETE"])
def ai_profile(profile_id: str):
    store = _store()
    if request.method == "DELETE":
        store.delete(profile_id)
        return jsonify({"ok": True})
    return jsonify({"profile": store.update(profile_id, _json_object())})


@ai_blueprint.route("/api/ai/defaults", methods=["PATCH"])
def ai_defaults():
    return jsonify({"defaults": _store().set_defaults(_json_object())})


@ai_blueprint.route("/api/ai/profiles/<profile_id>/test", methods=["POST"])
def ai_profile_test(profile_id: str):
    store = _store()
    profile = store.get(profile_id)
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        raise AIProfileStoreError("A JSON object is required.")
    try:
        result = test_profile(
            store,
            profile,
            multimodal=payload.get("multimodal") is True,
        )
    except AIProviderRequestError as exc:
        status = 504 if exc.code == "timeout" else 422
        return jsonify({
            "error": str(exc),
            "code": exc.code,
            "technical_error": exc.technical_error,
        }), status
    return jsonify(result)


@ai_blueprint.route("/api/ai/cli-integrations", methods=["GET"])
def ai_cli_integrations():
    return jsonify({"integrations": discover_cli_integrations()})


@ai_blueprint.route("/api/ai/cli-integrations/<cli_type>/models", methods=["GET"])
def ai_cli_models(cli_type: str):
    return jsonify(list_cli_models(cli_type))
