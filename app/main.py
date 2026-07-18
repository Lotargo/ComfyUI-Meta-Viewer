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
from . import file_actions
from . import library as media_library
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
    AlbumCreateRequest,
    AlbumUpdateRequest,
    ExtractRequest,
    FolderInfo,
    ImageListItem,
    ImagesResponse,
    LibraryAssetIdsRequest,
    LibraryAssetUpdateRequest,
    LibraryBulkRequest,
    OkResponse,
    ScanRequest,
    ScanResponse,
    SourceUpdateRequest,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024
app.config["SEND_FILE_MAX_AGE"] = 3600
app.config.update(build_runtime_paths().flask_config())
app.jinja_env.auto_reload = True


def static_version(filename: str) -> str:
    try:
        static_file = Path(app.static_folder or "") / filename
        stat = static_file.stat()
        return f"{stat.st_mtime_ns:x}-{stat.st_size:x}"
    except OSError:
        return "missing"


app.jinja_env.globals["static_version"] = static_version


def storage_path(config_key: str) -> Path:
    return Path(app.config[config_key])


def clear_image_caches(image_id: int) -> None:
    (storage_path("THUMBNAIL_FOLDER") / f"{image_id}.jpg").unlink(missing_ok=True)
    clear_cutout(storage_path("CUTOUT_FOLDER"), image_id)
    clear_preview_cache(storage_path("PREVIEW_FOLDER"), image_id)


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


@app.errorhandler(media_library.LibraryError)
def library_error(error):
    if isinstance(error, media_library.LibraryNotFoundError):
        status = 404
    elif isinstance(error, media_library.LibraryConflictError):
        status = 409
    else:
        status = 400
    return jsonify({"error": str(error), "code": "library_error"}), status


@app.errorhandler(file_actions.ImageFileActionError)
def image_file_action_error(error):
    return jsonify({"error": str(error), "code": error.code}), error.status_code


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/library")
def library_page():
    return render_template("library.html")


@app.route("/api/library", methods=["GET"])
def api_library_summary():
    result = {
        "system_collections": media_library.SYSTEM_COLLECTIONS,
        "summary": media_library.library_summary(),
        "albums": media_library.list_albums(),
    }
    if request.args.get("include_filters", "1") != "0":
        result["metadata_filters"] = media_library.list_metadata_filters()
    return jsonify(result)


@app.route("/api/library/assets", methods=["GET"])
def api_library_assets():
    # Parse rating parameter if present
    rating_val = request.args.get("rating")
    rating = int(rating_val) if rating_val and rating_val.isdigit() else None

    result = media_library.get_assets(
        collection=request.args.get("collection", "all"),
        album_id=request.args.get("album_id", type=int),
        page=request.args.get("page", 1, type=int),
        per_page=request.args.get("per_page", 80, type=int),
        sort_by=request.args.get("sort_by", "date"),
        sort_dir=request.args.get("sort_dir", "desc"),
        query=request.args.get("q", ""),
        source_id=request.args.get("source_id", type=int),
        tag=request.args.get("tag"),
        rating=rating,
        model_family=request.args.get("model_family"),
        orientation=request.args.get("orientation"),
        node_type=request.args.get("node_type"),
    )
    return jsonify(result)


@app.route("/api/library/assets/<int:asset_id>", methods=["PATCH"])
def api_update_library_asset(asset_id: int):
    try:
        payload = LibraryAssetUpdateRequest.model_validate(
            request.get_json(silent=True) or {}
        )
    except ValidationError as exc:
        return jsonify({"error": exc.errors()[0]["msg"]}), 400
    asset = media_library.update_asset(
        asset_id,
        favorite=payload.favorite,
        rating=payload.rating,
        note=payload.note,
        tags=payload.tags,
        file_name=payload.file_name,
    )
    return jsonify({"asset": asset})


@app.route("/api/library/assets/bulk", methods=["POST"])
def api_library_bulk():
    try:
        payload = LibraryBulkRequest.model_validate(
            request.get_json(silent=True) or {}
        )
    except ValidationError as exc:
        return jsonify({"error": exc.errors()[0]["msg"]}), 400
    result = media_library.bulk_action(
        payload.asset_ids,
        payload.action,
        album_id=payload.album_id,
        rating=payload.rating,
    )
    for image_id in result["removed_ids"]:
        clear_image_caches(image_id)
    return jsonify({"ok": True, **result})


