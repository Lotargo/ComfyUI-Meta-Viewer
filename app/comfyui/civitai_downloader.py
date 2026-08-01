from __future__ import annotations

import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from app import database
from app.config_store import ConfigStore

from .detector import detect_comfyui
from .resource_taxonomy import FOLDER_RESOURCE_TYPES
from .workflow_inventory import invalidate_runtime_inventory

API_BASE = "https://civitai.com/api/v1"
USER_AGENT = "ComfyUI-Meta-Viewer/1.0"
TIMEOUT_SECONDS = 30

# Civitai model types -> local ComfyUI model folder.
CIVITAI_FOLDER_MAP: dict[str, str] = {
    "Checkpoint": "checkpoints",
    "LORA": "loras",
    "LoCon": "loras",
    "DOra": "loras",
    "TextualInversion": "embeddings",
    "VAE": "vae",
    "ControlNet": "controlnet",
    "Upscaler": "upscale_models",
    "CLIP": "text_encoders",
}

CIVITAI_FILTER_TYPES = ("Checkpoint", "LORA", "LoCon", "DOra", "TextualInversion", "VAE", "ControlNet", "Upscaler", "CLIP")
MODEL_FILE_SUFFIXES = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".onnx", ".patch", ".txt"}

DOWNLOAD_STATUSES = ("queued", "downloading", "completed", "failed", "cancelled")

CHUNK_SIZE = 1024 * 1024
PROGRESS_INTERVAL_SECONDS = 0.25


class CivitaiDownloaderError(RuntimeError):
    """Raised when Civitai requests or download targets are invalid."""


def _get_json(url: str, *, token: str = "") -> dict[str, Any]:
    request = urllib.request.Request(url, headers=_request_headers(token))
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            data = json_loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise CivitaiDownloaderError("Civitai not found this model or page.") from exc
        if exc.code == 429:
            raise CivitaiDownloaderError("Civitai rate limit reached. Try again later.") from exc
        raise CivitaiDownloaderError(f"Civitai returned HTTP {exc.code}. Try again later.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CivitaiDownloaderError(
            "Could not reach Civitai. Check your internet connection and retry."
        ) from exc
    if not isinstance(data, dict):
        raise CivitaiDownloaderError("Civitai returned an invalid response.")
    return data


def _request_headers(token: str = "") -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    if str(token).strip():
        headers["Authorization"] = f"Bearer {str(token).strip()}"
    return headers


def _api_token(store: ConfigStore | None) -> str:
    if store is not None:
        token = str((store.comfyui_settings() or {}).get("civitai_api_token") or "")
        if token.strip():
            return token.strip()
    return _civitai_cli_token()


def _civitai_cli_config_path() -> Path | None:
    try:
        if os.name == "nt":
            base = os.environ.get("APPDATA")
            if not base:
                return None
            return Path(base) / "civitai" / "config.yaml"
        base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
        return Path(base) / "civitai" / "config.yaml"
    except (OSError, RuntimeError):
        return None


