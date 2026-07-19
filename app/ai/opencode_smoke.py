from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..config_store import ConfigStoreError
from ..paths import PathValidationError, build_runtime_paths, normalize_path
from .execution import OpenCodePromptExecutionError, OpenCodePromptExecutor
from .profiles import AIProfileStore, AIProfileStoreError
from .prompting import PromptTask
from .secrets import SecretStoreError
from .smoke import (
    SCENARIOS,
    LoadedSmokeImage,
    SmokeRunReport,
    SmokeRunnerError,
    _print_report,
    _print_scenarios,
    _write_json_report,
    evaluate_smoke_checks,
    load_smoke_image,
    scenario_by_id,
)


@dataclass(frozen=True)
class ResolvedOpenCodeProfile:
    profile: dict[str, Any]
    selected_by: str


def resolve_opencode_profile(
    store: AIProfileStore,
    *,
    selector: str | None,
    requires_image: bool,
) -> ResolvedOpenCodeProfile:
    listing = store.list()
    profiles = [
        profile
        for profile in listing["profiles"]
        if profile.get("kind") == "cli" and profile.get("cli_type") == "opencode"
    ]
    if not profiles:
        raise SmokeRunnerError(
            "No OpenCode CLI profiles are configured.",
            code="profile_not_found",
        )

    selected: dict[str, Any] | None = None
    selected_by = ""
    if selector:
        selected = next(
            (profile for profile in profiles if profile["id"] == selector),
            None,
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
                    "More than one OpenCode profile has this name; use its ID.",
                    code="ambiguous_profile",
                )
            if matches:
                selected = matches[0]
                selected_by = "explicit name"
    else:
        default_key = "multimodal_profile_id" if requires_image else "text_profile_id"
        default_id = listing["defaults"].get(default_key)
        selected = next(
            (profile for profile in profiles if profile["id"] == default_id),
            None,
        )
        selected_by = default_key

    if selected is None:
        expected = "multimodal" if requires_image else "text"
        raise SmokeRunnerError(
            f"No matching {expected} OpenCode profile was selected. "
            "Use --profile ID-or-name.",
            code="profile_not_found",
        )
    if requires_image and selected.get("multimodal") is not True:
        raise SmokeRunnerError(
            "The selected OpenCode profile is not marked as multimodal.",
            code="incompatible_profile",
        )
    return ResolvedOpenCodeProfile(
        profile=store.get(selected["id"]),
        selected_by=selected_by,
    )


def run_opencode_smoke_scenario(
    *,
    scenario_id: str,
    profile: dict[str, Any],
    user_input: str | None = None,
    image: LoadedSmokeImage | None = None,
    checkpoint_profile: str | None = None,
    timeout_seconds: int | None = None,
    executor: OpenCodePromptExecutor | None = None,
) -> SmokeRunReport:
    scenario = scenario_by_id(scenario_id)
    used_default_input = user_input is None
    effective_input = scenario.default_input if user_input is None else user_input.strip()
    if not effective_input:
        raise SmokeRunnerError(
            "Smoke scenario input cannot be empty.",
            code="invalid_input",
        )
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

    effective_profile = dict(profile)
    if timeout_seconds is not None:
        if not 5 <= timeout_seconds <= 600:
            raise SmokeRunnerError(
                "Timeout must be between 5 and 600 seconds.",
                code="invalid_timeout",
            )
        effective_profile["timeout_seconds"] = timeout_seconds

    task_payload = scenario.task.model_dump(mode="json")
    if checkpoint_profile is not None:
        task_payload["checkpoint_profile"] = checkpoint_profile.strip() or None
    task = PromptTask.model_validate(task_payload)

    execution = (executor or OpenCodePromptExecutor()).execute(
        profile=effective_profile,
        task=task,
        user_input=effective_input,
        image_path=image.path if image is not None else None,
    )
    checks = evaluate_smoke_checks(
        scenario,
        execution,
        used_default_input=used_default_input,
        image=image,
    )
    return SmokeRunReport(
        scenario=scenario,
        profile=effective_profile,
        execution=execution,  # type: ignore[arg-type]
        checks=checks,
        effective_input=effective_input,
        used_default_input=used_default_input,
        image=image,
        started_at="managed-opencode",
    )


def _print_opencode_profiles(console: Console, store: AIProfileStore) -> None:
    listing = store.list()
    defaults = listing["defaults"]
    table = Table(title=f"OpenCode profiles · {store.config.path}")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Model")
    table.add_column("Vision")
    table.add_column("Executable")
    table.add_column("Default")
    for profile in listing["profiles"]:
        if profile.get("kind") != "cli" or profile.get("cli_type") != "opencode":
            continue
        default_labels: list[str] = []
        if defaults.get("text_profile_id") == profile["id"]:
            default_labels.append("text")
        if defaults.get("multimodal_profile_id") == profile["id"]:
            default_labels.append("vision")
        table.add_row(
            profile["id"],
            profile["name"],
            profile["model"],
            "yes" if profile.get("multimodal") else "no",
            profile.get("executable") or "PATH",
            ", ".join(default_labels) or "—",
        )
    console.print(table)


