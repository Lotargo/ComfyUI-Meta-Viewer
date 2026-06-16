from __future__ import annotations

import json
import os
import sys
import traceback
import webbrowser
import threading
from pathlib import Path

from pydantic import ValidationError
from flask import Flask, Response, jsonify, render_template, request

from . import database as db
from .extractor import (
    extract_metadata,
    make_thumbnail_bytes,
    make_thumbnail_bytes_from_bytes,
    make_thumbnail_b64,
    scan_paths,
    SUPPORTED,
)
from .schemas import (
    ExtractRequest,
    FolderInfo,
    ImageInsertRow,
    ImageListItem,
    ImageMetadata,
    ImagesResponse,
    OkResponse,
    ScanRequest,
    ScanResponse,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/folders", methods=["GET"])
def api_folders():
    folders = db.get_folders()
    return jsonify({"folders": [f.model_dump() for f in folders]})


@app.route("/api/scan", methods=["POST"])
def api_scan():
    try:
        req = ScanRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": e.errors()[0]["msg"]}), 400

    folder_path = Path(req.path)
    if not folder_path.is_dir():
        return jsonify({"error": f"Not a directory: {req.path}"}), 400

    folder_id = db.upsert_folder(req.path)
    old_mtimes = db.get_folder_mtimes(folder_id)

    files = sorted(
        f
        for f in folder_path.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED
    )

    to_process: list[tuple[str, Path]] = []
    cached_count = 0
    for f in files:
        rel_path = f.name
        mtime = f.stat().st_mtime
        if rel_path in old_mtimes and abs(old_mtimes[rel_path] - mtime) < 0.001:
            cached_count += 1
        else:
            to_process.append((rel_path, f))

    if to_process:
        new_images: list[ImageInsertRow] = []
        for rel_path, f in to_process:
            try:
                meta = extract_metadata(f)
                stat = f.stat()
                new_images.append(ImageInsertRow(
                    rel_path=rel_path,
                    file_name=f.name,
                    file_size=stat.st_size,
                    file_mtime=stat.st_mtime,
                    format=meta.format,
                    width=meta.size[0] if meta.size else 0,
                    height=meta.size[1] if meta.size else 0,
                    mode=meta.mode,
                    error=meta.error,
                    metadata_json=meta.model_dump_json(),
                ))
            except Exception as e:
                stat = f.stat()
                new_images.append(ImageInsertRow(
                    rel_path=rel_path,
                    file_name=f.name,
                    file_size=stat.st_size,
                    file_mtime=stat.st_mtime,
                    error=str(e) + "\n" + traceback.format_exc(),
                ))

        db.insert_images(folder_id, new_images)

    first_page = db.get_images_page(folder_id, page=1, per_page=50)
    folder_info = db.get_folders()
    current = next((f for f in folder_info if f.id == folder_id), None)

    resp = ScanResponse(
        folder_id=folder_id,
        folder=current,
        page=1,
        per_page=50,
        total=first_page.total,
        images=first_page.images,
        cached=cached_count,
        processed=len(to_process),
    )
    return jsonify(resp.model_dump())


@app.route("/api/images", methods=["GET"])
def api_images():
    folder_id = request.args.get("folder_id", type=int)
    if not folder_id:
        return jsonify({"error": "folder_id required"}), 400
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    result = db.get_images_page(folder_id, page, per_page)
    return jsonify(result.model_dump())


@app.route("/api/images/<int:image_id>", methods=["GET"])
def api_image_detail(image_id: int):
    detail = db.get_image_detail(image_id)
    if detail is None:
        return jsonify({"error": "Image not found"}), 404
    return jsonify(detail.model_dump())


@app.route("/api/folders/<int:folder_id>", methods=["DELETE"])
def api_delete_folder(folder_id: int):
    db.delete_folder(folder_id)
    return jsonify(OkResponse().model_dump())


@app.route("/api/thumbnail/<int:image_id>")
def api_thumbnail(image_id: int):
    thumb_dir = Path(app.config.get("THUMBNAIL_FOLDER", "cache/thumbnails"))
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
    thumb_data = make_thumbnail_bytes(img_path)
    if not thumb_data:
        return jsonify({"error": "failed"}), 500
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path.write_bytes(thumb_data)
    return Response(thumb_data, mimetype="image/jpeg")


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
    original = db.get_image_original_data(image_id)
    if original:
        fmt = db.get_image_format(image_id)
        mime = MIME_MAP.get(f".{fmt}" if fmt else "", "application/octet-stream")
        return Response(original, mimetype=mime)

    img_path = db.get_image_path(image_id)
    if not img_path:
        return jsonify({"error": "not found"}), 404
    p = Path(img_path)
    if not p.is_file():
        return jsonify({"error": "file not found"}), 404
    mime = MIME_MAP.get(p.suffix.lower(), "application/octet-stream")
    return Response(p.read_bytes(), mimetype=mime)


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
        suffix = Path(f.filename).suffix.lower()
        if suffix not in SUPPORTED:
            continue
        try:
            original_data = f.read()
            upload_dir = Path(app.config["UPLOAD_FOLDER"])
            upload_dir.mkdir(parents=True, exist_ok=True)
            safe_name = f.filename
            tmp = upload_dir / safe_name
            counter = 0
            while tmp.exists():
                counter += 1
                stem = Path(safe_name).stem
                ext = Path(safe_name).suffix
                tmp = upload_dir / f"{stem}_{counter}{ext}"
            tmp.write_bytes(original_data)
            meta = extract_metadata(tmp)
            thumbnail = make_thumbnail_b64(tmp)
            tmp.unlink(missing_ok=True)
            img_id, fid = db.insert_upload_image(
                file_name=f.filename,
                original_data=original_data,
                metadata=meta,
                thumbnail_b64=thumbnail,
            )
            folder_id = fid
            result = meta.model_dump()
            result["id"] = img_id
            result["folder_id"] = fid
            result["thumbnail"] = thumbnail
            results.append(result)
        except Exception as e:
            tb = traceback.format_exc()
            results.append({"file": f.filename, "error": f"{e}\n{tb}"})
    resp = {"images": results, "count": len(results)}
    if folder_id is not None:
        resp["folder_id"] = folder_id
    return jsonify(resp)


def open_browser(port: int):
    threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()


def main():
    upload_dir = Path(os.environ.get("COMFY_META_UPLOAD", ".comfy_meta_uploads"))
    upload_dir.mkdir(exist_ok=True)
    app.config["UPLOAD_FOLDER"] = str(upload_dir)

    db_path = upload_dir / "meta.db"
    db.set_db_path(db_path)
    db.init_db()

    port = int(os.environ.get("COMFY_META_PORT", "7860"))

    if "--no-browser" not in sys.argv:
        open_browser(port)

    print(f"  ComfyUI Meta Viewer")
    print(f"  http://127.0.0.1:{port}")
    print()

    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
