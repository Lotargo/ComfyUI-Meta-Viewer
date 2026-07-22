from __future__ import annotations

import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any


class ComfyUIClientError(RuntimeError):
    """Raised when communicating with the ComfyUI API fails."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        payload: Any = None,
    ):
        self.status = status
        self.payload = payload
        super().__init__(message)


class ComfyUIClient:
    """Small standard-library client for the local ComfyUI HTTP API."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8188, timeout: float = 3.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def check_health(self) -> dict[str, Any]:
        system_stats = self._request_json("GET", "/system_stats")
        return {
            "online": True,
            "system_stats": system_stats,
            "queue_info": self.get_queue(),
        }

    def get_queue(self) -> dict[str, Any]:
        try:
            data = self._request_json("GET", "/queue")
        except ComfyUIClientError:
            return {
                "queue_running": [],
                "queue_pending": [],
                "running_count": 0,
                "pending_count": 0,
                "total_remaining": 0,
                "is_busy": False,
            }
        running = data.get("queue_running", []) if isinstance(data, dict) else []
        pending = data.get("queue_pending", []) if isinstance(data, dict) else []
        return {
            "queue_running": running,
            "queue_pending": pending,
            "running_count": len(running),
            "pending_count": len(pending),
            "total_remaining": len(running) + len(pending),
            "is_busy": bool(running or pending),
        }

    def get_object_info(self) -> dict[str, Any]:
        data = self._request_json("GET", "/object_info", timeout=max(self.timeout, 15.0))
        if not isinstance(data, dict):
            raise ComfyUIClientError("ComfyUI /object_info returned an invalid response")
        return data

    def list_model_folders(self) -> list[str]:
        data = self._request_json("GET", "/models")
        if not isinstance(data, list):
            raise ComfyUIClientError("ComfyUI /models returned an invalid response")
        return [str(item) for item in data]

    def list_models(self, folder: str) -> list[str]:
        encoded = urllib.parse.quote(str(folder), safe="")
        data = self._request_json("GET", f"/models/{encoded}", timeout=max(self.timeout, 10.0))
        if not isinstance(data, list):
            raise ComfyUIClientError(f"ComfyUI model folder '{folder}' returned an invalid response")
        return [str(item) for item in data]

    def queue_prompt(
        self,
        workflow: dict[str, Any],
        *,
        client_id: str,
        prompt_id: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "prompt": workflow,
            "client_id": client_id,
        }
        if prompt_id:
            payload["prompt_id"] = prompt_id
        if extra_data:
            payload["extra_data"] = extra_data
        data = self._request_json("POST", "/prompt", payload=payload, timeout=max(self.timeout, 30.0))
        if not isinstance(data, dict) or not data.get("prompt_id"):
            raise ComfyUIClientError("ComfyUI did not return a prompt ID", payload=data)
        return data

    def get_history(self, prompt_id: str) -> dict[str, Any]:
        encoded = urllib.parse.quote(prompt_id, safe="")
        data = self._request_json("GET", f"/history/{encoded}", timeout=max(self.timeout, 10.0))
        if not isinstance(data, dict):
            raise ComfyUIClientError("ComfyUI history response is invalid", payload=data)
        return data

    def get_job(self, prompt_id: str) -> dict[str, Any] | None:
        encoded = urllib.parse.quote(prompt_id, safe="")
        try:
            data = self._request_json("GET", f"/api/jobs/{encoded}", timeout=max(self.timeout, 10.0))
            return data if isinstance(data, dict) else None
        except ComfyUIClientError as exc:
            if exc.status not in {404, 405}:
                raise

        history = self.get_history(prompt_id)
        if prompt_id in history:
            item = history[prompt_id]
            status_info = item.get("status", {}) if isinstance(item, dict) else {}
            status_str = status_info.get("status_str")
            status = "completed" if status_str == "success" else "failed"
            prompt_record = item.get("prompt") if isinstance(item, dict) else None
            executed_workflow = (
                prompt_record[2]
                if isinstance(prompt_record, list)
                and len(prompt_record) > 2
                and isinstance(prompt_record[2], dict)
                else None
            )
            return {
                "id": prompt_id,
                "status": status,
                "outputs": item.get("outputs", {}),
                "execution_status": status_info,
                "workflow": {"prompt": executed_workflow} if executed_workflow else None,
            }

        queue = self.get_queue()
        for position, item in enumerate(queue.get("queue_running", [])):
            if len(item) > 1 and item[1] == prompt_id:
                return {"id": prompt_id, "status": "in_progress", "queue_position": position}
        for position, item in enumerate(queue.get("queue_pending", [])):
            if len(item) > 1 and item[1] == prompt_id:
                return {"id": prompt_id, "status": "pending", "queue_position": position}
        return None

    def cancel_prompt(self, prompt_id: str) -> bool:
        encoded = urllib.parse.quote(prompt_id, safe="")
        try:
            data = self._request_json("POST", f"/api/jobs/{encoded}/cancel", payload={})
            return bool(data.get("cancelled")) if isinstance(data, dict) else True
        except ComfyUIClientError as exc:
            if exc.status not in {404, 405}:
                raise
        self._request_json("POST", "/queue", payload={"delete": [prompt_id]})
        try:
            self._request_json("POST", "/interrupt", payload={"prompt_id": prompt_id})
        except ComfyUIClientError:
            pass
        return True

    def download_output(self, output: dict[str, Any]) -> bytes:
        filename = output.get("filename")
        if not filename:
            raise ComfyUIClientError("ComfyUI output does not include a filename")
        query = urllib.parse.urlencode({
            "filename": filename,
            "subfolder": output.get("subfolder", ""),
            "type": output.get("type", "output"),
        })
        return self._request_bytes("GET", f"/view?{query}", timeout=max(self.timeout, 60.0))

    def upload_image(
        self,
        filename: str,
        data: bytes,
        *,
        subfolder: str = "cmv",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        boundary = f"----cmv-{uuid.uuid4().hex}"
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        parts: list[bytes] = []

        def add_field(name: str, value: str) -> None:
            parts.extend([
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                value.encode("utf-8"),
                b"\r\n",
            ])

        safe_filename = filename.replace('"', "_").replace("\r", "_").replace("\n", "_")
        parts.extend([
            f"--{boundary}\r\n".encode("ascii"),
            f'Content-Disposition: form-data; name="image"; filename="{safe_filename}"\r\n'.encode("utf-8"),
            f"Content-Type: {content_type}\r\n\r\n".encode("ascii"),
            data,
            b"\r\n",
        ])
        add_field("type", "input")
        add_field("subfolder", subfolder)
        add_field("overwrite", "true" if overwrite else "false")
        parts.append(f"--{boundary}--\r\n".encode("ascii"))
        raw = b"".join(parts)
        response = self._request_json(
            "POST",
            "/upload/image",
            raw_data=raw,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            timeout=max(self.timeout, 60.0),
        )
        if not isinstance(response, dict) or not response.get("name"):
            raise ComfyUIClientError("ComfyUI image upload response is invalid", payload=response)
        return response

    def interrupt(self) -> bool:
        self._request_json("POST", "/interrupt", payload={})
        return True

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: Any = None,
        raw_data: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        request_headers = {
            "User-Agent": "ComfyUI-Meta-Viewer",
            "Accept": "application/json",
        }
        request_headers.update(headers or {})
        body = raw_data
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        data = self._request_bytes(
            method,
            path,
            data=body,
            headers=request_headers,
            timeout=timeout,
        )
        if not data:
            return {}
        try:
            return json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ComfyUIClientError(
                f"ComfyUI returned invalid JSON for {path}: {exc}",
                payload=data[:500],
            ) from exc

    def _request_bytes(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> bytes:
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers or {"User-Agent": "ComfyUI-Meta-Viewer"},
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            parsed: Any = raw.decode("utf-8", errors="replace")
            try:
                parsed = json.loads(parsed)
            except json.JSONDecodeError:
                pass
            detail = parsed.get("error") if isinstance(parsed, dict) else parsed
            raise ComfyUIClientError(
                f"ComfyUI API {path} returned HTTP {exc.code}: {detail}",
                status=exc.code,
                payload=parsed,
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ComfyUIClientError(
                f"Cannot connect to ComfyUI API at {self.base_url}: {exc}",
            ) from exc


__all__ = ["ComfyUIClient", "ComfyUIClientError"]
