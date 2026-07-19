from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..config_store import ConfigStoreError
from ..paths import PathValidationError, build_runtime_paths, normalize_path
from .execution import OpenCodePromptExecutionError, OpenCodePromptExecutor
from .opencode_smoke import resolve_opencode_profile
from .profiles import AIProfileStore, AIProfileStoreError
from .prompting import (
    PromptFamily,
    PromptModifier,
    PromptOperation,
    PromptResult,
    PromptScenario,
    PromptTask,
)
from .secrets import SecretStoreError
from .smoke import SmokeRunnerError


QualityStatus = Literal["pass", "warn", "fail"]
_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
_SENTENCE_RE = re.compile(r"[.!?](?:\s|$)")


@dataclass(frozen=True)
class QualityBenchmark:
    benchmark_id: str
    title: str
    description: str
    task: PromptTask
    input_text: str
    min_words: int
    max_words: int
    coverage_groups: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class QualityMetric:
    metric_id: str
    status: QualityStatus
    points: int
    maximum: int
    detail: str


@dataclass(frozen=True)
class QualityReport:
    benchmark: QualityBenchmark
    profile: dict[str, Any]
    result: PromptResult
    metrics: tuple[QualityMetric, ...]
    latency_ms: int
    raw_response_sha256: str
    bundle_metadata: dict[str, Any]

    @property
    def score(self) -> int:
        return sum(metric.points for metric in self.metrics)

    @property
    def maximum(self) -> int:
        return sum(metric.maximum for metric in self.metrics)

    @property
    def percentage(self) -> int:
        if self.maximum == 0:
            return 0
        return round(self.score * 100 / self.maximum)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1",
            "benchmark": {
                "id": self.benchmark.benchmark_id,
                "title": self.benchmark.title,
                "description": self.benchmark.description,
            },
            "profile": {
                "id": self.profile.get("id"),
                "name": self.profile.get("name"),
                "kind": self.profile.get("kind"),
                "cli_type": self.profile.get("cli_type"),
                "model": self.profile.get("model"),
            },
            "result": self.result.model_dump(mode="json"),
            "score": self.score,
            "maximum": self.maximum,
            "percentage": self.percentage,
            "metrics": [
                {
                    "id": metric.metric_id,
                    "status": metric.status,
                    "points": metric.points,
                    "maximum": metric.maximum,
                    "detail": metric.detail,
                }
                for metric in self.metrics
            ],
            "execution": {
                "transport": "opencode",
                "latency_ms": self.latency_ms,
                "raw_response_sha256": self.raw_response_sha256,
                "bundle": self.bundle_metadata,
            },
        }


BENCHMARKS: dict[str, QualityBenchmark] = {
    "flux-portrait-detailed": QualityBenchmark(
        benchmark_id="flux-portrait-detailed",
        title="Detailed FLUX environmental portrait",
        description=(
            "Measures whether the model preserves and organises a production-level portrait brief "
            "instead of merely paraphrasing its subject."
        ),
        task=PromptTask(
            family=PromptFamily.FLUX,
            operation=PromptOperation.GENERATE,
            scenario=PromptScenario.PORTRAIT,
            modifiers=(PromptModifier.SAFE,),
            checkpoint_profile="flux-quality-benchmark-v1",
        ),
        input_text=(
            "Create an editorial environmental portrait of a fictional adult ceramic artist inside "
            "a working pottery studio. Use an eye-level medium close-up with an 85 mm portrait-lens "
            "look. Turn the subject's shoulders slightly away from the camera while keeping calm direct "
            "eye contact. Show fine natural skin texture, a few loose dark hair strands, a charcoal linen "
            "apron dusted with pale clay, and both hands holding an unfinished matte ceramic cup at chest "
            "height. Place a softly blurred shelf edge in the foreground, the artist in the midground, and "
            "kiln shelves with bowls and tools in the background. Warm diffused key light should enter from "
            "high camera-left, with a restrained cool fill on the shadow side and a subtle amber rim from the "
            "kiln area. Use shallow depth of field, realistic material response, restrained earth tones, and "
            "high-end editorial photography without generic quality slogans."
        ),
        min_words=95,
        max_words=170,
        coverage_groups={
            "subject_identity": ("ceramic artist", "potter", "pottery artist"),
            "expression_and_pose": (
                "direct eye contact",
                "direct gaze",
                "calm gaze",
                "shoulders",
                "shoulder turn",
            ),
            "camera_and_crop": (
                "85 mm",
                "85mm",
                "portrait-lens",
                "portrait lens",
                "medium close-up",
                "eye-level",
                "eye level",
            ),
            "foreground_midground_background": (
                "foreground",
                "midground",
                "background",
                "shelf edge",
                "kiln shelves",
            ),
            "lighting_layers": (
                "key light",
                "fill",
                "rim",
                "camera-left",
                "camera left",
                "shadow side",
            ),
            "materials_and_texture": (
                "skin texture",
                "linen apron",
                "clay dust",
                "matte ceramic",
                "material response",
            ),
            "hands_and_object": (
                "both hands",
                "unfinished",
                "ceramic cup",
                "chest height",
            ),
            "depth_and_medium": (
                "shallow depth of field",
                "editorial photography",
                "editorial photograph",
                "earth tones",
                "softly blurred",
            ),
        },
    ),
}

