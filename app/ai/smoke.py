from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..config_store import ConfigStoreError
from ..paths import PathValidationError, build_runtime_paths, normalize_path
from .execution import (
    DirectPromptExecutionError,
    DirectPromptExecutionResult,
    DirectPromptExecutor,
)
from .profiles import AIProfileStore, AIProfileStoreError
from .prompting import (
    CapabilityStatus,
    PromptFamily,
    PromptModifier,
    PromptOperation,
    PromptResult,
    PromptScenario,
    PromptTask,
)
from .secrets import SecretStoreError


SmokeStatus = Literal["pass", "warn", "fail"]
_IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


@dataclass(frozen=True)
class SmokeScenario:
    scenario_id: str
    title: str
    description: str
    task: PromptTask
    default_input: str
    requires_image: bool = False
    checks: tuple[str, ...] = ("nonempty_result",)


@dataclass(frozen=True)
class SmokeCheckResult:
    check_id: str
    status: SmokeStatus
    detail: str


@dataclass(frozen=True)
class ResolvedSmokeProfile:
    profile: dict[str, Any]
    api_key: str | None
    selected_by: str


@dataclass(frozen=True)
class LoadedSmokeImage:
    path: Path
    data_url: str
    byte_count: int
    sha256: str


@dataclass(frozen=True)
class SmokeRunReport:
    scenario: SmokeScenario
    profile: dict[str, Any]
    execution: DirectPromptExecutionResult
    checks: tuple[SmokeCheckResult, ...]
    effective_input: str
    used_default_input: bool
    image: LoadedSmokeImage | None
    started_at: str

    @property
    def failed(self) -> bool:
        return any(check.status == "fail" for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        image = None
        if self.image is not None:
            image = {
                "path": str(self.image.path),
                "bytes": self.image.byte_count,
                "sha256": self.image.sha256,
            }
        return {
            "schema_version": "1",
            "started_at": self.started_at,
            "scenario": {
                "id": self.scenario.scenario_id,
                "title": self.scenario.title,
                "description": self.scenario.description,
            },
            "profile": {
                "id": self.profile.get("id"),
                "name": self.profile.get("name"),
                "kind": self.profile.get("kind"),
                "model": self.profile.get("model"),
                "base_url": self.profile.get("base_url"),
                "multimodal": self.profile.get("multimodal") is True,
            },
            "task": self.execution.bundle.task.model_dump(mode="json"),
            "input": {
                "text": self.effective_input,
                "used_default": self.used_default_input,
                "image": image,
            },
            "result": self.execution.result.model_dump(mode="json"),
            "execution": self.execution.metadata(),
            "checks": [
                {
                    "id": check.check_id,
                    "status": check.status,
                    "detail": check.detail,
                }
                for check in self.checks
            ],
            "failed": self.failed,
        }


SCENARIOS: dict[str, SmokeScenario] = {
    "flux-portrait-generate": SmokeScenario(
        scenario_id="flux-portrait-generate",
        title="FLUX portrait generation",
        description="Text-only safe portrait through the FLUX family profile.",
        task=PromptTask(
            family=PromptFamily.FLUX,
            operation=PromptOperation.GENERATE,
            scenario=PromptScenario.PORTRAIT,
            modifiers=(PromptModifier.SAFE,),
        ),
        default_input=(
            "Create a polished studio portrait of a fictional adult ceramic artist. "
            "Use a three-quarter composition, calm direct gaze, natural skin texture, "
            "charcoal work apron, warm side lighting, and a softly blurred workshop background."
        ),
        checks=("nonempty_result", "strict_schema", "safe_modifier_compiled"),
    ),
    "pony-portrait-generate": SmokeScenario(
        scenario_id="pony-portrait-generate",
        title="Pony portrait generation",
        description="Checks Pony hybrid syntax, score prefix, source and safe rating.",
        task=PromptTask(
            family=PromptFamily.PONY,
            operation=PromptOperation.GENERATE,
            scenario=PromptScenario.PORTRAIT,
            modifiers=(PromptModifier.SAFE,),
        ),
        default_input=(
            "Create a safe anime-style solo portrait of a fictional adult astronomer on an "
            "observatory balcony at night, with short silver hair, a navy coat, a gentle smile, "
            "soft moonlight, and a detailed star field."
        ),
        checks=(
            "nonempty_result",
            "strict_schema",
            "pony_complete_score_prefix",
            "pony_source_tag",
            "pony_safe_rating",
        ),
    ),
    "sdxl-graphic-text-generate": SmokeScenario(
        scenario_id="sdxl-graphic-text-generate",
        title="SDXL graphic design generation",
        description="Exercises limited typography and exact visible-text preservation.",
        task=PromptTask(
            family=PromptFamily.SDXL,
            operation=PromptOperation.GENERATE,
            scenario=PromptScenario.GRAPHIC_DESIGN_TEXT,
            modifiers=(PromptModifier.SAFE,),
        ),
        default_input=(
            "Create a minimalist science-fiction book cover. Preserve the exact title "
            '"VECTOR GARDEN". Place the title in large geometric lettering at the top, use one '
            "small subtitle line below it, a dark charcoal background, thin luminous grid lines, "
            "and a single abstract orange sphere in the lower third."
        ),
        checks=(
            "nonempty_result",
            "strict_schema",
            "limited_warning",
            "default_visible_text_preserved",
        ),
    ),
    "flux-graphic-text-reconstruct": SmokeScenario(
        scenario_id="flux-graphic-text-reconstruct",
        title="FLUX graphic design reconstruction",
        description="Real multimodal reconstruction from a user-supplied image.",
        task=PromptTask(
            family=PromptFamily.FLUX,
            operation=PromptOperation.RECONSTRUCT,
            scenario=PromptScenario.GRAPHIC_DESIGN_TEXT,
            modifiers=(PromptModifier.SAFE,),
        ),
        default_input=(
            "Reconstruct the attached image faithfully. Preserve visible text exactly when readable, "
            "describe layout and reading order, separate observed details from uncertainty, and do "
            "not invent missing copy."
        ),
        requires_image=True,
        checks=("nonempty_result", "strict_schema", "multimodal_input_used"),
    ),
}


class SmokeRunnerError(RuntimeError):
    def __init__(self, message: str, *, code: str = "smoke_error"):
        self.code = code
        super().__init__(message)


def scenario_by_id(scenario_id: str) -> SmokeScenario:
    try:
        return SCENARIOS[scenario_id]
    except KeyError as exc:
        raise SmokeRunnerError(
            f"Unknown smoke scenario: {scenario_id}", code="unknown_scenario"
        ) from exc


def resolve_smoke_profile(
    store: AIProfileStore,
    *,
    selector: str | None,
    requires_image: bool,
) -> ResolvedSmokeProfile:
    listing = store.list()
    profiles = [
        profile
        for profile in listing["profiles"]
        if profile.get("kind") == "openai_compatible"
    ]
    if not profiles:
        raise SmokeRunnerError(
            "No OpenAI-compatible profiles are configured.", code="profile_not_found"
        )

    selected: dict[str, Any] | None = None
    selected_by = ""
    if selector:
        selected = next(
            (profile for profile in profiles if profile["id"] == selector), None
        )
        if selected is not None:
            selected_by = "explicit id"
        else:
            matches = [
                profile
                for profile in profiles
                if str(profile.get("name", "")).casefold() == selector.casefold()
            ]
            if len(matches) > 1:
                raise SmokeRunnerError(
                    "More than one direct profile has this name; use its ID.",
                    code="ambiguous_profile",
                )
            if matches:
                selected = matches[0]
                selected_by = "explicit name"
    else:
        default_key = "multimodal_profile_id" if requires_image else "text_profile_id"
        default_id = listing["defaults"].get(default_key)
        selected = next(
            (profile for profile in profiles if profile["id"] == default_id), None
        )
        selected_by = default_key

    if selected is None:
        expected = "multimodal" if requires_image else "text"
        raise SmokeRunnerError(
            f"No matching {expected} direct profile was selected. Use --profile ID-or-name.",
            code="profile_not_found",
        )
    if requires_image and selected.get("multimodal") is not True:
        raise SmokeRunnerError(
            "The selected profile is not marked as multimodal.",
            code="incompatible_profile",
        )
    if selected.get("has_credentials") is False:
        detail = selected.get("credential_error") or "No credential is available."
        raise SmokeRunnerError(str(detail), code="missing_credentials")

    private_profile = store.get(selected["id"])
    try:
        api_key = store.resolve_api_key(private_profile)
    except SecretStoreError as exc:
        raise SmokeRunnerError(
            f"Cannot read the credential store: {exc}", code="credential_store_error"
        ) from exc
    return ResolvedSmokeProfile(
        profile=private_profile,
        api_key=api_key,
        selected_by=selected_by,
    )


def load_smoke_image(path_value: str | Path) -> LoadedSmokeImage:
    path = normalize_path(path_value)
    if not path.is_file():
        raise SmokeRunnerError(f"Image file does not exist: {path}", code="image_not_found")
    mime_type = _IMAGE_MIME_TYPES.get(path.suffix.lower())
    if mime_type is None:
        raise SmokeRunnerError(
            "Smoke images must be PNG, JPEG, WEBP, or GIF.",
            code="unsupported_image",
        )
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise SmokeRunnerError(
            f"Cannot read image: {path}: {exc}", code="image_read_error"
        ) from exc
    if not payload:
        raise SmokeRunnerError("The selected image is empty.", code="invalid_image")
    return LoadedSmokeImage(
        path=path,
        data_url=f"data:{mime_type};base64,{base64.b64encode(payload).decode('ascii')}",
        byte_count=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def _contains_all(text: str, values: Iterable[str]) -> bool:
    lowered = text.casefold()
    return all(value.casefold() in lowered for value in values)


def evaluate_smoke_checks(
    scenario: SmokeScenario,
    execution: DirectPromptExecutionResult,
    *,
    used_default_input: bool,
    image: LoadedSmokeImage | None,
) -> tuple[SmokeCheckResult, ...]:
    result: PromptResult = execution.result
    checks: list[SmokeCheckResult] = []
    for check_id in scenario.checks:
        status: SmokeStatus = "fail"
        detail = f"Unknown smoke check: {check_id}"
        if check_id == "nonempty_result":
            passed = bool(result.positive_prompt.strip())
            status = "pass" if passed else "fail"
            detail = "Positive prompt is non-empty." if passed else "Positive prompt is empty."
        elif check_id == "strict_schema":
            status = "pass"
            detail = (
                f"PromptResult schema_version={result.schema_version} passed Pydantic validation."
            )
        elif check_id == "safe_modifier_compiled":
            passed = PromptModifier.SAFE in execution.bundle.task.modifiers
            status = "pass" if passed else "fail"
            detail = (
                "Safe modifier is present in the compiled task."
                if passed
                else "Safe modifier is missing."
            )
        elif check_id == "pony_complete_score_prefix":
            tokens = (
                "score_9",
                "score_8_up",
                "score_7_up",
                "score_6_up",
                "score_5_up",
                "score_4_up",
            )
            passed = _contains_all(result.positive_prompt, tokens)
            status = "pass" if passed else "fail"
            detail = (
                "Complete Pony V6 XL score prefix found."
                if passed
                else "One or more Pony score tokens are missing."
            )
        elif check_id == "pony_source_tag":
            passed = any(
                token in result.positive_prompt.casefold()
                for token in (
                    "source_anime",
                    "source_cartoon",
                    "source_furry",
                    "source_pony",
                )
            )
            status = "pass" if passed else "fail"
            detail = (
                "A supported Pony source tag is present."
                if passed
                else "No supported Pony source tag was found."
            )
        elif check_id == "pony_safe_rating":
            passed = "rating_safe" in result.positive_prompt.casefold()
            status = "pass" if passed else "fail"
            detail = "rating_safe is present." if passed else "rating_safe is missing."
        elif check_id == "limited_warning":
            passed = (
                execution.bundle.capability_status is CapabilityStatus.LIMITED
                and bool(execution.bundle.warnings)
            )
            status = "pass" if passed else "fail"
            detail = (
                "Limited capability warning was compiled."
                if passed
                else "Expected limited capability warning is missing."
            )
        elif check_id == "default_visible_text_preserved":
            if not used_default_input:
                status = "warn"
                detail = (
                    "Custom input was used, so the built-in VECTOR GARDEN check was skipped."
                )
            else:
                passed = "VECTOR GARDEN" in result.positive_prompt
                status = "pass" if passed else "fail"
                detail = (
                    "Exact title VECTOR GARDEN was preserved."
                    if passed
                    else "Exact title VECTOR GARDEN was not preserved."
                )
        elif check_id == "multimodal_input_used":
            passed = image is not None
            status = "pass" if passed else "fail"
            detail = (
                "A validated local image was attached."
                if passed
                else "No image was attached."
            )
        checks.append(SmokeCheckResult(check_id, status, detail))
    return tuple(checks)


def run_smoke_scenario(
    *,
    store: AIProfileStore,
    scenario: SmokeScenario,
    selector: str | None,
    user_input: str | None = None,
    image_path: str | Path | None = None,
    checkpoint_profile: str | None = None,
    timeout_seconds: int | None = None,
    executor: DirectPromptExecutor | None = None,
    resolved_profile: ResolvedSmokeProfile | None = None,
    loaded_image: LoadedSmokeImage | None = None,
) -> SmokeRunReport:
    used_default_input = user_input is None
    effective_input = scenario.default_input if user_input is None else user_input.strip()
    if not effective_input:
        raise SmokeRunnerError("Smoke scenario input cannot be empty.", code="invalid_input")

    if loaded_image is not None and image_path is not None:
        raise SmokeRunnerError(
            "Pass either loaded_image or image_path, not both.", code="invalid_image_input"
        )
    image = loaded_image or (load_smoke_image(image_path) if image_path is not None else None)
    if scenario.requires_image and image is None:
        raise SmokeRunnerError(
            f"Scenario '{scenario.scenario_id}' requires --image PATH.",
            code="image_required",
        )
    if not scenario.requires_image and image is not None:
        raise SmokeRunnerError(
            f"Scenario '{scenario.scenario_id}' does not accept an image.",
            code="unexpected_image",
        )

    resolved = resolved_profile or resolve_smoke_profile(
        store,
        selector=selector,
        requires_image=scenario.requires_image,
    )
    profile = dict(resolved.profile)
    if timeout_seconds is not None:
        if not 5 <= timeout_seconds <= 600:
            raise SmokeRunnerError(
                "Timeout must be between 5 and 600 seconds.", code="invalid_timeout"
            )
        profile["timeout_seconds"] = timeout_seconds

    task_payload = scenario.task.model_dump(mode="json")
    if checkpoint_profile is not None:
        task_payload["checkpoint_profile"] = checkpoint_profile.strip() or None
    task = PromptTask.model_validate(task_payload)

    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    execution = (executor or DirectPromptExecutor()).execute(
        profile=profile,
        api_key=resolved.api_key,
        task=task,
        user_input=effective_input,
        image_data_url=image.data_url if image is not None else None,
    )
    checks = evaluate_smoke_checks(
        scenario,
        execution,
        used_default_input=used_default_input,
        image=image,
    )
    return SmokeRunReport(
        scenario=scenario,
        profile=profile,
        execution=execution,
        checks=checks,
        effective_input=effective_input,
        used_default_input=used_default_input,
        image=image,
        started_at=started_at,
    )


def _status_style(status: SmokeStatus) -> str:
    return {"pass": "bold green", "warn": "bold yellow", "fail": "bold red"}[status]


def _print_scenarios(console: Console) -> None:
    table = Table(title="Real-provider smoke scenarios")
    table.add_column("ID", style="bold cyan", no_wrap=True)
    table.add_column("Family")
    table.add_column("Operation")
    table.add_column("Scenario")
    table.add_column("Input")
    table.add_column("Purpose")
    for scenario in SCENARIOS.values():
        table.add_row(
            scenario.scenario_id,
            scenario.task.family.value,
            scenario.task.operation.value,
            scenario.task.scenario.value,
            "image + text" if scenario.requires_image else "text",
            scenario.description,
        )
    console.print(table)


def _print_profiles(console: Console, store: AIProfileStore) -> None:
    listing = store.list()
    defaults = listing["defaults"]
    table = Table(title=f"AI profiles · {store.config.path}")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Kind")
    table.add_column("Model")
    table.add_column("Vision")
    table.add_column("Credentials")
    table.add_column("Default")
    for profile in listing["profiles"]:
        default_labels: list[str] = []
        if defaults.get("text_profile_id") == profile["id"]:
            default_labels.append("text")
        if defaults.get("multimodal_profile_id") == profile["id"]:
            default_labels.append("vision")
        table.add_row(
            profile["id"],
            profile["name"],
            profile["kind"],
            profile["model"],
            "yes" if profile.get("multimodal") else "no",
            "available" if profile.get("has_credentials", True) else "missing",
            ", ".join(default_labels) or "—",
        )
    console.print(table)
    secret_status = listing.get("secret_store", {})
    console.print(
        f"Secret store: {secret_status.get('backend') or 'unavailable'} · "
        f"{secret_status.get('message') or 'no status message'}"
    )


def _print_run_header(
    console: Console,
    *,
    scenario: SmokeScenario,
    profile: dict[str, Any],
    selected_by: str,
    config_path: Path,
    image: LoadedSmokeImage | None,
) -> None:
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(style="bold cyan")
    table.add_column()
    table.add_row("Scenario", f"{scenario.scenario_id} · {scenario.title}")
    table.add_row(
        "Task",
        f"{scenario.task.family.value} / {scenario.task.operation.value} / "
        f"{scenario.task.scenario.value}",
    )
    table.add_row("Profile", f"{profile['name']} · {profile['model']} ({selected_by})")
    table.add_row("Config", str(config_path))
    table.add_row("Image", str(image.path) if image is not None else "none")
    console.print(Panel(table, title="Smoke execution", border_style="cyan"))


def _print_report(console: Console, report: SmokeRunReport, *, show_bundle: bool) -> None:
    console.print(Panel(Text(report.effective_input), title="Input", border_style="blue"))

    result_table = Table(title="Normalized PromptResult", show_header=False)
    result_table.add_column("Field", style="bold cyan", no_wrap=True)
    result_table.add_column("Value", overflow="fold")
    result_table.add_row("schema_version", report.execution.result.schema_version)
    result_table.add_row("positive_prompt", report.execution.result.positive_prompt)
    result_table.add_row(
        "negative_prompt", report.execution.result.negative_prompt or "<empty>"
    )
    console.print(result_table)

    section_table = Table(title="Compiled instruction sections")
    section_table.add_column("Kind")
    section_table.add_column("ID")
    section_table.add_column("Version")
    section_table.add_column("SHA-256")
    for section in report.execution.metadata()["bundle"]["sections"]:
        section_table.add_row(
            section["kind"],
            section["section_id"],
            section["version"],
            section["content_sha256"][:16],
        )
    console.print(section_table)

    check_table = Table(title="Scenario checks")
    check_table.add_column("Status")
    check_table.add_column("Check")
    check_table.add_column("Detail")
    for check in report.checks:
        check_table.add_row(
            Text(check.status.upper(), style=_status_style(check.status)),
            check.check_id,
            check.detail,
        )
    console.print(check_table)

    summary = Table(show_header=False, box=None)
    summary.add_column(style="bold cyan")
    summary.add_column()
    summary.add_row("Latency", f"{report.execution.latency_ms} ms")
    summary.add_row("Raw response SHA-256", report.execution.raw_response_sha256)
    summary.add_row("Capability", report.execution.bundle.capability_status.value)
    summary.add_row("Warnings", str(len(report.execution.bundle.warnings)))
    summary.add_row("Result", "FAILED" if report.failed else "PASSED")
    console.print(
        Panel(
            summary,
            title="Summary",
            border_style="red" if report.failed else "green",
        )
    )

    if show_bundle:
        console.print(
            Panel(
                Text(report.execution.bundle.render()),
                title="Full InstructionBundle",
                border_style="magenta",
            )
        )


def _read_input(args: argparse.Namespace) -> str | None:
    if args.input is not None:
        return args.input
    if args.input_file is None:
        return None
    path = normalize_path(args.input_file)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SmokeRunnerError(
            f"Cannot read input file: {path}: {exc}", code="input_read_error"
        ) from exc


def _write_json_report(path_value: str, report: SmokeRunReport) -> Path:
    path = normalize_path(path_value)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise SmokeRunnerError(
            f"Cannot write JSON report: {path}: {exc}", code="report_write_error"
        ) from exc
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.ai.smoke",
        description="Run explicit real-provider AI smoke scenarios with Rich output.",
    )
    parser.add_argument("--no-color", action="store_true", help="Disable terminal colors.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List built-in smoke scenarios.")

    profiles = subparsers.add_parser(
        "profiles", help="List configured AI profiles without secrets."
    )
    profiles.add_argument("--config", help="Override the application config.json path.")

    run = subparsers.add_parser("run", help="Run one real-provider scenario.")
    run.add_argument("scenario", choices=tuple(SCENARIOS))
    run.add_argument(
        "--profile",
        help="Direct profile ID or exact profile name. Defaults to app settings.",
    )
    run.add_argument("--config", help="Override the application config.json path.")
    input_group = run.add_mutually_exclusive_group()
    input_group.add_argument("--input", help="Override the built-in scenario input.")
    input_group.add_argument(
        "--input-file", help="Read the scenario input from a UTF-8 text file."
    )
    run.add_argument("--image", help="Local image path for multimodal scenarios.")
    run.add_argument(
        "--checkpoint-profile", help="Attach an explicit checkpoint profile identifier."
    )
    run.add_argument(
        "--timeout", type=int, help="Override timeout for this run only (5–600 seconds)."
    )
    run.add_argument(
        "--show-bundle", action="store_true", help="Print the full instruction bundle."
    )
    run.add_argument("--json-out", help="Write a sanitized JSON report to this path.")
    run.add_argument(
        "--debug", action="store_true", help="Print normalized technical error details."
    )
    return parser


def _config_path(value: str | None) -> Path:
    return normalize_path(value) if value else build_runtime_paths().config


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    console = Console(no_color=args.no_color)

    if args.command == "list":
        _print_scenarios(console)
        return 0

    try:
        config_path = _config_path(getattr(args, "config", None))
        store = AIProfileStore(config_path)
        if args.command == "profiles":
            _print_profiles(console, store)
            return 0

        scenario = scenario_by_id(args.scenario)
        user_input = _read_input(args)
        image = load_smoke_image(args.image) if args.image else None
        resolved = resolve_smoke_profile(
            store,
            selector=args.profile,
            requires_image=scenario.requires_image,
        )
        _print_run_header(
            console,
            scenario=scenario,
            profile=resolved.profile,
            selected_by=resolved.selected_by,
            config_path=config_path,
            image=image,
        )
        with console.status("Executing real provider call…", spinner="dots"):
            report = run_smoke_scenario(
                store=store,
                scenario=scenario,
                selector=args.profile,
                user_input=user_input,
                checkpoint_profile=args.checkpoint_profile,
                timeout_seconds=args.timeout,
                resolved_profile=resolved,
                loaded_image=image,
            )
        _print_report(console, report, show_bundle=args.show_bundle)
        if args.json_out:
            output_path = _write_json_report(args.json_out, report)
            console.print(f"JSON report: {output_path}")
        return 3 if report.failed else 0
    except DirectPromptExecutionError as exc:
        detail = f"stage={exc.stage} · code={exc.code}\n{exc}"
        if getattr(args, "debug", False) and exc.technical_error:
            detail += f"\n\nTechnical detail:\n{exc.technical_error}"
        console.print(
            Panel(Text(detail), title="Execution failed", border_style="red")
        )
        return 1
    except (
        SmokeRunnerError,
        AIProfileStoreError,
        ConfigStoreError,
        SecretStoreError,
        PathValidationError,
        OSError,
    ) as exc:
        code = getattr(exc, "code", "configuration_error")
        console.print(
            Panel(
                Text(f"code={code}\n{exc}"),
                title="Smoke configuration error",
                border_style="red",
            )
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
