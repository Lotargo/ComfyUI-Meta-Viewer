from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cli import CLIIntegrationError, CommandResult, sanitize_output


_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


@dataclass
class _WindowsJob:
    handle: Any
    kernel32: Any
    closed: bool = False

    @classmethod
    def attach(cls, process: subprocess.Popen[str]) -> _WindowsJob | None:
        if os.name != "nt":
            return None

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            return None

        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        configured = kernel32.SetInformationJobObject(
            handle,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        process_handle = getattr(process, "_handle", None)
        assigned = bool(
            configured
            and process_handle
            and kernel32.AssignProcessToJobObject(
                handle,
                wintypes.HANDLE(int(process_handle)),
            )
        )
        if not assigned:
            kernel32.CloseHandle(handle)
            return None
        return cls(handle=handle, kernel32=kernel32)

    def terminate(self) -> None:
        if not self.closed:
            self.kernel32.TerminateJobObject(self.handle, 1)

    def close(self) -> None:
        if not self.closed:
            self.kernel32.CloseHandle(self.handle)
            self.closed = True


def _subprocess_options() -> dict[str, Any]:
    if os.name == "nt":
        return {
            "creationflags": (
                subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        }
    return {"start_new_session": True}


def _fallback_terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass

    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass


def _drain_and_close_pipes(process: subprocess.Popen[str]) -> None:
    try:
        process.communicate(timeout=5)
        return
    except subprocess.TimeoutExpired:
        pass

    for stream in (process.stdout, process.stderr):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass
    try:
        process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        pass


def run_managed_command(
    args: list[str],
    *,
    timeout: int,
    cwd: str | Path | None = None,
) -> CommandResult:
    """Run an OpenCode-style CLI without leaving descendant processes behind.

    Windows npm shims can exit before their Node child. That child may keep inherited
    pipes and temporary workspace files open. A Job Object makes the process tree
    lifetime explicit and kills every descendant when the job is terminated or closed.
    """

    env = os.environ.copy()
    env.setdefault("NO_COLOR", "1")
    started = time.monotonic()
    process: subprocess.Popen[str] | None = None
    job: _WindowsJob | None = None

    try:
        process = subprocess.Popen(
            args,
            cwd=str(cwd) if cwd is not None else None,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **_subprocess_options(),
        )
        job = _WindowsJob.attach(process)
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        if process is not None:
            if job is not None:
                job.terminate()
                job.close()
                job = None
            _fallback_terminate_process_tree(process)
            _drain_and_close_pipes(process)
            time.sleep(0.1)
        raise CLIIntegrationError(
            f"The CLI did not respond within {timeout} seconds.", code="timeout"
        ) from exc
    except OSError as exc:
        if process is not None:
            _fallback_terminate_process_tree(process)
            _drain_and_close_pipes(process)
        raise CLIIntegrationError(
            f"Cannot start the CLI executable: {exc}", code="cli_unavailable"
        ) from exc
    finally:
        if job is not None:
            job.close()

    return CommandResult(
        returncode=process.returncode,
        stdout=sanitize_output(stdout),
        stderr=sanitize_output(stderr),
        elapsed_ms=round((time.monotonic() - started) * 1000),
    )
