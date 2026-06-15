from __future__ import annotations

import json
import os
import sys
import traceback
import webbrowser
import threading
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

from . import database as db
from .extractor import (
    extract_metadata,
    make_thumbnail_bytes,
    make_thumbnail_b64,
    scan_directory,
    scan_paths,
    SUPPORTED,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/folders", methods=["GET"])
def api_folders():
    folders = db.get_folders()
    return jsonify({"folders": folders})


@app.route("/api/scan", methods=["POST"])
def api_scan():
    data = request.get_json(silent=True) or {}
    path_str = data.get("path", "").strip()
    if not path_str:
        return jsonify({"error": "No path provided"}), 400

    folder_path = Path(path_str)
    if not folder_path.is_dir():
        return jsonify({"error": f"Not a directory: {path_str}"}), 400

    folder_id = db.upsert_folder(path_str)

    old_mtimes = db.get_folder_mtimes(folder_id)

    files = sorted(
        f
        for f in folder_path.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED
    )

    to_process = []
    cached_count = 0
    for f in files:
        rel_path = f.name
        mtime = f.stat().st_mtime
        if rel_path in old_mtimes and abs(old_mtimes[rel_path] - mtime) < 0.001:
            cached_count += 1
        else:
            to_process.append((rel_path, f))

    if to_process:
        new_images = []
        for rel_path, f in to_process:
            try:
                meta = extract_metadata(f)
                stat = f.stat()
                new_images.append(
                    {
                        "rel_path": rel_path,
                        "file_name": f.name,
                        "file_size": stat.st_size,
                        "file_mtime": stat.st_mtime,
                        "format": meta.get("format"),
                        "width": meta.get("size", [0, 0])[0],
                        "height": meta.get("size", [0, 0])[1],
                        "mode": meta.get("mode"),
                        "error": meta.get("error"),
                        "metadata_json": json.dumps(meta, default=str),
                    }
                )
            except Exception as e:
                stat = f.stat()
                new_images.append(
                    {
                        "rel_path": rel_path,
                        "file_name": f.name,
                        "file_size": stat.st_size,
                        "file_mtime": stat.st_mtime,
                        "error": str(e) + "\n" + traceback.format_exc(),
                    }
                )

        db.insert_images(folder_id, new_images)

    first_page = db.get_images_page(folder_id, page=1, per_page=50)
    folder_info = db.get_folders()
    current = next((f for f in folder_info if f["id"] == folder_id), None)

    return jsonify(
        {
            "folder_id": folder_id,
            "folder": current,
            "page": 1,
            "per_page": 50,
            "total": first_page["total"],
            "images": first_page["images"],
            "cached": cached_count,
            "processed": len(to_process),
        }
    )


@app.route("/api/images", methods=["GET"])
def api_images():
    folder_id = request.args.get("folder_id", type=int)
    if not folder_id:
        return jsonify({"error": "folder_id required"}), 400
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    result = db.get_images_page(folder_id, page, per_page)
    return jsonify(result)


@app.route("/api/images/<int:image_id>", methods=["GET"])
def api_image_detail(image_id: int):
    detail = db.get_image_detail(image_id)
    if detail is None:
        return jsonify({"error": "Image not found"}), 404
    return jsonify(detail)


@app.route("/api/folders/<int:folder_id>", methods=["DELETE"])
def api_delete_folder(folder_id: int):
    db.delete_folder(folder_id)
    return jsonify({"ok": True})


@app.route("/api/thumbnail/<int:image_id>")
def api_thumbnail(image_id: int):
    thumb_dir = Path(app.config.get("THUMBNAIL_FOLDER", "cache/thumbnails"))
    thumb_path = thumb_dir / f"{image_id}.jpg"

    if thumb_path.exists():
        return Response(thumb_path.read_bytes(), mimetype="image/jpeg")

    img_path = db.get_image_path(image_id)
    if not img_path:
        return jsonify({"error": "not found"}), 404
    thumb_data = make_thumbnail_bytes(img_path)
    if not thumb_data:
        return jsonify({"error": "failed"}), 500
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path.write_bytes(thumb_data)
    return Response(thumb_data, mimetype="image/jpeg")


@app.route("/api/extract", methods=["POST"])
def api_extract():
    data = request.get_json(silent=True) or {}
    paths = data.get("paths", [])
    if not paths:
        return jsonify({"error": "No paths provided"}), 400
    results = scan_paths(paths)
    for item in results:
        if "error" in item:
            continue
        path = item.get("path", "")
        if path and Path(path).is_file():
            item["thumbnail"] = make_thumbnail_b64(path)
    return jsonify({"images": results, "count": len(results)})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "files" not in request.files:
        return jsonify({"error": "No files"}), 400
    files = request.files.getlist("files")
    upload_dir = Path(app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for f in files:
        if not f.filename:
            continue
        suffix = Path(f.filename).suffix.lower()
        if suffix not in SUPPORTED:
            continue
        safe_name = f.filename
        tmp = upload_dir / safe_name
        counter = 0
        while tmp.exists():
            counter += 1
            stem = Path(safe_name).stem
            ext = Path(safe_name).suffix
            tmp = upload_dir / f"{stem}_{counter}{ext}"
        try:
            f.save(str(tmp))
            meta = extract_metadata(tmp)
            meta["thumbnail"] = make_thumbnail_b64(tmp)
            results.append(meta)
        except Exception as e:
            tb = traceback.format_exc()
            results.append({"file": f.filename, "error": f"{e}\n{tb}"})
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
    return jsonify({"images": results, "count": len(results)})


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
