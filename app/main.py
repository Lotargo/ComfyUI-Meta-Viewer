from __future__ import annotations

import json
import os
import sys
import time
import traceback
import webbrowser
import threading
from pathlib import Path

from pydantic import ValidationError
from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_file,
    stream_with_context,
)

from . import database as db
from .cutout import clear_cutout, get_cutout_path, make_cutout_png
from .config_store import ConfigStore, ConfigStoreError
from .extractor import (
    has_generation_metadata,
    make_thumbnail_bytes,
    make_thumbnail_bytes_from_bytes,
    make_thumbnail_b64,
    scan_paths,
    SUPPORTED,
)
from .folder_picker import FolderPickerUnavailable, choose_folder
from .indexing import index_source_directory
from .paths import (
    PathValidationError,
    RuntimePaths,
    build_runtime_paths,
    normalize_existing_directory,
    portable_filename,
)
from .preview import (
    PreviewBusyError,
    clear_preview_cache,
    get_or_create_preview,
    preview_mimetype,
)
from .reset_service import ResetOperationError, reset_application_index
from .schemas import (
    ExtractRequest,
    FolderInfo,
    ImageListItem,
    ImagesResponse,
    OkResponse,
    ScanRequest,
    ScanResponse,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024
app.config["SEND_FILE_MAX_AGE"] = 3600
app.config.update(build_runtime_paths().flask_config())
app.jinja_env.auto_reload = True


def storage_path(config_key: str) -> Path:
    return Path(app.config[config_key])


def configured_runtime_paths() -> RuntimePaths:
    thumbnails = storage_path("THUMBNAIL_FOLDER")
    return RuntimePaths(
        project_root=build_runtime_paths().project_root,
        data_dir=storage_path("UPLOAD_FOLDER"),
        database=Path(db.get_db_path()),
        config=storage_path("CONFIG_FILE"),
        cache_dir=thumbnails.parent,
        thumbnails=thumbnails,
        previews=storage_path("PREVIEW_FOLDER"),
        cutouts=storage_path("CUTOUT_FOLDER"),
    )


@app.after_request
def add_cache_headers(response):
    if request.path.startswith("/static/"):
        if request.path.endswith((".woff2", ".woff", ".ttf", ".eot")):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif request.path.endswith((".css", ".js")):
            response.headers["Cache-Control"] = "public, max-age=0"
        else:
            response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.errorhandler(db.DatabaseMaintenanceError)
def database_maintenance_error(error):
    return jsonify({"error": str(error), "code": "database_maintenance"}), 503


@app.errorhandler(ConfigStoreError)
def config_store_error(error):
    return jsonify({"error": str(error), "code": "configuration_error"}), 500


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/folders", methods=["GET"])
def api_folders():
    folders = db.get_folders()
    return jsonify({"folders": [f.model_dump() for f in folders]})


@app.route("/api/folders/events", methods=["GET"])
def api_folders_events():
    def event_stream():
        last_state = None
        while True:
            try:
                folders_data = db.get_folders()
                state = {
                    str(f.id): {
                        "status": f.status,
                        "processed_count": f.processed_count,
                        "image_count": f.image_count,
                    }
                    for f in folders_data
                }
                if state != last_state:
                    yield f"data: {json.dumps(state)}\n\n"
                    last_state = state
                has_processing = any(f.status == "processing" for f in folders_data)
                sleep_time = 1.0 if has_processing else 5.0
                time.sleep(sleep_time)
            except GeneratorExit:
                break
            except Exception:
                time.sleep(5.0)

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/folders/<int:folder_id>/pause", methods=["POST"])
def api_pause_folder(folder_id: int):
    db.update_folder_status(folder_id, "paused")
    return jsonify(OkResponse().model_dump())


@app.route("/api/folders/<int:folder_id>/resume", methods=["POST"])
def api_resume_folder(folder_id: int):
    db.update_folder_status(folder_id, "processing")
    from .worker import start_worker
    start_worker(storage_path("THUMBNAIL_FOLDER"))
    return jsonify(OkResponse().model_dump())


@app.route("/api/scan", methods=["POST"])
def api_scan():
    try:
        req = ScanRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": e.errors()[0]["msg"]}), 400

    try:
        folder_path = normalize_existing_directory(req.path)
    except PathValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    result = index_source_directory(
        folder_path,
        thumbnail_dir=storage_path("THUMBNAIL_FOLDER"),
        cutout_dir=storage_path("CUTOUT_FOLDER"),
        preview_dir=storage_path("PREVIEW_FOLDER"),
    )
    ConfigStore(storage_path("CONFIG_FILE")).add_source(folder_path)

    from .worker import start_worker
    start_worker(storage_path("THUMBNAIL_FOLDER"))

    first_page = db.get_images_page(result.folder_id, page=1, per_page=50)
    folder_info = db.get_folders()
    current = next((f for f in folder_info if f.id == result.folder_id), None)

    resp = ScanResponse(
        folder_id=result.folder_id,
        folder=current,
        page=1,
        per_page=50,
        total=first_page.total,
        images=first_page.images,
        cached=result.cached,
        processed=result.processed,
    )
    return jsonify(resp.model_dump())


@app.route("/api/images", methods=["GET"])
def api_images():
    folder_id = request.args.get("folder_id", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    sort_by = request.args.get("sort_by", "date")
    sort_dir = request.args.get("sort_dir", "desc")
    result = db.get_images_page(folder_id, page, per_page, sort_by, sort_dir)
    return jsonify(result.model_dump())


@app.route("/api/images/<int:image_id>", methods=["GET"])
def api_image_detail(image_id: int):
    detail = db.get_image_detail(image_id)
    if detail is None:
        return jsonify({"error": "Image not found"}), 404
    return jsonify(detail.model_dump())


@app.route("/api/images/<int:image_id>", methods=["DELETE"])
def api_delete_image(image_id: int):
    ok = db.delete_image(image_id)
    if not ok:
        return jsonify({"error": "Image not found"}), 404

    thumb_dir = storage_path("THUMBNAIL_FOLDER")
    (thumb_dir / f"{image_id}.jpg").unlink(missing_ok=True)
    clear_cutout(storage_path("CUTOUT_FOLDER"), image_id)
    clear_preview_cache(storage_path("PREVIEW_FOLDER"), image_id)
    return jsonify(OkResponse().model_dump())


@app.route("/api/folders/<int:folder_id>", methods=["DELETE"])
def api_delete_folder(folder_id: int):
    folder_path = db.get_folder_path(folder_id)
    image_ids = db.get_folder_image_ids(folder_id)
    db.delete_folder(folder_id)
    if folder_path:
        ConfigStore(storage_path("CONFIG_FILE")).remove_source_for_index_path(
            folder_path
        )
    thumb_dir = storage_path("THUMBNAIL_FOLDER")
    cutout_dir = storage_path("CUTOUT_FOLDER")
    preview_dir = storage_path("PREVIEW_FOLDER")
    for image_id in image_ids:
        (thumb_dir / f"{image_id}.jpg").unlink(missing_ok=True)
        clear_cutout(cutout_dir, image_id)
        clear_preview_cache(preview_dir, image_id)
    return jsonify(OkResponse().model_dump())


def _perform_reset(*, factory_reset: bool):
    expected_confirmation = "factory-reset" if factory_reset else "reset-index"
    payload = request.get_json(silent=True) or {}
    if payload.get("confirm") != expected_confirmation:
        return jsonify({
            "error": f"Confirmation must be '{expected_confirmation}'",
            "code": "confirmation_required",
        }), 400

    app.config["RESET_IN_PROGRESS"] = True
    try:
        result = reset_application_index(
            configured_runtime_paths(),
            factory_reset=factory_reset,
        )
        return jsonify(result.to_dict())
    except ResetOperationError as exc:
        return jsonify({
            "error": str(exc),
            "failures": exc.failures,
            "code": "reset_failed",
        }), 500
    except Exception as exc:
        return jsonify({"error": str(exc), "code": "reset_failed"}), 500
    finally:
        app.config["RESET_IN_PROGRESS"] = False
        from .worker import start_worker
        start_worker(storage_path("THUMBNAIL_FOLDER"))


@app.route("/api/reset", methods=["POST"])
@app.route("/api/reset-index", methods=["POST"])
def api_reset_index():
    return _perform_reset(factory_reset=False)


@app.route("/api/factory-reset", methods=["POST"])
def api_factory_reset():
    return _perform_reset(factory_reset=True)


@app.route("/api/diagnostics", methods=["GET"])
def api_diagnostics():
    thumb_dir = storage_path("THUMBNAIL_FOLDER")
    cutout_dir = storage_path("CUTOUT_FOLDER")
    preview_dir = storage_path("PREVIEW_FOLDER")
    thumb_count = 0
    if thumb_dir.exists() and thumb_dir.is_dir():
        thumb_count = sum(1 for f in thumb_dir.iterdir() if f.is_file())
    cutout_count = 0
    if cutout_dir.exists() and cutout_dir.is_dir():
        cutout_count = sum(1 for f in cutout_dir.iterdir() if f.is_file())
    preview_count = 0
    if preview_dir.exists() and preview_dir.is_dir():
        preview_count = sum(1 for f in preview_dir.iterdir() if f.is_file())

    diagnostics = db.get_diagnostics()
    diagnostics.update({
        "thumbnail_dir": str(thumb_dir),
        "thumbnail_count": thumb_count,
        "cutout_dir": str(cutout_dir),
        "cutout_count": cutout_count,
        "preview_dir": str(preview_dir),
        "preview_count": preview_count,
        "upload_dir": str(storage_path("UPLOAD_FOLDER")),
    })
    return jsonify(diagnostics)


@app.route("/api/cutout/<int:image_id>", methods=["GET"])
def api_get_cutout(image_id: int):
    cutout_path = get_cutout_path(storage_path("CUTOUT_FOLDER"), image_id)
    if not cutout_path.exists():
        return jsonify({"error": "Cutout not found"}), 404
    return Response(cutout_path.read_bytes(), mimetype="image/png")


@app.route("/api/cutout/<int:image_id>", methods=["POST"])
def api_create_cutout(image_id: int):
    try:
        _, cached = make_cutout_png(
            image_id,
            storage_path("CUTOUT_FOLDER"),
        )
    except FileNotFoundError:
        return jsonify({"error": "Image source not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "ok": True,
        "image_id": image_id,
        "cutout_url": f"/api/cutout/{image_id}",
        "cached": cached,
    })


@app.route("/api/cutout/<int:image_id>", methods=["DELETE"])
def api_delete_cutout(image_id: int):
    deleted = clear_cutout(storage_path("CUTOUT_FOLDER"), image_id)
    return jsonify({"ok": True, "deleted": deleted})


@app.route("/api/thumbnail/<int:image_id>")

def api_thumbnail(image_id: int):
    thumb_dir = storage_path("THUMBNAIL_FOLDER")
    thumb_path = thumb_dir / f"{image_id}.jpg"

    if thumb_path.exists():
        return Response(thumb_path.read_bytes(), mimetype="image/jpeg")

    original = db.get_image_original_data(image_id)
    if original:
        thumb_data = make_thumbnail_bytes_from_bytes(original)
        if thumb_data:
            thumb_dir.mkdir(parents=True, exist_ok=True)
            thumb_path.write_bytes(thumb_data)
            return Response(thumb_data, mimetype="image/jpeg")
        return jsonify({"error": "failed"}), 500

    img_path = db.get_image_path(image_id)
    if not img_path:
        return jsonify({"error": "not found"}), 404
    
    db.ensure_image_processed(image_id, img_path)

    thumb_data = make_thumbnail_bytes(img_path)
    if not thumb_data:
        return jsonify({"error": "failed"}), 500
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path.write_bytes(thumb_data)
    return Response(thumb_data, mimetype="image/jpeg")


@app.route("/api/preview/<int:image_id>")
def api_preview(image_id: int):
    try:
        preview_path = get_or_create_preview(
            image_id,
            storage_path("PREVIEW_FOLDER"),
        )
    except PreviewBusyError:
        response = jsonify({"status": "busy"})
        response.status_code = 202
        response.headers["Retry-After"] = "1"
        return response
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    response = send_file(
        preview_path,
        mimetype=preview_mimetype(preview_path),
        conditional=True,
        max_age=0,
    )
    response.headers["Cache-Control"] = "private, no-cache"
    return response


MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


@app.route("/api/original/<int:image_id>")
def api_original(image_id: int):
    source = db.get_image_source_info(image_id)
    if not source:
        return jsonify({"error": "not found"}), 404

    fmt = source.get("format")
    suffix = Path(source["file_name"]).suffix.lower()
    mime = MIME_MAP.get(
        f".{fmt}".lower() if fmt else suffix,
        "application/octet-stream",
    )

    if source["has_original_data"]:
        response = Response(
            stream_with_context(db.iter_image_original_data(image_id)),
            mimetype=mime,
            direct_passthrough=True,
        )
        response.content_length = int(source.get("file_size") or 0) or None
        response.headers["Cache-Control"] = "private, no-cache"
        response.headers["Content-Disposition"] = "inline"
        return response

    p = Path(source["path"])
    if not p.is_file():
        return jsonify({"error": "file not found"}), 404
    return send_file(
        p.resolve(),
        mimetype=mime,
        conditional=True,
        as_attachment=False,
        download_name=source["file_name"],
        max_age=0,
    )


@app.route("/api/extract", methods=["POST"])
def api_extract():
    try:
        req = ExtractRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": e.errors()[0]["msg"]}), 400

    results = scan_paths(req.paths)
    image_dicts = []
    for item in results:
        d = item.model_dump()
        if not d.get("error") and d.get("path") and Path(d["path"]).is_file():
            d["thumbnail"] = make_thumbnail_b64(d["path"])
        image_dicts.append(d)

    return jsonify({"images": image_dicts, "count": len(image_dicts)})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "files" not in request.files:
        return jsonify({"error": "No files"}), 400
    files = request.files.getlist("files")
    results: list[dict] = []
    folder_id: int | None = None
    for f in files:
        if not f.filename:
            continue
        safe_name = portable_filename(f.filename)
        suffix = Path(safe_name).suffix.lower()
        if suffix not in SUPPORTED:
            continue
        try:
            original_data = f.read()
            img_id, fid = db.insert_upload_image(
                file_name=safe_name,
                original_data=original_data,
                has_metadata=has_generation_metadata(original_data, safe_name),
            )
            folder_id = fid
            results.append({
                "id": img_id,
                "folder_id": fid,
                "file_name": safe_name,
                "file_size": len(original_data),
            })
        except Exception as e:
            tb = traceback.format_exc()
            results.append({"file": f.filename, "error": f"{e}\n{tb}"})
    resp = {"images": results, "count": len(results)}
    if folder_id is not None:
        resp["folder_id"] = folder_id
    return jsonify(resp)


@app.route("/api/choose-folder", methods=["POST"])
def api_choose_folder():
    try:
        folder_path = choose_folder()
        if folder_path:
            return jsonify({"path": str(folder_path)})
        return jsonify({"path": None})
    except (FolderPickerUnavailable, PathValidationError) as exc:
        return jsonify({
            "error": str(exc),
            "code": "folder_picker_unavailable",
            "fallback": "Enter the folder path manually",
        }), 503


def open_browser(port: int):
    threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()


def configure_runtime(paths: RuntimePaths | None = None) -> RuntimePaths:
    runtime_paths = paths or build_runtime_paths()
    runtime_paths.ensure_directories()
    app.config.update(runtime_paths.flask_config())
    db.set_db_path(runtime_paths.database)
    db.init_db()
    _migrate_indexed_sources(ConfigStore(runtime_paths.config))
    return runtime_paths


def _migrate_indexed_sources(store: ConfigStore) -> None:
    candidates: list[Path] = []
    for stored_path in db.get_indexed_folder_paths():
        if stored_path.startswith("__uploads"):
            continue
        candidate = Path(stored_path)
        if candidate.is_dir():
            candidates.append(candidate)
            continue
        suffix = " (no metadata)"
        if stored_path.endswith(suffix):
            source = Path(stored_path.removesuffix(suffix))
            if source.is_dir():
                candidates.append(source)
    store.add_sources(candidates)


def _run_reset_command(paths: RuntimePaths, *, factory_reset: bool) -> None:
    paths.ensure_directories()
    app.config.update(paths.flask_config())
    db.set_db_path(paths.database)
    try:
        result = reset_application_index(paths, factory_reset=factory_reset)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(result.to_dict(), ensure_ascii=True, indent=2))


def main():
    reset_index_requested = "--reset-index" in sys.argv
    factory_reset_requested = "--factory-reset" in sys.argv
    if reset_index_requested and factory_reset_requested:
        raise SystemExit("Choose only one reset command")

    runtime_paths = build_runtime_paths()
    if reset_index_requested or factory_reset_requested:
        _run_reset_command(
            runtime_paths,
            factory_reset=factory_reset_requested,
        )
        return

    configure_runtime(runtime_paths)

    # Start queue background worker
    from .worker import start_worker
    start_worker(storage_path("THUMBNAIL_FOLDER"))

    port = int(os.environ.get("COMFY_META_PORT", "7860"))

    if "--no-browser" not in sys.argv:
        open_browser(port)

    print(f"  ComfyUI Meta Viewer")
    print(f"  http://127.0.0.1:{port}")
    print()

    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