_GENERIC_BUZZWORDS = (
    "masterpiece",
    "best quality",
    "8k",
    "uhd",
    "award-winning",
    "stunning",
    "perfect face",
)


def evaluate_prompt_quality(
    benchmark: QualityBenchmark,
    result: PromptResult,
) -> tuple[QualityMetric, ...]:
    prompt = result.positive_prompt.strip()
    word_count = len(_WORD_RE.findall(prompt))
    metrics: list[QualityMetric] = []

    if benchmark.min_words <= word_count <= benchmark.max_words:
        metrics.append(QualityMetric(
            "word_budget", "pass", 15, 15,
            f"{word_count} words; expected {benchmark.min_words}-{benchmark.max_words}.",
        ))
    elif word_count > benchmark.max_words:
        metrics.append(QualityMetric(
            "word_budget", "warn", 8, 15,
            f"{word_count} words; detailed but above the benchmark maximum of {benchmark.max_words}.",
        ))
    elif word_count >= round(benchmark.min_words * 0.75):
        metrics.append(QualityMetric(
            "word_budget", "warn", 8, 15,
            f"{word_count} words; usable but below the detailed benchmark minimum of {benchmark.min_words}.",
        ))
    else:
        metrics.append(QualityMetric(
            "word_budget", "fail", 0, 15,
            f"{word_count} words; too shallow for this detailed benchmark.",
        ))

    for group_id, markers in benchmark.coverage_groups.items():
        found = [marker for marker in markers if marker.casefold() in prompt.casefold()]
        metrics.append(QualityMetric(
            f"coverage:{group_id}",
            "pass" if found else "fail",
            8 if found else 0,
            8,
            "Covered by: " + ", ".join(found[:3])
            if found else "No concrete wording found for this visual dimension.",
        ))

    metrics.append(QualityMetric(
        "flux_negative_policy",
        "pass" if result.negative_prompt == "" else "fail",
        10 if result.negative_prompt == "" else 0,
        10,
        "FLUX negative_prompt is correctly empty."
        if result.negative_prompt == "" else "FLUX benchmark expects an empty negative_prompt.",
    ))

    buzzwords = [word for word in _GENERIC_BUZZWORDS if word in prompt.casefold()]
    metrics.append(QualityMetric(
        "concrete_language",
        "pass" if not buzzwords else "fail",
        6 if not buzzwords else 0,
        6,
        "No generic quality slogans found."
        if not buzzwords else "Generic quality slogans found: " + ", ".join(buzzwords),
    ))

    sentence_count = len(_SENTENCE_RE.findall(prompt))
    if sentence_count >= 3:
        metrics.append(QualityMetric(
            "coherent_development", "pass", 5, 5,
            f"{sentence_count} developed sentences found.",
        ))
    elif sentence_count == 2:
        metrics.append(QualityMetric(
            "coherent_development", "warn", 3, 5,
            "Only two sentences; the prompt may still be compressed.",
        ))
    else:
        metrics.append(QualityMetric(
            "coherent_development", "fail", 0, 5,
            "The prompt is not developed into multiple coherent sentences.",
        ))
    return tuple(metrics)


def quality_status(report: QualityReport, minimum_score: int) -> QualityStatus:
    if report.percentage >= minimum_score:
        return "pass"
    if report.percentage >= max(0, minimum_score - 15):
        return "warn"
    return "fail"


def run_benchmark(
    *,
    benchmark: QualityBenchmark,
    profile: dict[str, Any],
    executor: OpenCodePromptExecutor | None = None,
) -> QualityReport:
    execution = (executor or OpenCodePromptExecutor()).execute(
        profile=profile,
        task=benchmark.task,
        user_input=benchmark.input_text,
    )
    return QualityReport(
        benchmark=benchmark,
        profile=profile,
        result=execution.result,
        metrics=evaluate_prompt_quality(benchmark, execution.result),
        latency_ms=execution.latency_ms,
        raw_response_sha256=execution.raw_response_sha256,
        bundle_metadata=execution.bundle.metadata(),
    )


def _status_style(status: QualityStatus) -> str:
    return {"pass": "bold green", "warn": "bold yellow", "fail": "bold red"}[status]


def _print_benchmarks(console: Console) -> None:
    table = Table(title="OpenCode prompt quality benchmarks")
    table.add_column("ID", style="bold cyan")
    table.add_column("Family")
    table.add_column("Scenario")
    table.add_column("Purpose")
    for benchmark in BENCHMARKS.values():
        table.add_row(
            benchmark.benchmark_id,
            benchmark.task.family.value,
            benchmark.task.scenario.value,
            benchmark.description,
        )
    console.print(table)