@app.route("/api/library/assets/trash", methods=["POST"])
def api_trash_library_assets():
    try:
        payload = LibraryAssetIdsRequest.model_validate(
            request.get_json(silent=True) or {}
        )
    except ValidationError as exc:
        return jsonify({"error": exc.errors()[0]["msg"]}), 400

    removed_ids: list[int] = []
    failures: list[dict[str, str | int]] = []
    for image_id in dict.fromkeys(payload.asset_ids):
        try:
            file_actions.move_image_file_to_trash(image_id)
        except file_actions.ImageFileActionError as exc:
            failures.append({
                "id": image_id,
                "error": str(exc),
                "code": exc.code,
            })
            continue

        # The source watcher may remove the row before this request reaches it.
        db.delete_image(image_id)
        clear_image_caches(image_id)
        removed_ids.append(image_id)

    return jsonify({
        "ok": not failures,
        "affected": len(removed_ids),
        "removed_ids": removed_ids,
        "failures": failures,
    })


@app.route("/api/albums", methods=["GET", "POST"])
def api_albums():
    if request.method == "GET":
        return jsonify({"albums": media_library.list_albums()})
    try:
        payload = AlbumCreateRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors()[0]["msg"]}), 400
    return jsonify({"album": media_library.create_album(payload.name)}), 201


@app.route("/api/albums/<int:album_id>", methods=["PATCH", "DELETE"])
def api_album(album_id: int):
    if request.method == "DELETE":
        if not media_library.delete_album(album_id):
            raise media_library.LibraryNotFoundError("Album not found")
        return jsonify(OkResponse().model_dump())
    try:
        payload = AlbumUpdateRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors()[0]["msg"]}), 400
    album = media_library.update_album(
        album_id,
        name=payload.name,
        cover_image_id=payload.cover_image_id,
        clear_cover=payload.clear_cover,
    )
    return jsonify({"album": album})


@app.route("/api/albums/<int:album_id>/assets", methods=["POST", "DELETE"])
def api_album_assets(album_id: int):
    body = request.get_json(silent=True) or {}
    asset_ids = body.get("asset_ids")
    if not isinstance(asset_ids, list) or not asset_ids:
        return jsonify({"error": "asset_ids must be a non-empty list"}), 400
    if request.method == "POST":
        affected = media_library.add_assets_to_album(album_id, asset_ids)
    else:
        affected = media_library.remove_assets_from_album(album_id, asset_ids)
    return jsonify({"ok": True, "affected": affected})


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
                        "enabled": f.enabled,
                        "recursive": f.recursive,
                        "source_status": f.source_status,
                        "last_error": f.last_error,
                        "revision": f.revision,
                        "name": f.name,
                    }
                    for f in folders_data
                }
                if state != last_state:
                    yield f"data: {json.dumps(state)}\n\n"
                    last_state = state
                has_processing = any(
                    f.status == "processing"
                    or f.source_status in ("reconnecting", "unavailable")
                    for f in folders_data
                )
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


@app.route("/api/folders/<int:folder_id>", methods=["PATCH"])
def api_update_source(folder_id: int):
    try:
        req = SourceUpdateRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors()[0]["msg"]}), 400
    if req.name is None and req.enabled is None and req.recursive is None:
        return jsonify({"error": "No source settings were provided"}), 400

    record = db.get_folder_record(folder_id)
    if record is None or str(record["path"]).startswith("__uploads"):
        return jsonify({"error": "Source not found"}), 404

    from .source_monitor import get_source_monitor

    monitor = get_source_monitor()
    if monitor is not None and monitor.running:
        updated = monitor.update_source(
            folder_id,
            name=req.name,
            enabled=req.enabled,
            recursive=req.recursive,
        )
        if updated is None:
            return jsonify({"error": "Source not found"}), 404
    else:
        settings = ConfigStore(storage_path("CONFIG_FILE")).update_source(
            record["path"],
            name=req.name,
            enabled=req.enabled,
            recursive=req.recursive,
        )
        if settings is None:
            return jsonify({"error": "Source not found"}), 404
        db.update_source_settings(
            folder_id,
            name=settings.name,
            enabled=settings.enabled,
            recursive=settings.recursive,
        )
        if not settings.enabled:
            db.update_source_state(folder_id, "disabled")
        elif req.enabled is True or req.recursive is not None:
            source_path = Path(settings.path)
            if source_path.is_dir():
                result = index_source_directory(
                    source_path,
                    thumbnail_dir=storage_path("THUMBNAIL_FOLDER"),
                    cutout_dir=storage_path("CUTOUT_FOLDER"),
                    preview_dir=storage_path("PREVIEW_FOLDER"),
                    name=settings.name,
                    recursive=settings.recursive,
                )
                if result.processed:
                    from .worker import start_worker

                    start_worker(storage_path("THUMBNAIL_FOLDER"))
            else:
                db.update_source_state(
                    folder_id,
                    "unavailable",
                    f"Source directory is unavailable: {source_path}",
                )

    current = next((item for item in db.get_folders() if item.id == folder_id), None)
    return jsonify({"folder": current.model_dump() if current else None})


