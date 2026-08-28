from __future__ import annotations

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

USER_AGENT = "ComfyUI-Meta-Viewer/1.0"
TIMEOUT_SECONDS = 30
CHUNK_SIZE = 1024 * 1024
PROGRESS_INTERVAL_SECONDS = 0.25
MODEL_FILE_SUFFIXES = {
    ".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".onnx", ".patch", ".txt"
}
ACTIVE_STATUSES = {"queued", "downloading", "paused"}


class SimpleModelDownloaderError(RuntimeError):
    """Raised when a fixed Simple Mode model dependency cannot be queued or downloaded."""


class _PausedDownload(Exception):
    pass


class _CancelledDownload(Exception):
    pass


def _ensure_schema() -> None:
    conn = database.get_conn()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS simple_model_downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id TEXT NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                folder TEXT NOT NULL,
                filename TEXT NOT NULL,
                source_url TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL DEFAULT 0,
                downloaded_bytes INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'queued',
                error TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )
        conn.commit()
    finally:
        conn.close()


def _recover_interrupted_downloads() -> None:
    _ensure_schema()
    conn = database.get_conn()
    try:
        conn.execute(
            """UPDATE simple_model_downloads
               SET status='queued', updated_at=datetime('now')
               WHERE status='downloading'"""
        )
        conn.commit()
    finally:
        conn.close()


def _api_token(store: ConfigStore | None) -> str:
    if store is None:
        return ""
    return str((store.comfyui_settings() or {}).get("civitai_api_token") or "").strip()