def _print_report(
    console: Console,
    report: QualityReport,
    *,
    minimum_score: int,
    show_bundle: bool,
) -> None:
    console.print(Panel(
        Text(report.benchmark.input_text),
        title="Detailed benchmark input",
        border_style="blue",
    ))

    result_table = Table(title="Normalized PromptResult", show_header=False)
    result_table.add_column("Field", style="bold cyan", no_wrap=True)
    result_table.add_column("Value", overflow="fold")
    result_table.add_row("positive_prompt", report.result.positive_prompt)
    result_table.add_row("negative_prompt", report.result.negative_prompt or "<empty>")
    console.print(result_table)

    metric_table = Table(title="Quality metrics")
    metric_table.add_column("Status")
    metric_table.add_column("Metric")
    metric_table.add_column("Points")
    metric_table.add_column("Detail")
    for metric in report.metrics:
        metric_table.add_row(
            Text(metric.status.upper(), style=_status_style(metric.status)),
            metric.metric_id,
            f"{metric.points}/{metric.maximum}",
            metric.detail,
        )
    console.print(metric_table)

    status = quality_status(report, minimum_score)
    summary = Table(show_header=False, box=None)
    summary.add_column(style="bold cyan")
    summary.add_column()
    summary.add_row("Score", f"{report.score}/{report.maximum} ({report.percentage}%)")
    summary.add_row("Minimum", f"{minimum_score}%")
    summary.add_row("Latency", f"{report.latency_ms} ms")
    summary.add_row("Raw response SHA-256", report.raw_response_sha256)
    summary.add_row("Result", status.upper())
    console.print(Panel(
        summary,
        title="Prompt quality summary",
        border_style={"pass": "green", "warn": "yellow", "fail": "red"}[status],
    ))

    if show_bundle:
        from .prompting import PromptCompiler

        bundle = PromptCompiler().compile(report.benchmark.task)
        console.print(Panel(
            Text(bundle.render()),
            title="Full InstructionBundle",
            border_style="magenta",
        ))


def _write_json(path_value: str, report: QualityReport) -> Path:
    path = normalize_path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.ai.quality_benchmark",
        description="Evaluate prompt depth through a real OpenCode model call.",
    )
    parser.add_argument("--no-color", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List quality benchmarks.")

    run = subparsers.add_parser("run", help="Run one quality benchmark through OpenCode.")
    run.add_argument("benchmark", choices=tuple(BENCHMARKS))
    run.add_argument("--profile", help="OpenCode profile ID or exact profile name.")
    run.add_argument("--config", help="Override the application config.json path.")
    run.add_argument("--minimum-score", type=int, default=85)
    run.add_argument("--timeout", type=int)
    run.add_argument("--show-bundle", action="store_true")
    run.add_argument("--json-out")
    run.add_argument("--debug", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    console = Console(no_color=args.no_color)
    if args.command == "list":
        _print_benchmarks(console)
        return 0

    try:
        if not 0 <= args.minimum_score <= 100:
            raise SmokeRunnerError(
                "Minimum score must be between 0 and 100.",
                code="invalid_minimum_score",
            )
        config_path = normalize_path(args.config) if args.config else build_runtime_paths().config
        store = AIProfileStore(config_path)
        resolved = resolve_opencode_profile(
            store,
            selector=args.profile,
            requires_image=False,
        )
        profile = dict(resolved.profile)
        if args.timeout is not None:
            if not 5 <= args.timeout <= 600:
                raise SmokeRunnerError(
                    "Timeout must be between 5 and 600 seconds.",
                    code="invalid_timeout",
                )
            profile["timeout_seconds"] = args.timeout

        benchmark = BENCHMARKS[args.benchmark]
        header = Table(show_header=False, box=None)
        header.add_column(style="bold cyan")
        header.add_column()
        header.add_row("Benchmark", f"{benchmark.benchmark_id} · {benchmark.title}")
        header.add_row("Profile", f"{profile['name']} · {profile['model']}")
        header.add_row("Backend", "OpenCode managed CLI")
        header.add_row("Minimum score", f"{args.minimum_score}%")
        console.print(Panel(header, title="Prompt quality benchmark", border_style="cyan"))

        with console.status("Executing quality benchmark…", spinner="dots"):
            report = run_benchmark(benchmark=benchmark, profile=profile)
        _print_report(
            console,
            report,
            minimum_score=args.minimum_score,
            show_bundle=args.show_bundle,
        )
        if args.json_out:
            console.print(f"JSON report: {_write_json(args.json_out, report)}")
        return 0 if quality_status(report, args.minimum_score) == "pass" else 3
    except OpenCodePromptExecutionError as exc:
        detail = f"stage={exc.stage} · code={exc.code}\n{exc}"
        if args.debug and exc.technical_error:
            detail += f"\n\nTechnical detail:\n{exc.technical_error}"
        console.print(Panel(Text(detail), title="Benchmark execution failed", border_style="red"))
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
        console.print(Panel(
            Text(f"code={code}\n{exc}"),
            title="Benchmark configuration error",
            border_style="red",
        ))
        return 2


if __name__ == "__main__":
    sys.exit(main())
