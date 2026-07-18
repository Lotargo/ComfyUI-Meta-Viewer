from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)(\S+)"),
    re.compile(r"(?i)((?:api[_-]?key|access[_-]?token|password)\s*[:=]\s*)(\S+)"),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{8,})\b"),
)


CLI_SPECS: dict[str, dict[str, Any]] = {
    "opencode": {
        "label": "OpenCode",
        "commands": ("opencode",),
        "version_args": ("--version",),
        "auth_args": ("auth", "list"),
        "models_args": ("models",),
        "multimodal": True,
        "experimental": False,
    },
    "claude": {
        "label": "Claude Code",
        "commands": ("claude",),
        "version_args": ("--version",),
        "auth_args": ("auth", "status"),
        "models_args": None,
        "multimodal": False,
        "experimental": False,
    },
    "antigravity": {
        "label": "Antigravity CLI",
        "commands": ("agy", "antigravity"),
        "version_args": ("--help",),
        "auth_args": None,
        "models_args": ("models",),
        "multimodal": False,
        "experimental": True,
    },
}


class CLIIntegrationError(RuntimeError):
    def __init__(self, message: str, *, code: str = "cli_error"):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: int


def sanitize_output(value: str, *, maximum: int = 16_000) -> str:
    text = ANSI_RE.sub("", value).replace("\x00", "")
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 2:
            text = pattern.sub(r"\1[redacted]", text)
        else:
            text = pattern.sub("[redacted]", text)
    return text.strip()[:maximum]


def _subprocess_options() -> dict[str, Any]:
    options: dict[str, Any] = {}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    return options


def run_command(
    args: list[str],
    *,
    timeout: int,
    cwd: str | Path | None = None,
) -> CommandResult:
    env = os.environ.copy()
    env.setdefault("NO_COLOR", "1")
    started = time.monotonic()
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd is not None else None,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            **_subprocess_options(),
        )
    except subprocess.TimeoutExpired as exc:
        raise CLIIntegrationError(
            f"The CLI did not respond within {timeout} seconds.", code="timeout"
        ) from exc
    except OSError as exc:
        raise CLIIntegrationError(
            f"Cannot start the CLI executable: {exc}", code="cli_unavailable"
        ) from exc
    return CommandResult(
        returncode=completed.returncode,
        stdout=sanitize_output(completed.stdout),
        stderr=sanitize_output(completed.stderr),
        elapsed_ms=round((time.monotonic() - started) * 1000),
    )


def find_executable(cli_type: str, requested: str | None = None) -> str | None:
    if cli_type not in CLI_SPECS:
        return None
    if requested:
        candidate = Path(requested).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
    for command in CLI_SPECS[cli_type]["commands"]:
        found = shutil.which(command)
        if found:
            return str(Path(found).resolve())
    return None


def _version_text(cli_type: str, result: CommandResult) -> str | None:
    output = result.stdout or result.stderr
    if not output:
        return None
    first_line = output.splitlines()[0].strip()
    if cli_type == "antigravity" and first_line.lower().startswith("usage"):
        return None
    return first_line[:200]


def _authentication_status(cli_type: str, executable: str) -> dict[str, Any]:
    auth_args = CLI_SPECS[cli_type]["auth_args"]
    if auth_args is None:
        return {
            "status": "unknown",
            "message": "This CLI has no documented non-interactive auth status command.",
        }
    try:
        result = run_command([executable, *auth_args], timeout=12)
    except CLIIntegrationError as exc:
        return {"status": "unknown", "message": str(exc)}
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    if cli_type == "opencode":
        match = re.search(r"\b([0-9]+)\s+credentials?\b", output, re.IGNORECASE)
        environment_section = (
            output.split("Environment", 1)[1] if "Environment" in output else ""
        )
        has_environment_credentials = any(
            line.strip().startswith("•")
            for line in environment_section.splitlines()
        )
        if result.returncode == 0 and (
            (match and int(match.group(1)) > 0) or has_environment_credentials
        ):
            return {
                "status": "available",
                "message": "OpenCode reports configured provider credentials.",
            }
        return {
            "status": "missing",
            "message": "OpenCode is installed but has no configured credentials.",
        }
    if result.returncode == 0:
        return {
            "status": "available",
            "message": "Claude Code reports an active authenticated session.",
        }
    detail = output.splitlines()[-1] if output else "Authentication check failed."
    return {"status": "error", "message": detail[:500]}


def probe_cli(cli_type: str) -> dict[str, Any]:
    spec = CLI_SPECS[cli_type]
    executable = find_executable(cli_type)
    result: dict[str, Any] = {
        "type": cli_type,
        "label": spec["label"],
        "installed": executable is not None,
        "executable": executable,
        "version": None,
        "authentication": {
            "status": "unavailable",
            "message": "CLI executable was not found in PATH.",
        },
        "multimodal": spec["multimodal"],
        "experimental": spec["experimental"],
        "model_discovery": spec["models_args"] is not None,
    }
    if executable is None:
        return result
    with ThreadPoolExecutor(max_workers=2) as executor:
        version_future = executor.submit(
            run_command, [executable, *spec["version_args"]], timeout=4
        )
        auth_future = executor.submit(
            _authentication_status, cli_type, executable
        )
        try:
            result["version"] = _version_text(cli_type, version_future.result())
        except CLIIntegrationError as exc:
            result["probe_error"] = str(exc)
        result["authentication"] = auth_future.result()
    return result


