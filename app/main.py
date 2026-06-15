from __future__ import annotations

import base64
import io
import os
import sys
import webbrowser
import threading
import traceback
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .extractor import extract_metadata, scan_paths, SUPPORTED

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


def _make_thumbnail_b64(path: str | Path, max_size: int = 256) -> str | None:
    try:
        from PIL import Image
        img = Image.open(str(path))
        img.thumbnail((max_size, max_size))
        buf = io.BytesIO()
        fmt = "JPEG" if img.mode == "RGB" else "PNG"
        if img.mode in ("RGBA", "P", "LA"):
            fmt = "PNG"
        if img.mode not in ("RGB", "RGBA", "L", "P", "LA"):
            img = img.convert("RGB")
            fmt = "JPEG"
        img.save(buf, format=fmt, quality=80)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        mime = "jpeg" if fmt == "JPEG" else "png"
        return f"data:image/{mime};base64,{b64}"
    except Exception:
        return None


def _attach_thumbnails(results: list[dict]) -> list[dict]:
    for item in results:
        if "error" in item:
            continue
        path = item.get("path", "")
        if path and Path(path).is_file():
            item["thumbnail"] = _make_thumbnail_b64(path)
    return results


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/extract", methods=["POST"])
def api_extract():
    data = request.get_json(silent=True) or {}
    paths = data.get("paths", [])
    if not paths:
        return jsonify({"error": "No paths provided"}), 400
    results = scan_paths(paths)
    _attach_thumbnails(results)
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
            meta["thumbnail"] = _make_thumbnail_b64(tmp)
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

    port = int(os.environ.get("COMFY_META_PORT", "7860"))

    if "--no-browser" not in sys.argv:
        open_browser(port)

    print(f"  ComfyUI Meta Viewer")
    print(f"  http://127.0.0.1:{port}")
    print()

    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