def _print_header(
    console: Console,
    *,
    scenario_id: str,
    profile: dict[str, Any],
    selected_by: str,
    config_path: Path,
    image: LoadedSmokeImage | None,
) -> None:
    scenario = scenario_by_id(scenario_id)
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(style="bold cyan")
    table.add_column()
    table.add_row("Backend", "OpenCode managed CLI")
    table.add_row("Scenario", f"{scenario.scenario_id} · {scenario.title}")
    table.add_row(
        "Task",
        f"{scenario.task.family.value} / {scenario.task.operation.value} / "
        f"{scenario.task.scenario.value}",
    )
    table.add_row("Profile", f"{profile['name']} · {profile['model']} ({selected_by})")
    table.add_row("Config", str(config_path))
    table.add_row("Image", str(image.path) if image is not None else "none")
    table.add_row("Isolation", "temporary workspace · all OpenCode tools denied")
    console.print(Panel(table, title="OpenCode smoke execution", border_style="cyan"))


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
            f"Cannot read input file: {path}: {exc}",
            code="input_read_error",
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.ai.opencode_smoke",
        description="Run explicit CMV prompt scenarios through the OpenCode CLI host.",
    )
    parser.add_argument("--no-color", action="store_true", help="Disable terminal colors.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List shared CMV smoke scenarios.")

    profiles = subparsers.add_parser(
        "profiles",
        help="List configured OpenCode profiles.",
    )
    profiles.add_argument("--config", help="Override the application config.json path.")

    run = subparsers.add_parser("run", help="Run one scenario through OpenCode.")
    run.add_argument("scenario", choices=tuple(SCENARIOS))
    run.add_argument(
        "--profile",
        help="OpenCode profile ID or exact profile name. Defaults to app settings.",
    )
    run.add_argument("--config", help="Override the application config.json path.")
    input_group = run.add_mutually_exclusive_group()
    input_group.add_argument("--input", help="Override the built-in scenario input.")
    input_group.add_argument(
        "--input-file",
        help="Read the scenario input from a UTF-8 text file.",
    )
    run.add_argument("--image", help="Local image path for multimodal scenarios.")
    run.add_argument(
        "--checkpoint-profile",
        help="Attach an explicit checkpoint profile identifier.",
    )
    run.add_argument(
        "--timeout",
        type=int,
        help="Override timeout for this run only (5–600 seconds).",
    )
    run.add_argument(
        "--show-bundle",
        action="store_true",
        help="Print the full compiled instruction bundle.",
    )
    run.add_argument("--json-out", help="Write a sanitized JSON report to this path.")
    run.add_argument(
        "--debug",
        action="store_true",
        help="Print normalized technical error details.",
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
            _print_opencode_profiles(console, store)
            return 0

        scenario = scenario_by_id(args.scenario)
        user_input = _read_input(args)
        image = load_smoke_image(args.image) if args.image else None
        resolved = resolve_opencode_profile(
            store,
            selector=args.profile,
            requires_image=scenario.requires_image,
        )
        _print_header(
            console,
            scenario_id=args.scenario,
            profile=resolved.profile,
            selected_by=resolved.selected_by,
            config_path=config_path,
            image=image,
        )
        with console.status("Executing OpenCode host call…", spinner="dots"):
            report = run_opencode_smoke_scenario(
                scenario_id=args.scenario,
                profile=resolved.profile,
                user_input=user_input,
                image=image,
                checkpoint_profile=args.checkpoint_profile,
                timeout_seconds=args.timeout,
            )
        _print_report(console, report, show_bundle=args.show_bundle)
        if args.json_out:
            output_path = _write_json_report(args.json_out, report)
            console.print(f"JSON report: {output_path}")
        return 3 if report.failed else 0
    except OpenCodePromptExecutionError as exc:
        detail = f"stage={exc.stage} · code={exc.code}\n{exc}"
        if getattr(args, "debug", False) and exc.technical_error:
            detail += f"\n\nTechnical detail:\n{exc.technical_error}"
        console.print(
            Panel(Text(detail), title="OpenCode execution failed", border_style="red")
        )
        return 1
    except (
        SmokeRunnerError,
        AIProfileStoreError,
        ConfigStoreError,
        SecretStoreError,
        PathValidationError,
        OSError,
        ValueError,
    ) as exc:
        code = getattr(exc, "code", "configuration_error")
        console.print(
            Panel(
                Text(f"code={code}\n{exc}"),
                title="OpenCode smoke configuration error",
                border_style="red",
            )
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