def discover_cli_integrations() -> list[dict[str, Any]]:
    cli_types = tuple(CLI_SPECS)
    with ThreadPoolExecutor(max_workers=len(cli_types)) as executor:
        found = list(executor.map(probe_cli, cli_types))
    return found


def list_cli_models(cli_type: str, executable: str | None = None) -> dict[str, Any]:
    if cli_type not in CLI_SPECS:
        raise CLIIntegrationError("Unsupported CLI integration.")
    spec = CLI_SPECS[cli_type]
    executable = find_executable(cli_type, executable)
    if executable is None:
        raise CLIIntegrationError(
            f"{spec['label']} was not found in PATH.", code="cli_unavailable"
        )
    model_args = spec["models_args"]
    if model_args is None:
        return {
            "models": [],
            "source": "manual",
            "message": "Enter a Claude model ID or supported alias manually.",
        }
    result = run_command([executable, *model_args], timeout=30)
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    if result.returncode != 0:
        raise CLIIntegrationError(
            output or "The CLI could not list models.", code="cli_authentication"
        )
    models: list[str] = []
    for line in output.splitlines():
        value = line.strip().lstrip("-*•│| ").strip()
        if not value or len(value) > 300:
            continue
        if cli_type == "opencode" and not re.fullmatch(r"[^\s/]+/[^\s]+", value):
            continue
        if cli_type == "antigravity" and value.lower().startswith(("available", "model")):
            continue
        if value not in models:
            models.append(value)
        if len(models) >= 5_000:
            break
    return {"models": models, "source": "cli", "message": None}


def _parse_cli_response(cli_type: str, output: str) -> str:
    if cli_type == "claude":
        try:
            payload = json.loads(output)
            result = payload.get("result")
            if isinstance(result, str):
                return result.strip()
        except (json.JSONDecodeError, AttributeError):
            pass
    if cli_type == "opencode":
        text_parts: list[str] = []
        for line in output.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            candidates = (
                event.get("text"),
                event.get("part", {}).get("text")
                if isinstance(event.get("part"), dict)
                else None,
            )
            text_parts.extend(item for item in candidates if isinstance(item, str))
        if text_parts:
            return "".join(text_parts).strip()
    return output.strip()


def run_cli_test(profile: dict[str, Any], *, multimodal: bool = False) -> dict[str, Any]:
    cli_type = profile["cli_type"]
    spec = CLI_SPECS[cli_type]
    executable = find_executable(cli_type, profile.get("executable"))
    if executable is None:
        raise CLIIntegrationError(
            f"{spec['label']} was not found in PATH.", code="cli_unavailable"
        )
    if multimodal and not spec["multimodal"]:
        raise CLIIntegrationError(
            f"The {spec['label']} adapter does not yet expose a documented image input.",
            code="incompatible_format",
        )

    prompt = "Reply with exactly CMV_OK and no other text. Do not use tools."
    temporary_directory: tempfile.TemporaryDirectory[str] | None = None
    if cli_type == "opencode":
        file_args: list[str] = []
        if multimodal:
            temporary_directory = tempfile.TemporaryDirectory(
                prefix="cmv-ai-test-"
            )
            image_path = Path(temporary_directory.name) / "test.png"
            image_path.write_bytes(base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElE"
                "QVR42mOQaMgDAAG6AQf4Lfx6AAAAAElFTkSuQmCC"
            ))
            file_args = ["--file", str(image_path)]
        args = [
            executable,
            "--pure",
            "run",
            "--model",
            profile["model"],
            "--format",
            "json",
            "--agent",
            "plan",
            "--title",
            "ComfyUI Meta Viewer connection test",
            *file_args,
            prompt,
        ]
    elif cli_type == "claude":
        args = [
            executable,
            "--print",
            prompt,
            "--output-format",
            "json",
            "--model",
            profile["model"],
            "--max-turns",
            "1",
            "--disallowedTools",
            "*",
        ]
    else:
        args = [
            executable,
            "--print",
            prompt,
            "--model",
            profile["model"],
            "--print-timeout",
            f"{profile['timeout_seconds']}s",
            "--sandbox",
        ]
    try:
        result = run_command(args, timeout=profile["timeout_seconds"])
    finally:
        if temporary_directory is not None:
            temporary_directory.cleanup()
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    if result.returncode != 0:
        lowered = output.lower()
        code = (
            "cli_authentication"
            if any(word in lowered for word in ("auth", "login", "credential", "access"))
            else "provider_error"
        )
        raise CLIIntegrationError(output or "CLI request failed.", code=code)
    response = _parse_cli_response(cli_type, result.stdout)
    if not response:
        raise CLIIntegrationError(
            "The CLI returned no text response.", code="incompatible_format"
        )
    return {
        "ok": True,
        "transport": "cli",
        "latency_ms": result.elapsed_ms,
        "response_preview": response[:500],
    }
