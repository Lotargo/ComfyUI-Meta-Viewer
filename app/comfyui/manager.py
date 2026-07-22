from __future__ import annotations

import os
import shlex
import subprocess
import sys
import threading
import time
from collections import deque
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

from .client import ComfyUIClient, ComfyUIClientError
from .detector import ComfyUIDetectionResult, detect_comfyui
from .launcher import generate_launcher_script


class ComfyUIMode(str, Enum):
    NONE = "none"
    MANAGED = "managed"
    EXTERNAL = "external"


class ComfyUIStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    BUSY = "busy"
    STOPPING = "stopping"
    ERROR = "error"
    EXTERNAL = "external"


class ComfyUIManager:
    """Thread-safe Process & Integration Manager for local ComfyUI.

    Handles:
    - Managed process launching (subprocess.Popen)
    - Stdout/stderr log capturing into ring buffer
    - Health polling & readiness detection
    - External ComfyUI detection & connection
    - Interrupt and clean stopping
    """

    def __init__(self, max_log_lines: int = 1000):
        self._lock = threading.RLock()
        self._mode: ComfyUIMode = ComfyUIMode.NONE
        self._status: ComfyUIStatus = ComfyUIStatus.STOPPED
        self._process: subprocess.Popen | None = None
        self._job_object = None
        self._host: str = "127.0.0.1"
        self._port: int = 8188
        self._last_error: str | None = None
        self._logs: deque[str] = deque(maxlen=max_log_lines)
        self._reader_thread: threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None
        self._stop_monitor_event = threading.Event()
        self._installation: ComfyUIDetectionResult | None = None
        self._launcher_script: Path | None = None

    @property
    def mode(self) -> ComfyUIMode:
        with self._lock:
            return self._mode

    @property
    def status(self) -> ComfyUIStatus:
        with self._lock:
            return self._status

    @property
    def pid(self) -> int | None:
        with self._lock:
            if self._mode == ComfyUIMode.MANAGED and self._process:
                return self._process.pid
            return None

    def get_info(self) -> dict[str, Any]:
        with self._lock:
            return {
                "mode": self._mode.value,
                "status": self._status.value,
                "pid": self.pid,
                "host": self._host,
                "port": self._port,
                "last_error": self._last_error,
                "installation": self._installation.to_dict() if self._installation else None,
                "launcher_script": str(self._launcher_script) if self._launcher_script else None,
            }

    def get_logs(self, max_lines: int = 200) -> list[str]:
        with self._lock:
            lines = list(self._logs)
            return lines[-max_lines:]

    def clear_logs(self) -> None:
        with self._lock:
            self._logs.clear()

    def set_installation(
        self,
        install_path: str | Path,
        custom_python: str | Path | None = None,
    ) -> ComfyUIDetectionResult:
        with self._lock:
            detection = detect_comfyui(install_path, custom_python=custom_python)
            self._installation = detection
            if not detection.is_valid:
                self._last_error = detection.error
            else:
                self._last_error = None
            return detection

    def start_managed(
        self,
        install_path: str | Path,
        host: str = "127.0.0.1",
        port: int = 8188,
        extra_args: str | Sequence[str] | None = None,
        custom_python: str | Path | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if self._mode == ComfyUIMode.MANAGED and self._process and self._process.poll() is None:
                raise RuntimeError("ComfyUI managed process is already running.")

            detection = self.set_installation(install_path, custom_python=custom_python)
            if not detection.is_valid:
                self._status = ComfyUIStatus.ERROR
                self._last_error = detection.error or "Invalid installation directory"
                raise ValueError(f"Cannot start ComfyUI: {self._last_error}")

            self._host = host
            self._port = port

            try:
                self._launcher_script = generate_launcher_script(
                    detection=detection,
                    extra_args=extra_args,
                    host=host,
                    port=port,
                )
            except Exception as exc:
                self._log(f"[CMV] Warning: failed to generate launcher script: {exc}")

            cmd = [str(detection.interpreter), str(detection.main_py), "--listen", host, "--port", str(port)]
            if extra_args:
                if isinstance(extra_args, str):
                    tokens = shlex.split(extra_args) if extra_args.strip() else []
                else:
                    tokens = list(extra_args)
                cmd.extend(tokens)

            self._log(f"[CMV] Launching ComfyUI managed process: {' '.join(cmd)}")
            self._log(f"[CMV] Working directory: {detection.comfy_dir}")

            popen_kwargs: dict[str, Any] = {
                "cwd": str(detection.comfy_dir),
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "bufsize": 1,
            }

            if sys.platform == "win32" or os.name == "nt":
                self._setup_win32_job_object(popen_kwargs)

            try:
                self._process = subprocess.Popen(cmd, **popen_kwargs)
            except Exception as exc:
                self._status = ComfyUIStatus.ERROR
                self._last_error = str(exc)
                self._log(f"[CMV] Failed to spawn process: {exc}")
                raise RuntimeError(f"Failed to spawn ComfyUI process: {exc}") from exc

            self._mode = ComfyUIMode.MANAGED
            self._status = ComfyUIStatus.STARTING
            self._last_error = None

            self._reader_thread = threading.Thread(
                target=self._read_stdout_loop,
                args=(self._process,),
                daemon=True,
            )
            self._reader_thread.start()

            self._stop_monitor_event.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
            )
            self._monitor_thread.start()

            return self.get_info()

    def stop_managed(self) -> None:
        with self._lock:
            if self._mode != ComfyUIMode.MANAGED or not self._process:
                return

            self._status = ComfyUIStatus.STOPPING
            self._log("[CMV] Stopping managed ComfyUI process...")

            proc = self._process
            self._process = None

        if proc.poll() is None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    self._log("[CMV] Process did not exit within timeout, killing...")
                    proc.kill()
                    proc.wait(timeout=2.0)
            except Exception as exc:
                self._log(f"[CMV] Error terminating process: {exc}")

        with self._lock:
            self._mode = ComfyUIMode.NONE
            self._status = ComfyUIStatus.STOPPED
            self._log("[CMV] Managed ComfyUI process stopped.")

    def restart_managed(
        self,
        install_path: str | Path | None = None,
        host: str | None = None,
        port: int | None = None,
        extra_args: str | Sequence[str] | None = None,
        custom_python: str | Path | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            target_path = install_path or (self._installation.root_path if self._installation else None)
            target_host = host or self._host
            target_port = port or self._port

        if not target_path:
            raise ValueError("No installation path available for restart.")

        self.stop_managed()
        time.sleep(0.5)
        return self.start_managed(
            install_path=target_path,
            host=target_host,
            port=target_port,
            extra_args=extra_args,
            custom_python=custom_python,
        )

    def check_external_or_status(self, host: str = "127.0.0.1", port: int = 8188) -> dict[str, Any]:
        """Poll API status. If no managed process is running, check if an external instance is running."""
        with self._lock:
            mode = self._mode
            managed_proc = self._process

        client = ComfyUIClient(host=host, port=port)
        try:
            health = client.check_health()
            online = health.get("online", False)
            queue_info = health.get("queue_info", {})
            is_busy = queue_info.get("is_busy", False)

            with self._lock:
                if mode == ComfyUIMode.MANAGED and managed_proc and managed_proc.poll() is None:
                    self._status = ComfyUIStatus.BUSY if is_busy else ComfyUIStatus.READY
                    self._last_error = None
                elif mode != ComfyUIMode.MANAGED:
                    self._mode = ComfyUIMode.EXTERNAL
                    self._status = ComfyUIStatus.EXTERNAL
                    self._host = host
                    self._port = port
                    self._last_error = None

            return {
                "mode": self._mode.value,
                "status": self._status.value,
                "online": True,
                "is_busy": is_busy,
                "queue_info": queue_info,
                "system_stats": health.get("system_stats"),
            }
        except ComfyUIClientError as exc:
            with self._lock:
                if self._mode == ComfyUIMode.EXTERNAL:
                    self._mode = ComfyUIMode.NONE
                    self._status = ComfyUIStatus.STOPPED
                elif self._mode == ComfyUIMode.MANAGED:
                    if self._process and self._process.poll() is not None:
                        exit_code = self._process.poll()
                        self._status = ComfyUIStatus.ERROR
                        self._last_error = f"ComfyUI process exited unexpectedly with code {exit_code}"

            return {
                "mode": self._mode.value,
                "status": self._status.value,
                "online": False,
                "error": str(exc),
            }

    def interrupt_generation(self) -> bool:
        client = ComfyUIClient(host=self._host, port=self._port)
        return client.interrupt()

    def _log(self, message: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {message}"
        self._logs.append(line)

    def _read_stdout_loop(self, process: subprocess.Popen) -> None:
        if not process.stdout:
            return
        try:
            for line in iter(process.stdout.readline, ""):
                if not line:
                    break
                stripped = line.rstrip()
                if stripped:
                    with self._lock:
                        self._logs.append(stripped)
        except (OSError, ValueError):
            pass

    def _monitor_loop(self) -> None:
        start_time = time.time()
        ready_detected = False

        while not self._stop_monitor_event.is_set():
            with self._lock:
                proc = self._process
                mode = self._mode

            if mode != ComfyUIMode.MANAGED or not proc:
                break

            exit_code = proc.poll()
            if exit_code is not None:
                with self._lock:
                    self._status = ComfyUIStatus.ERROR
                    self._last_error = f"Managed ComfyUI process exited with code {exit_code}"
                    self._log(f"[CMV] Process exited unexpectedly with code {exit_code}")
                break

            client = ComfyUIClient(host=self._host, port=self._port)
            try:
                health = client.check_health()
                queue_info = health.get("queue_info", {})
                is_busy = queue_info.get("is_busy", False)

                with self._lock:
                    if self._mode == ComfyUIMode.MANAGED:
                        if not ready_detected:
                            ready_detected = True
                            self._log(f"[CMV] ComfyUI API is ready at http://{self._host}:{self._port}")
                        self._status = ComfyUIStatus.BUSY if is_busy else ComfyUIStatus.READY
                        self._last_error = None
            except ComfyUIClientError:
                with self._lock:
                    if self._mode == ComfyUIMode.MANAGED and not ready_detected:
                        self._status = ComfyUIStatus.STARTING
                        if time.time() - start_time > 120.0:
                            self._status = ComfyUIStatus.ERROR
                            self._last_error = "Timeout waiting for ComfyUI API readiness"
                            self._log("[CMV] Timed out waiting for ComfyUI API readiness")

            time.sleep(1.5)

    def _setup_win32_job_object(self, popen_kwargs: dict[str, Any]) -> None:
        try:
            import win32job
            import win32process

            job = win32job.CreateJobObject(None, "")
            info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
            info['BasicLimitInformation']['LimitFlags'] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)

            popen_kwargs["creationflags"] = win32process.CREATE_BREAKAWAY_FROM_JOB
            self._job_object = job
        except (ImportError, Exception):
            pass


comfy_manager = ComfyUIManager()