@app.route("/api/folders/<int:folder_id>/reconcile", methods=["POST"])
def api_reconcile_source(folder_id: int):
    record = db.get_folder_record(folder_id)
    if record is None or str(record["path"]).startswith("__uploads"):
        return jsonify({"error": "Source not found"}), 404
    if not bool(record["enabled"]):
        return jsonify({"error": "Enable the source before reconciling it"}), 409

    from .source_monitor import get_source_monitor

    monitor = get_source_monitor()
    if monitor is not None and monitor.running:
        monitor.request_reconcile(folder_id)
    else:
        source_path = normalize_existing_directory(record["path"])
        result = index_source_directory(
            source_path,
            thumbnail_dir=storage_path("THUMBNAIL_FOLDER"),
            cutout_dir=storage_path("CUTOUT_FOLDER"),
            preview_dir=storage_path("PREVIEW_FOLDER"),
            name=record["name"],
            recursive=bool(record["recursive"]),
        )
        if result.processed:
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

    store = ConfigStore(storage_path("CONFIG_FILE"))
    settings = store.add_source(
        folder_path,
        name=req.name,
        recursive=req.recursive,
    )
    result = index_source_directory(
        folder_path,
        thumbnail_dir=storage_path("THUMBNAIL_FOLDER"),
        cutout_dir=storage_path("CUTOUT_FOLDER"),
        preview_dir=storage_path("PREVIEW_FOLDER"),
        name=settings.name,
        recursive=settings.recursive,
    )

    from .source_monitor import get_source_monitor

    monitor = get_source_monitor()
    if monitor is not None and monitor.running:
        monitor.source_added(settings, result.folder_id)

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
    album_id = request.args.get("album_id", type=int)
    if folder_id is not None and album_id is not None:
        return jsonify({"error": "folder_id and album_id cannot be combined"}), 400
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    sort_by = request.args.get("sort_by", "date")
    sort_dir = request.args.get("sort_dir", "desc")
    rating_value = request.args.get("rating")
    try:
        rating = None if rating_value is None else int(rating_value)
    except ValueError:
        return jsonify({"error": "rating must be between 0 and 5"}), 400
    if rating is not None and rating not in range(6):
        return jsonify({"error": "rating must be between 0 and 5"}), 400
    result = db.get_images_page(
        folder_id,
        page,
        per_page,
        sort_by,
        sort_dir,
        album_id=album_id,
        rating=rating,
    )
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

    clear_image_caches(image_id)
    return jsonify(OkResponse().model_dump())


@app.route("/api/images/<int:image_id>/file-location", methods=["GET"])
def api_image_file_location(image_id: int):
    path = file_actions.get_local_image_path(image_id)
    return jsonify({"path": str(path)})


@app.route("/api/images/<int:image_id>/reveal", methods=["POST"])
def api_reveal_image(image_id: int):
    file_actions.reveal_image_file(image_id)
    return jsonify(OkResponse().model_dump())


@app.route("/api/folders/<int:folder_id>", methods=["DELETE"])
def api_delete_folder(folder_id: int):
    folder_path = db.get_folder_path(folder_id)
    image_ids = db.get_folder_image_ids(folder_id)
    from .source_monitor import get_source_monitor

    monitor = get_source_monitor()
    if monitor is not None:
        monitor.forget_source(folder_id)
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

    from .source_monitor import (
        source_monitor_is_running,
        start_source_monitor,
        stop_source_monitor,
    )

    monitor_was_running = source_monitor_is_running()
    monitor_stopped = not monitor_was_running
    app.config["RESET_IN_PROGRESS"] = True
    try:
        if monitor_was_running:
            monitor_stopped = stop_source_monitor(timeout=10.0)
            if not monitor_stopped:
                raise ResetOperationError(["Source monitor did not stop"])
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
        if monitor_was_running and monitor_stopped:
            start_source_monitor(configured_runtime_paths())


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
    store = ConfigStore(runtime_paths.config)
    _migrate_indexed_sources(store)
    from .source_monitor import sync_configured_sources

    sync_configured_sources(store)
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
    store.add_sources(candidates, reactivate=False)


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
    from .source_monitor import start_source_monitor, stop_source_monitor

    start_source_monitor(runtime_paths)

    port = int(os.environ.get("COMFY_META_PORT", "7860"))

    if "--no-browser" not in sys.argv:
        open_browser(port)

    print(f"  ComfyUI Meta Viewer")
    print(f"  http://127.0.0.1:{port}")
    print()

    try:
        app.run(host="127.0.0.1", port=port, debug=False)
    finally:
        stop_source_monitor()
        from .worker import stop_worker

        stop_worker(wait=True)


if __name__ == "__main__":
    main()