def _is_civitai_url(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").casefold()
    return host == "civitai.com" or host.endswith(".civitai.com")


def _request_for(url: str, *, store: ConfigStore, resume_from: int = 0) -> urllib.request.Request:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise SimpleModelDownloaderError("Model download URL must use HTTPS.")

    headers = {"User-Agent": USER_AGENT}
    source_url = url
    if _is_civitai_url(url):
        token = _api_token(store)
        if token:
            headers["Authorization"] = f"Bearer {token}"
            query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            if not any(key == "token" for key, _ in query):
                query.append(("token", token))
                source_url = urllib.parse.urlunparse(
                    parsed._replace(query=urllib.parse.urlencode(query))
                )
    if resume_from > 0:
        headers["Range"] = f"bytes={resume_from}-"
    return urllib.request.Request(source_url, headers=headers)


def _content_range_total(value: str | None) -> int:
    if not value or "/" not in value:
        return 0
    total = value.rsplit("/", 1)[-1].strip()
    return int(total) if total.isdigit() else 0


class SimpleModelDownloaderService:
    """Background downloader for trusted dependencies declared by Simple Mode model packs."""

    def __init__(self, store: ConfigStore):
        self.store = store
        _ensure_schema()

    def resolve_model_root(self) -> Path:
        config = self.store.comfyui_settings()
        install_path = str(config.get("install_path") or "").strip()
        if not install_path:
            raise SimpleModelDownloaderError(
                "Сначала укажите папку установленного ComfyUI в настройках Create."
            )
        detection = detect_comfyui(
            install_path,
            custom_python=config.get("custom_python"),
        )
        if detection.comfy_dir is None:
            raise SimpleModelDownloaderError(
                "В выбранной папке не найден main.py или ComfyUI/main.py. Проверьте путь в настройках."
            )
        model_root = (Path(detection.comfy_dir) / "models").resolve()
        model_root.mkdir(parents=True, exist_ok=True)
        return model_root

    def _resolve_target(self, folder: str, filename: str) -> tuple[Path, Path]:
        clean_folder = str(folder or "").strip()
        clean_name = Path(str(filename or "").strip()).name
        if clean_folder not in FOLDER_RESOURCE_TYPES:
            raise SimpleModelDownloaderError(f"Неизвестная папка моделей ComfyUI: {clean_folder}")
        if not clean_name or Path(clean_name).suffix.casefold() not in MODEL_FILE_SUFFIXES:
            raise SimpleModelDownloaderError("Некорректное имя файла модели.")

        root = self.resolve_model_root()
        directory = (root / clean_folder).resolve()
        try:
            directory.relative_to(root)
        except ValueError as exc:
            raise SimpleModelDownloaderError("Некорректная папка назначения.") from exc
        directory.mkdir(parents=True, exist_ok=True)
        target = (directory / clean_name).resolve()
        try:
            target.relative_to(directory)
        except ValueError as exc:
            raise SimpleModelDownloaderError("Некорректное имя файла модели.") from exc
        return target, target.with_name(target.name + ".part")

    def queue(
        self,
        *,
        profile_id: str,
        display_name: str,
        folder: str,
        filename: str,
        source_url: str,
    ) -> dict[str, Any]:
        source_url = str(source_url or "").strip()
        parsed = urllib.parse.urlparse(source_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise SimpleModelDownloaderError("Для этого компонента нет безопасной HTTPS-ссылки.")
        target, _ = self._resolve_target(folder, filename)
        if target.is_file() and target.stat().st_size > 0:
            invalidate_runtime_inventory()
            size = target.stat().st_size
            return {
                "id": 0,
                "profile_id": profile_id,
                "display_name": display_name,
                "folder": folder,
                "filename": Path(filename).name,
                "source_url": source_url,
                "file_size_bytes": size,
                "downloaded_bytes": size,
                "progress": 100.0,
                "status": "completed",
                "error": None,
            }

        conn = database.get_conn()
        try:
            row = conn.execute(
                """SELECT * FROM simple_model_downloads
                   WHERE profile_id=? AND folder=? AND filename=?
                   ORDER BY id DESC LIMIT 1""",
                (profile_id, folder, Path(filename).name),
            ).fetchone()
            if row is not None:
                current = dict(row)
                status = str(current.get("status") or "queued")
                if status in ACTIVE_STATUSES:
                    result = self._payload(current)
                    start_simple_download_worker(self.store)
                    return result
                if status in {"failed", "cancelled"}:
                    conn.execute(
                        """UPDATE simple_model_downloads
                           SET display_name=?, source_url=?, status='queued', error=NULL,
                               updated_at=datetime('now') WHERE id=?""",
                        (display_name, source_url, int(current["id"])),
                    )
                    conn.commit()
                    download_id = int(current["id"])
                else:
                    download_id = 0
            else:
                download_id = 0

            if download_id == 0:
                cursor = conn.execute(
                    """INSERT INTO simple_model_downloads
                       (profile_id, display_name, folder, filename, source_url)
                       VALUES (?, ?, ?, ?, ?)""",
                    (profile_id, display_name, folder, Path(filename).name, source_url),
                )
                conn.commit()
                download_id = int(cursor.lastrowid)
        finally:
            conn.close()

        start_simple_download_worker(self.store)
        return self.get(download_id)

    def get(self, download_id: int) -> dict[str, Any]:
        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM simple_model_downloads WHERE id=?", (int(download_id),)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise SimpleModelDownloaderError("Загрузка не найдена.")
        return self._payload(dict(row))

    def list(self, *, profile_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        conn = database.get_conn()
        try:
            if profile_id:
                rows = conn.execute(
                    """SELECT * FROM simple_model_downloads
                       WHERE profile_id=? ORDER BY id DESC LIMIT ?""",
                    (profile_id, max(1, min(int(limit), 500))),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM simple_model_downloads ORDER BY id DESC LIMIT ?",
                    (max(1, min(int(limit), 500)),),
                ).fetchall()
        finally:
            conn.close()
        return [self._payload(dict(row)) for row in rows]

    def pause(self, download_id: int) -> dict[str, Any]:
        return self._set_status(download_id, {"queued", "downloading"}, "paused")

    def resume(self, download_id: int) -> dict[str, Any]:
        result = self._set_status(
            download_id,
            {"paused", "failed", "cancelled"},
            "queued",
            clear_error=True,
        )
        start_simple_download_worker(self.store)
        return result

    def cancel(self, download_id: int) -> dict[str, Any]:
        return self._set_status(
            download_id,
            {"queued", "downloading", "paused", "failed"},
            "cancelled",
            clear_error=True,
        )

    def _set_status(
        self,
        download_id: int,
        allowed: set[str],
        status: str,
        *,
        clear_error: bool = False,
    ) -> dict[str, Any]:
        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT status FROM simple_model_downloads WHERE id=?", (int(download_id),)
            ).fetchone()
            if row is None:
                raise SimpleModelDownloaderError("Загрузка не найдена.")
            current = str(row["status"])
            if current not in allowed:
                return self.get(download_id)
            if clear_error:
                conn.execute(
                    """UPDATE simple_model_downloads
                       SET status=?, error=NULL, updated_at=datetime('now') WHERE id=?""",
                    (status, int(download_id)),
                )
            else:
                conn.execute(
                    """UPDATE simple_model_downloads
                       SET status=?, updated_at=datetime('now') WHERE id=?""",
                    (status, int(download_id)),
                )
            conn.commit()
        finally:
            conn.close()
        return self.get(download_id)

    @staticmethod
    def _payload(row: dict[str, Any]) -> dict[str, Any]:
        total = int(row.get("file_size_bytes") or 0)
        received = int(row.get("downloaded_bytes") or 0)
        status = str(row.get("status") or "queued")
        if status == "completed":
            progress = 100.0
        elif total > 0:
            progress = min(100.0, round(received * 100.0 / total, 2))
        else:
            progress = 0.0
        return {
            "id": int(row.get("id") or 0),
            "profile_id": str(row.get("profile_id") or ""),
            "display_name": str(row.get("display_name") or row.get("filename") or ""),
            "folder": str(row.get("folder") or ""),
            "filename": str(row.get("filename") or ""),
            "source_url": str(row.get("source_url") or ""),
            "file_size_bytes": total,
            "downloaded_bytes": received,
            "progress": progress,
            "status": status,
            "error": row.get("error"),
            "created_at": str(row.get("created_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
        }


_worker_thread: threading.Thread | None = None
_worker_lock = threading.Lock()
_worker_stop = threading.Event()
_worker_store: ConfigStore | None = None
_recovery_done = False


def start_simple_download_worker(store: ConfigStore) -> None:
    global _worker_thread, _worker_store, _recovery_done
    with _worker_lock:
        _worker_store = store
        if not _recovery_done:
            _recover_interrupted_downloads()
            _recovery_done = True
        if _worker_thread is None or not _worker_thread.is_alive():
            _worker_stop.clear()
            _worker_thread = threading.Thread(
                target=_download_loop,
                daemon=True,
                name="SimpleModelDownloadWorker",
            )
            _worker_thread.start()


def _download_loop() -> None:
    while not _worker_stop.is_set():
        row = _next_queued()
        if row is None:
            _worker_stop.wait(0.75)
            continue
        try:
            _perform_download(row)
        except Exception as exc:  # pragma: no cover - defensive guard
            _mark_failed(int(row["id"]), str(exc))
        _worker_stop.wait(0.08)


def _next_queued() -> dict[str, Any] | None:
    _ensure_schema()
    conn = database.get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM simple_model_downloads WHERE status='queued' ORDER BY id ASC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            """UPDATE simple_model_downloads SET status='downloading', error=NULL,
               updated_at=datetime('now') WHERE id=?""",
            (int(row["id"]),),
        )
        conn.commit()
        return dict(row)
    finally:
        conn.close()


def _current_status(download_id: int) -> str:
    conn = database.get_conn()
    try:
        row = conn.execute(
            "SELECT status FROM simple_model_downloads WHERE id=?", (int(download_id),)
        ).fetchone()
    finally:
        conn.close()
    return str(row["status"]) if row is not None else "cancelled"


def _perform_download(row: dict[str, Any]) -> None:
    store = _worker_store
    download_id = int(row["id"])
    if store is None:
        _mark_failed(download_id, "Downloader is not configured.")
        return
    service = SimpleModelDownloaderService(store)
    target, part = service._resolve_target(str(row["folder"]), str(row["filename"]))
    source_url = str(row.get("source_url") or "")

    resume_from = part.stat().st_size if part.is_file() else 0
    request = _request_for(source_url, store=store, resume_from=resume_from)
    downloaded = resume_from
    total = int(row.get("file_size_bytes") or 0)
    last_update = 0.0

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status_code = int(getattr(response, "status", 200) or 200)
            content_type = str(response.headers.get("Content-Type") or "")
            if "text/html" in content_type.casefold():
                response.read(min(CHUNK_SIZE, 128 * 1024))
                if _is_civitai_url(source_url):
                    raise SimpleModelDownloaderError(
                        "Civitai вернул страницу входа. Добавьте API token в настройках ComfyUI."
                    )
                raise SimpleModelDownloaderError("Ссылка вернула HTML вместо файла модели.")

            content_length = response.headers.get("Content-Length")
            response_length = int(content_length) if content_length and content_length.isdigit() else 0
            range_total = _content_range_total(response.headers.get("Content-Range"))
            if status_code == 206 and resume_from > 0:
                mode = "ab"
                total = range_total or (resume_from + response_length if response_length else total)
            else:
                mode = "wb"
                downloaded = 0
                total = range_total or response_length or total

            _update_progress(download_id, downloaded, total)
            with part.open(mode) as out:
                while True:
                    current = _current_status(download_id)
                    if current == "paused":
                        raise _PausedDownload()
                    if current == "cancelled":
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
        _mark_completed(download_id, downloaded, total or downloaded)
        invalidate_runtime_inventory()
    except _PausedDownload:
        _mark_paused(download_id, downloaded, total)
    except _CancelledDownload:
        part.unlink(missing_ok=True)
        _mark_cancelled(download_id)
    except urllib.error.HTTPError as exc:
        if exc.code == 416 and part.is_file():
            part.unlink(missing_ok=True)
        if exc.code in (401, 403) and _is_civitai_url(source_url):
            _mark_failed(
                download_id,
                "Civitai требует авторизацию. Добавьте API token в настройках ComfyUI и повторите.",
            )
        else:
            _mark_failed(download_id, f"Сервер загрузки вернул HTTP {exc.code}.")
    except (urllib.error.URLError, TimeoutError, OSError, SimpleModelDownloaderError) as exc:
        _mark_failed(download_id, str(exc))


def _update_progress(download_id: int, downloaded: int, total: int) -> None:
    conn = database.get_conn()
    try:
        conn.execute(
            """UPDATE simple_model_downloads
               SET downloaded_bytes=?, file_size_bytes=?, updated_at=datetime('now') WHERE id=?""",
            (max(0, int(downloaded)), max(0, int(total)), int(download_id)),
        )
        conn.commit()
    finally:
        conn.close()


def _mark_completed(download_id: int, downloaded: int, total: int) -> None:
    conn = database.get_conn()
    try:
        conn.execute(
            """UPDATE simple_model_downloads
               SET status='completed', downloaded_bytes=?, file_size_bytes=?, error=NULL,
                   updated_at=datetime('now') WHERE id=?""",
            (int(downloaded), int(total or downloaded), int(download_id)),
        )
        conn.commit()
    finally:
        conn.close()


def _mark_failed(download_id: int, message: str) -> None:
    conn = database.get_conn()
    try:
        conn.execute(
            """UPDATE simple_model_downloads
               SET status='failed', error=?, updated_at=datetime('now') WHERE id=?""",
            (str(message)[:2000], int(download_id)),
        )
        conn.commit()
    finally:
        conn.close()


def _mark_paused(download_id: int, downloaded: int, total: int) -> None:
    conn = database.get_conn()
    try:
        conn.execute(
            """UPDATE simple_model_downloads
               SET status='paused', downloaded_bytes=?, file_size_bytes=?, error=NULL,
                   updated_at=datetime('now') WHERE id=?""",
            (int(downloaded), int(total), int(download_id)),
        )
        conn.commit()
    finally:
        conn.close()


def _mark_cancelled(download_id: int) -> None:
    conn = database.get_conn()
    try:
        conn.execute(
            """UPDATE simple_model_downloads
               SET status='cancelled', error=NULL, updated_at=datetime('now') WHERE id=?""",
            (int(download_id),),
        )
        conn.commit()
    finally:
        conn.close()


__all__ = [
    "SimpleModelDownloaderError",
    "SimpleModelDownloaderService",
    "start_simple_download_worker",
]
