from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class ComfyUIClientError(RuntimeError):
    """Raised when communicating with ComfyUI API fails."""


class ComfyUIClient:
    """HTTP client for ComfyUI API endpoint checks, system stats, and prompt interrupts."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8188, timeout: float = 3.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def check_health(self) -> dict[str, Any]:
        """Query /system_stats and /queue to check API responsiveness.

        Returns dict with online status, queue_info, and system_stats.
        Raises ComfyUIClientError if unreachable or invalid response.
        """
        url = f"{self.base_url}/system_stats"
        req = urllib.request.Request(url, headers={"User-Agent": "ComfyUI-Meta-Viewer"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    queue_info = self.get_queue()
                    return {
                        "online": True,
                        "system_stats": data,
                        "queue_info": queue_info,
                    }
                raise ComfyUIClientError(f"ComfyUI API returned HTTP {resp.status}")
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise ComfyUIClientError(f"Cannot connect to ComfyUI API at {self.base_url}: {exc}") from exc

    def get_queue(self) -> dict[str, Any]:
        """Fetch prompt queue state from /queue endpoint."""
        url = f"{self.base_url}/queue"
        req = urllib.request.Request(url, headers={"User-Agent": "ComfyUI-Meta-Viewer"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    running = data.get("queue_running", [])
                    pending = data.get("queue_pending", [])
                    return {
                        "queue_running": running,
                        "queue_pending": pending,
                        "running_count": len(running),
                        "pending_count": len(pending),
                        "total_remaining": len(running) + len(pending),
                        "is_busy": len(running) > 0 or len(pending) > 0,
                    }
                return {"running_count": 0, "pending_count": 0, "total_remaining": 0, "is_busy": False}
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            return {"running_count": 0, "pending_count": 0, "total_remaining": 0, "is_busy": False}

    def interrupt(self) -> bool:
        """Send POST /interrupt to cancel active execution."""
        url = f"{self.base_url}/interrupt"
        req = urllib.request.Request(
            url,
            data=b"",
            headers={"User-Agent": "ComfyUI-Meta-Viewer", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status in (200, 201, 202)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ComfyUIClientError(f"Failed to interrupt ComfyUI execution: {exc}") from exc
