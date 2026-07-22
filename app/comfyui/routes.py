from __future__ import annotations

from pathlib import Path
from flask import Blueprint, current_app, jsonify, render_template, request

from app.config_store import ConfigStore
from .detector import detect_comfyui
from .launcher import generate_launcher_script
from .manager import ComfyUIMode, comfy_manager

comfyui_blueprint = Blueprint("comfyui", __name__)


def _config_store() -> ConfigStore:
    return current_app.config["CONFIG_STORE"]


@comfyui_blueprint.route("/settings/comfyui")
def comfyui_settings_page():
    return render_template("comfyui_settings.html")


@comfyui_blueprint.route("/api/comfyui/config", methods=["GET", "POST"])
def comfyui_config():
    store = _config_store()
    if request.method == "GET":
        settings = store.comfyui_settings()
        return jsonify(settings)

    payload = request.get_json(silent=True) or {}
    updated = store.update_comfyui_settings(
        install_path=payload.get("install_path"),
        custom_python=payload.get("custom_python"),
        host=payload.get("host"),
        port=payload.get("port"),
        extra_args=payload.get("extra_args"),
        auto_start=payload.get("auto_start"),
    )
    return jsonify(updated)


@comfyui_blueprint.route("/api/comfyui/detect", methods=["POST"])
def comfyui_detect():
    payload = request.get_json(silent=True) or {}
    path = payload.get("path", "")
    custom_python = payload.get("custom_python")
    result = detect_comfyui(path, custom_python=custom_python)
    return jsonify(result.to_dict())


@comfyui_blueprint.route("/api/comfyui/status", methods=["GET"])
def comfyui_status():
    store = _config_store()
    cfg = store.comfyui_settings()
    host = cfg.get("host") or "127.0.0.1"
    port = int(cfg.get("port") or 8188)

    # Check external or update status
    status_data = comfy_manager.check_external_or_status(host=host, port=port)
    info = comfy_manager.get_info()
    info.update(status_data)
    return jsonify(info)


@comfyui_blueprint.route("/api/comfyui/start", methods=["POST"])
def comfyui_start():
    payload = request.get_json(silent=True) or {}
    store = _config_store()
    cfg = store.comfyui_settings()

    install_path = payload.get("install_path") or cfg.get("install_path")
    if not install_path:
        return jsonify({"error": "No installation path specified", "code": "missing_path"}), 400

    host = payload.get("host") or cfg.get("host") or "127.0.0.1"
    port = int(payload.get("port") or cfg.get("port") or 8188)
    extra_args = payload.get("extra_args") if "extra_args" in payload else cfg.get("extra_args")
    custom_python = payload.get("custom_python") if "custom_python" in payload else cfg.get("custom_python")

    try:
        info = comfy_manager.start_managed(
            install_path=install_path,
            host=host,
            port=port,
            extra_args=extra_args,
            custom_python=custom_python,
        )
        return jsonify(info)
    except Exception as exc:
        return jsonify({"error": str(exc), "code": "start_failed"}), 422


@comfyui_blueprint.route("/api/comfyui/stop", methods=["POST"])
def comfyui_stop():
    if comfy_manager.mode == ComfyUIMode.EXTERNAL:
        return jsonify({"error": "Cannot stop external ComfyUI process", "code": "external_process"}), 400

    comfy_manager.stop_managed()
    return jsonify(comfy_manager.get_info())


@comfyui_blueprint.route("/api/comfyui/restart", methods=["POST"])
def comfyui_restart():
    payload = request.get_json(silent=True) or {}
    store = _config_store()
    cfg = store.comfyui_settings()

    install_path = payload.get("install_path") or cfg.get("install_path")
    host = payload.get("host") or cfg.get("host") or "127.0.0.1"
    port = int(payload.get("port") or cfg.get("port") or 8188)
    extra_args = payload.get("extra_args") if "extra_args" in payload else cfg.get("extra_args")
    custom_python = payload.get("custom_python") if "custom_python" in payload else cfg.get("custom_python")

    try:
        info = comfy_manager.restart_managed(
            install_path=install_path,
            host=host,
            port=port,
            extra_args=extra_args,
            custom_python=custom_python,
        )
        return jsonify(info)
    except Exception as exc:
        return jsonify({"error": str(exc), "code": "restart_failed"}), 422


@comfyui_blueprint.route("/api/comfyui/interrupt", methods=["POST"])
def comfyui_interrupt():
    try:
        ok = comfy_manager.interrupt_generation()
        return jsonify({"success": ok})
    except Exception as exc:
        return jsonify({"error": str(exc), "code": "interrupt_failed"}), 422


@comfyui_blueprint.route("/api/comfyui/logs", methods=["GET"])
def comfyui_logs():
    lines_param = request.args.get("lines", "200")
    try:
        lines = int(lines_param)
    except ValueError:
        lines = 200
    return jsonify({"logs": comfy_manager.get_logs(lines)})


@comfyui_blueprint.route("/api/comfyui/launcher", methods=["POST"])
def comfyui_launcher():
    payload = request.get_json(silent=True) or {}
    store = _config_store()
    cfg = store.comfyui_settings()

    install_path = payload.get("install_path") or cfg.get("install_path")
    if not install_path:
        return jsonify({"error": "No installation path specified", "code": "missing_path"}), 400

    detection = detect_comfyui(install_path, custom_python=payload.get("custom_python") or cfg.get("custom_python"))
    if not detection.is_valid:
        return jsonify({"error": detection.error, "code": "invalid_installation"}), 422

    try:
        script_path = generate_launcher_script(
            detection=detection,
            extra_args=payload.get("extra_args") if "extra_args" in payload else cfg.get("extra_args"),
            host=payload.get("host") or cfg.get("host") or "127.0.0.1",
            port=int(payload.get("port") or cfg.get("port") or 8188),
        )
        return jsonify({
            "script_path": str(script_path),
            "script_content": script_path.read_text(encoding="utf-8"),
        })
    except Exception as exc:
        return jsonify({"error": str(exc), "code": "launcher_failed"}), 422