def _parse_flat_yaml(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return values
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            values[key] = value
    return values


def _civitai_cli_token() -> str:
    env_token = os.environ.get("CIVITAI_TOKEN") or os.environ.get("CIVITAI_API_TOKEN")
    if env_token and str(env_token).strip():
        return str(env_token).strip()
    path = _civitai_cli_config_path()
    if path is None or not path.is_file():
        return ""
    values = _parse_flat_yaml(path)
    token = values.get("token") or values.get("access_token")
    return str(token or "").strip()


def json_loads(raw: str) -> Any:
    import json

    return json.loads(raw)


class CivitaiDownloaderService:
    """Search Civitai, inspect model versions and queue background downloads."""

    def __init__(self, store: ConfigStore):
        self.store = store

    # ------------------------------------------------------------------ search

    def search(
        self,
        *,
        query: str = "",
        types: str = "",
        page: int = 1,
        limit: int = 20,
        sort: str = "Most Downloaded",
        nsfw: bool = True,
        cursor: str = "",
    ) -> dict[str, Any]:
        clean_query = str(query).strip()
        params: dict[str, str] = {
            "limit": str(max(1, min(int(limit), 100))),
            "nsfw": "true" if nsfw else "false",
        }
        if clean_query:
            params["query"] = clean_query
        else:
            params["page"] = str(max(1, int(page)))
        if str(cursor).strip():
            params["cursor"] = str(cursor).strip()
        requested_types = _validate_types(types)
        if requested_types:
            params["types"] = requested_types
        if str(sort).strip():
            params["sort"] = str(sort).strip()
        url = f"{API_BASE}/models?{urllib.parse.urlencode(params)}"
        data = _get_json(url, token=_api_token(self.store))

        items = data.get("items") if isinstance(data.get("items"), list) else []
        results = [self._search_item(item) for item in items if isinstance(item, dict)]
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        return {
            "items": results,
            "total_items": int(metadata.get("totalItems") or 0),
            "current_page": int(metadata.get("currentPage") or 1),
            "total_pages": int(metadata.get("totalPages") or 1),
            "next_page": metadata.get("nextPage"),
            "next_cursor": metadata.get("nextCursor"),
            "using_cursor": bool(metadata.get("nextCursor") or metadata.get("nextPage")),
        }

    def _search_item(self, item: dict[str, Any]) -> dict[str, Any]:
        versions = item.get("modelVersions") if isinstance(item.get("modelVersions"), list) else []
        first = versions[0] if versions and isinstance(versions[0], dict) else {}
        files = first.get("files") if isinstance(first.get("files"), list) else []
        primary = _primary_file(files)
        stats = item.get("stats") if isinstance(item.get("stats"), dict) else {}
        return {
            "id": int(item.get("id") or 0),
            "name": str(item.get("name") or ""),
            "description": _clean_description(item.get("description")),
            "type": str(item.get("type") or ""),
            "nsfw": bool(item.get("nsfw")),
            "tags": [str(tag) for tag in (item.get("tags") or []) if isinstance(tag, str)][:12],
            "creator": str((item.get("creator") or {}).get("username") or ""),
            "stats": {
                "download_count": int(stats.get("downloadCount") or 0),
                "rating": round(float(stats.get("rating") or 0), 2),
                "rating_count": int(stats.get("ratingCount") or 0),
            },
            "images": [p for p in (_preview_image(image) for image in _first_version_images(item)) if p][:4],
            "version_id": int(first.get("id") or 0) if first else None,
            "version_name": str(first.get("name") or ""),
            "file_name": str(primary.get("name") or "") if primary else "",
            "file_size_bytes": _size_kb_to_bytes(primary.get("sizeKB")) if primary else 0,
        }

    # ---------------------------------------------------------------- details

    def details(self, model_id: int) -> dict[str, Any]:
        data = _get_json(f"{API_BASE}/models/{int(model_id)}", token=_api_token(self.store))
        versions = []
        for version in data.get("modelVersions") or []:
            if not isinstance(version, dict):
                continue
            files = version.get("files") if isinstance(version.get("files"), list) else []
            versions.append({
                "id": int(version.get("id") or 0),
                "name": str(version.get("name") or ""),
                "base_model": str(version.get("baseModel") or ""),
                "trained_words": [str(word) for word in (version.get("trainedWords") or []) if isinstance(word, str)],
                "files": [
                    {
                        "name": str(file.get("name") or ""),
                        "size_bytes": _size_kb_to_bytes(file.get("sizeKB")),
                        "type": str(file.get("type") or ""),
                        "format": str((file.get("metadata") or {}).get("format") or ""),
                        "primary": bool(file.get("primary")),
                    }
                    for file in files
                    if isinstance(file, dict)
                ],
            })
        stats = data.get("stats") if isinstance(data.get("stats"), dict) else {}
        return {
            "id": int(data.get("id") or 0),
            "name": str(data.get("name") or ""),
            "description": _clean_description(data.get("description")),
            "type": str(data.get("type") or ""),
            "nsfw": bool(data.get("nsfw")),
            "tags": [str(tag) for tag in (data.get("tags") or []) if isinstance(tag, str)][:12],
            "creator": str((data.get("creator") or {}).get("username") or ""),
            "stats": {
                "download_count": int(stats.get("downloadCount") or 0),
                "rating": round(float(stats.get("rating") or 0), 2),
                "rating_count": int(stats.get("ratingCount") or 0),
            },
            "images": [p for p in (_preview_image(image) for image in _all_version_images(data)) if p][:8],
            "versions": versions,
        }

    # --------------------------------------------------------------- download

    def available_folders(self) -> list[str]:
        return sorted(FOLDER_RESOURCE_TYPES)

    def folder_for_type(self, model_type: str) -> str | None:
        return CIVITAI_FOLDER_MAP.get(str(model_type or ""))

    def start_download(
        self,
        *,
        model_id: int,
        model_name: str,
        version_id: int,
        version_name: str,
        folder: str,
        filename: str,
        file_type: str = "",
        file_size_bytes: int = 0,
    ) -> dict[str, Any]:
        filename = _sanitize_filename(filename)
        self._validate_target(folder, filename)
        source_url = _download_url(version_id, filename, file_type)
        conn = database.get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO model_downloads
                    (civitai_model_id, civitai_model_name, civitai_version_id,
                     version_name, folder, filename, file_size_bytes, source_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (int(model_id), str(model_name), int(version_id), str(version_name),
                 folder, filename, int(file_size_bytes), source_url),
            )
            conn.commit()
            download_id = int(cursor.lastrowid)
        finally:
            conn.close()
        start_download_worker(self.store)
        return self._row_payload(self._get_download(download_id))

    def list_downloads(self) -> list[dict[str, Any]]:
        conn = database.get_conn()
        try:
            rows = conn.execute(
                """SELECT * FROM model_downloads ORDER BY id DESC LIMIT 100"""
            ).fetchall()
        finally:
            conn.close()
        return [self._row_payload(dict(row)) for row in rows]

    def cancel_download(self, download_id: int) -> bool:
        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT status FROM model_downloads WHERE id=?", (int(download_id),)
            ).fetchone()
            if row is None or row["status"] not in ("queued", "downloading"):
                return False
            conn.execute(
                "UPDATE model_downloads SET status='cancelled', updated_at=datetime('now') WHERE id=?",
                (int(download_id),),
            )
            conn.commit()
        finally:
            conn.close()
        return True

    def delete_download(self, download_id: int) -> bool:
        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT folder, filename, status FROM model_downloads WHERE id=?", (int(download_id),)
            ).fetchone()
            if row is None:
                return False
            if row["status"] in ("queued", "downloading"):
                conn.execute(
                    "UPDATE model_downloads SET status='cancelled', updated_at=datetime('now') WHERE id=?",
                    (int(download_id),),
                )
                conn.commit()
                return True
            conn.execute("DELETE FROM model_downloads WHERE id=?", (int(download_id),))
            conn.commit()
        finally:
            conn.close()
        if row["status"] not in ("queued", "downloading"):
            self._remove_partial_files(row["folder"], row["filename"])
        return True

    # ------------------------------------------------------------------ target

    def _validate_target(self, folder: str, filename: str) -> None:
        folder = str(folder or "").strip()
        if folder not in FOLDER_RESOURCE_TYPES:
            raise CivitaiDownloaderError("Unknown model folder. Choose a valid target folder.")
        filename = _sanitize_filename(filename)
        if not filename:
            raise CivitaiDownloaderError("Provide a valid file name for the download.")
        if not Path(filename).suffix.casefold() in MODEL_FILE_SUFFIXES:
            raise CivitaiDownloaderError(
                "Unsupported model file extension. Use .safetensors, .ckpt, .gguf or similar."
            )

    def resolve_model_root(self) -> Path:
        config = self.store.comfyui_settings()
        detection = detect_comfyui(
            str(config.get("install_path") or ""),
            custom_python=config.get("custom_python"),
        )
        if detection.comfy_dir is None:
            raise CivitaiDownloaderError(
                "ComfyUI installation path is not configured or invalid. "
                "Set it in the runtime settings first."
            )
        model_root = (Path(detection.comfy_dir) / "models").resolve()
        if not model_root.is_dir():
            model_root.mkdir(parents=True, exist_ok=True)
        return model_root

    def _resolve_target(self, folder: str, filename: str) -> tuple[Path, Path]:
        model_root = self.resolve_model_root()
        directory = (model_root / folder).resolve()
        try:
            directory.relative_to(model_root)
        except ValueError as exc:
            raise CivitaiDownloaderError("Invalid model folder.") from exc
        directory.mkdir(parents=True, exist_ok=True)
        target = (directory / filename).resolve()
        try:
            target.relative_to(directory)
        except ValueError as exc:
            raise CivitaiDownloaderError("Invalid model file name.") from exc
        return target, target.with_name(target.name + ".part")

    def _get_download(self, download_id: int) -> dict[str, Any]:
        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM model_downloads WHERE id=?", (int(download_id),)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise CivitaiDownloaderError("Download record not found.")
        return dict(row)

    def _row_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        status = str(row.get("status") or "queued")
        total = int(row.get("file_size_bytes") or 0)
        received = int(row.get("downloaded_bytes") or 0)
        progress = 0.0
        if status == "completed":
            progress = 100.0
        elif total > 0:
            progress = min(100.0, round(received * 100.0 / total, 2))
        return {
            "id": int(row.get("id") or 0),
            "civitai_model_id": int(row.get("civitai_model_id") or 0),
            "civitai_model_name": str(row.get("civitai_model_name") or ""),
            "civitai_version_id": int(row.get("civitai_version_id") or 0),
            "version_name": str(row.get("version_name") or ""),
            "folder": str(row.get("folder") or ""),
            "filename": str(row.get("filename") or ""),
            "file_size_bytes": total,
            "downloaded_bytes": received,
            "progress": progress,
            "status": status,
            "error": row.get("error"),
            "created_at": str(row.get("created_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
        }

    def _remove_partial_files(self, folder: str, filename: str) -> None:
        try:
            target, part = self._resolve_target(folder, filename)
            part.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
        except CivitaiDownloaderError:
            return
        except OSError:
            return


# ---------------------------------------------------------------------- worker

_download_thread: threading.Thread | None = None
_download_stop = threading.Event()
_download_lock = threading.Lock()
_worker_store: ConfigStore | None = None


def start_download_worker(store: ConfigStore) -> None:
    global _download_thread, _worker_store
    with _download_lock:
        if store is not None:
            _worker_store = store
        if _download_thread is None or not _download_thread.is_alive():
            _download_stop.clear()
            _download_thread = threading.Thread(
                target=_download_loop, daemon=True, name="CivitaiDownloadWorker"
            )
            _download_thread.start()


def stop_download_worker(*, wait: bool = False, timeout: float = 10.0) -> bool:
    _download_stop.set()
    with _download_lock:
        worker = _download_thread
    if wait and worker is not None and worker is not threading.current_thread():
        worker.join(timeout)
    return worker is None or not worker.is_alive()


def _download_loop() -> None:
    print("[Civitai] Download worker started", flush=True)
    while not _download_stop.is_set():
        row = _next_queued_download()
        if row is None:
            _download_stop.wait(1.0)
            continue
        try:
            _perform_download(row)
        except Exception as exc:  # pragma: no cover - defensive
            _mark_failed(int(row["id"]), str(exc))
        _download_stop.wait(0.1)


def _next_queued_download() -> dict[str, Any] | None:
    conn = database.get_conn()
    try:
        row = conn.execute(
            """SELECT * FROM model_downloads
            WHERE status='queued' ORDER BY id ASC LIMIT 1"""
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE model_downloads SET status='downloading', updated_at=datetime('now') WHERE id=?",
            (int(row["id"]),),
        )
        conn.commit()
        return dict(row)
    finally:
        conn.close()


def _perform_download(row: dict[str, Any]) -> None:
    download_id = int(row["id"])
    store = _worker_store
    if store is None:
        _mark_failed(download_id, "Download worker is not configured.")
        return
    service = CivitaiDownloaderService(store)
    try:
        target, part = service._resolve_target(str(row["folder"]), str(row["filename"]))
    except CivitaiDownloaderError as exc:
        _mark_failed(download_id, str(exc))
        return

    source_url = str(row.get("source_url") or "")
    token = _api_token(store)
    if token:
        separator = "&" if "?" in source_url else "?"
        source_url = f"{source_url}{separator}token={urllib.parse.quote(token)}"
    request = urllib.request.Request(source_url, headers=_request_headers(token))
    downloaded = 0
    last_update = 0.0
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("Content-Type") or ""
            if "text/html" in content_type.casefold():
                response.read(CHUNK_SIZE)
                raise CivitaiDownloaderError(_html_login_hint())
            headers_total = response.headers.get("Content-Length")
            total = int(headers_total) if headers_total and headers_total.isdigit() else int(row.get("file_size_bytes") or 0)
            if total:
                _update_progress(download_id, downloaded, total)
            with part.open("wb") as out:
                while True:
                    if _download_stop.is_set() or _is_cancelled(download_id):
                        raise _CancelledDownload()
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    out.write(chunk)
                    downloaded += len(chunk)
                    now = time.monotonic()
                    if now - last_update >= PROGRESS_INTERVAL_SECONDS:
                        _update_progress(download_id, downloaded, total)
                        last_update = now
        part.replace(target)
        _mark_completed(download_id, downloaded, total)
    except _CancelledDownload:
        part.unlink(missing_ok=True)
        _mark_cancelled(download_id)
    except urllib.error.HTTPError as exc:
        part.unlink(missing_ok=True)
        if exc.code in (401, 403):
            _mark_failed(download_id, _auth_hint())
        else:
            _mark_failed(download_id, f"Civitai returned HTTP {exc.code}.")
    except Exception as exc:
        part.unlink(missing_ok=True)
        _mark_failed(download_id, str(exc))


class _CancelledDownload(Exception):
    pass


def _is_cancelled(download_id: int) -> bool:
    conn = database.get_conn()
    try:
        row = conn.execute(
            "SELECT status FROM model_downloads WHERE id=?", (int(download_id),)
        ).fetchone()
    finally:
        conn.close()
    return row is None or row["status"] == "cancelled"


def _update_progress(download_id: int, downloaded: int, total: int) -> None:
    conn = database.get_conn()
    try:
        conn.execute(
            """UPDATE model_downloads
            SET downloaded_bytes=?, file_size_bytes=?, updated_at=datetime('now')
            WHERE id=?""",
            (int(downloaded), int(total), int(download_id)),
        )
        conn.commit()
    finally:
        conn.close()


def _mark_completed(download_id: int, downloaded: int, total: int) -> None:
    conn = database.get_conn()
    try:
        conn.execute(
            """UPDATE model_downloads
            SET status='completed', downloaded_bytes=?, file_size_bytes=?,
                error=NULL, updated_at=datetime('now')
            WHERE id=?""",
            (int(downloaded), int(total), int(download_id)),
        )
        conn.commit()
    finally:
        conn.close()
    invalidate_runtime_inventory()


def _mark_failed(download_id: int, message: str) -> None:
    conn = database.get_conn()
    try:
        conn.execute(
            """UPDATE model_downloads
            SET status='failed', error=?, updated_at=datetime('now')
            WHERE id=?""",
            (str(message)[:2000], int(download_id)),
        )
        conn.commit()
    finally:
        conn.close()


def _mark_cancelled(download_id: int) -> None:
    conn = database.get_conn()
    try:
        conn.execute(
            "UPDATE model_downloads SET error='Cancelled', updated_at=datetime('now') WHERE id=?",
            (int(download_id),),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------- helpers


def _auth_hint() -> str:
    return (
        "Civitai requires an API token for this download. "
        "Log in with 'civitai login' in a terminal, or add your token "
        "in the ComfyUI runtime settings (Civitai API token)."
    )


def _html_login_hint() -> str:
    return (
        "Civitai returned the login page instead of the model file. "
        "Log in with 'civitai login' in a terminal, or add your Civitai "
        "API token in the runtime settings to download."
    )


def _validate_types(types: str) -> str:
    requested = [part.strip() for part in str(types or "").split(",") if part.strip()]
    if not requested:
        return ""
    unknown = [item for item in requested if item not in CIVITAI_FILTER_TYPES]
    if unknown:
        raise CivitaiDownloaderError(
            "Unsupported Civitai model types: " + ", ".join(sorted(unknown))
        )
    return ",".join(dict.fromkeys(requested))


def _download_url(version_id: int, filename: str, file_type: str) -> str:
    params: list[tuple[str, str]] = []
    if str(file_type).strip():
        params.append(("type", str(file_type).strip()))
    params.append(("filename", filename))
    query = urllib.parse.urlencode(params)
    return f"https://civitai.com/api/download/models/{int(version_id)}?{query}"


def _sanitize_filename(filename: str) -> str:
    name = str(filename or "").strip().replace("\\", "/").split("/")[-1]
    name = re.sub(r"[<>:\"|?*\x00-\x1f]", "_", name).strip(" .")
    return name


def _primary_file(files: list[dict[str, Any]]) -> dict[str, Any] | None:
    for file in files:
        if file.get("primary"):
            return file
    return files[0] if files else None


def _size_kb_to_bytes(size_kb: Any) -> int:
    try:
        return int(float(size_kb) * 1024)
    except (TypeError, ValueError):
        return 0


def _first_version_images(item: dict[str, Any]) -> list[dict[str, Any]]:
    versions = item.get("modelVersions") if isinstance(item.get("modelVersions"), list) else []
    for version in versions:
        if isinstance(version, dict):
            images = version.get("images") if isinstance(version.get("images"), list) else []
            if images:
                return [img for img in images if isinstance(img, dict)]
    top = item.get("images") if isinstance(item.get("images"), list) else []
    return [img for img in top if isinstance(img, dict)]


def _all_version_images(data: dict[str, Any]) -> list[dict[str, Any]]:
    versions = data.get("modelVersions") if isinstance(data.get("modelVersions"), list) else []
    collected: list[dict[str, Any]] = []
    for version in versions:
        if not isinstance(version, dict):
            continue
        for image in version.get("images") or []:
            if isinstance(image, dict):
                collected.append(image)
    if not collected:
        top = data.get("images") if isinstance(data.get("images"), list) else []
        collected = [img for img in top if isinstance(img, dict)]
    return collected


def _preview_image(image: dict[str, Any]) -> dict[str, Any] | None:
    url = str(image.get("url") or "")
    if not _is_image_url(url):
        return None
    return {
        "url": url,
        "proxy_url": _preview_proxy_url(url),
        "width": int(image.get("width") or 0),
        "height": int(image.get("height") or 0),
        "nsfw": bool(image.get("nsfw")),
    }


_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")


def _is_image_url(url: str) -> bool:
    if not url:
        return False
    path = url.split("?", 1)[0].lower()
    return path.endswith(_IMAGE_EXTENSIONS)


def _preview_proxy_url(url: str) -> str:
    if not url or not url.startswith("https://"):
        return ""
    return "/api/editor/models/civitai/image?url=" + urllib.parse.quote(url, safe="")


def fetch_civitai_image(url: str, *, timeout: int = 30) -> bytes:
    """Download a Civitai image with the Referer/UA headers their CDN requires."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://civitai.com/",
            "Accept": "image/*",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise CivitaiDownloaderError(f"Civitai image returned HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CivitaiDownloaderError("Could not fetch the Civitai image. Check your connection.") from exc


def _clean_description(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    description = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", " ", description).strip()[:500]


__all__ = [
    "CIVITAI_FOLDER_MAP",
    "CIVITAI_FILTER_TYPES",
    "CivitaiDownloaderError",
    "CivitaiDownloaderService",
    "fetch_civitai_image",
    "start_download_worker",
    "stop_download_worker",
]
