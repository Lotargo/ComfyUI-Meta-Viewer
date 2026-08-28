from __future__ import annotations

import urllib.error
import urllib.request
from typing import Any

from . import simple_downloader as downloader

_installed = False
_original_perform_download = downloader._perform_download
_original_cancel = downloader.SimpleModelDownloaderService.cancel


def _probe_remote_size(row: dict[str, Any]) -> int:
    store = downloader._worker_store
    source_url = str(row.get("source_url") or "")
    if store is None or not source_url:
        return 0

    try:
        request = downloader._request_for(source_url, store=store)
        request.add_header("Range", "bytes=0-0")
        with urllib.request.urlopen(request, timeout=downloader.TIMEOUT_SECONDS) as response:
            content_type = str(response.headers.get("Content-Type") or "").casefold()
            if "text/html" in content_type:
                return 0
            range_total = downloader._content_range_total(response.headers.get("Content-Range"))
            if range_total > 0:
                return range_total
            status_code = int(getattr(response, "status", 200) or 200)
            content_length = str(response.headers.get("Content-Length") or "")
            if status_code != 206 and content_length.isdigit():
                return int(content_length)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0
    return 0


def _perform_download_with_size_probe(row: dict[str, Any]) -> None:
    mutable = dict(row)
    if int(mutable.get("file_size_bytes") or 0) <= 0:
        total = _probe_remote_size(mutable)
        if total > 0:
            mutable["file_size_bytes"] = total
            downloader._update_progress(
                int(mutable["id"]),
                int(mutable.get("downloaded_bytes") or 0),
                total,
            )
    _original_perform_download(mutable)


def _cancel_and_cleanup(self: downloader.SimpleModelDownloaderService, download_id: int) -> dict[str, Any]:
    before = self.get(download_id)
    result = _original_cancel(self, download_id)
    if result.get("status") == "cancelled":
        try:
            _, part = self._resolve_target(str(before.get("folder") or ""), str(before.get("filename") or ""))
            part.unlink(missing_ok=True)
        except (OSError, downloader.SimpleModelDownloaderError):
            # An active writer may still own the .part file (notably on Windows).
            # The downloader loop observes the cancelled status and removes it on its next chunk.
            pass
    return result


def install_simple_download_probe() -> None:
    global _installed
    if _installed:
        return
    downloader._perform_download = _perform_download_with_size_probe
    downloader.SimpleModelDownloaderService.cancel = _cancel_and_cleanup
    _installed = True


__all__ = ["install_simple_download_probe"]
