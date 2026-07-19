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
from .execution import (
    OpenCodeIntentJudgeExecutionError,
    OpenCodeIntentJudgeExecutionResult,
    OpenCodeIntentJudgeExecutor,
    OpenCodePromptExecutionError,
    OpenCodePromptExecutionResult,
    OpenCodePromptExecutor,
)
from .judging import IntentJudgeResult
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


IntentStatus = Literal["pass", "warn", "fail"]
_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-'][A-Za-zА-Яа-яЁё0-9]+)*")
_SENTENCE_RE = re.compile(r"[.!?](?:\s|$)")

_GENERIC_BUZZWORDS = (
    "masterpiece",
    "best quality",
    "8k",
    "uhd",
    "award-winning",
    "stunning",
    "perfect face",
    "ultra detailed",
)


@dataclass(frozen=True)
class IntentBenchmark:
    benchmark_id: str
    title: str
    description: str
    task: PromptTask
    input_text: str


@dataclass(frozen=True)
class IntentHeuristicMetric:
    metric_id: str
    status: IntentStatus
    points: int
    maximum: int
    detail: str


@dataclass(frozen=True)
class IntentBenchmarkReport:
    benchmark: IntentBenchmark
    generator_profile: dict[str, Any]
    judge_profile: dict[str, Any]
    generation: OpenCodePromptExecutionResult
    judge: OpenCodeIntentJudgeExecutionResult
    heuristic_metrics: tuple[IntentHeuristicMetric, ...]

    @property
    def heuristic_score(self) -> int:
        return sum(metric.points for metric in self.heuristic_metrics)

    @property
    def heuristic_maximum(self) -> int:
        return sum(metric.maximum for metric in self.heuristic_metrics)

    @property
    def heuristic_percentage(self) -> int:
        if self.heuristic_maximum == 0:
            return 0
        return round(self.heuristic_score * 100 / self.heuristic_maximum)

    @property
    def judge_score(self) -> int:
        return self.judge.result.total

    @property
    def combined_score(self) -> int:
        # The same model may be biased toward its own answer, so the judge is not
        # allowed to outweigh deterministic checks in the free baseline.
        return round((self.heuristic_percentage + self.judge_score) / 2)

    @property
    def score_gap(self) -> int:
        return abs(self.heuristic_percentage - self.judge_score)

    @property
    def same_model_judge(self) -> bool:
        return (
            self.generator_profile.get("id") == self.judge_profile.get("id")
            and self.generator_profile.get("model") == self.judge_profile.get("model")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1",
            "benchmark": {
                "id": self.benchmark.benchmark_id,
                "title": self.benchmark.title,
                "description": self.benchmark.description,
                "input_text": self.benchmark.input_text,
                "task": self.benchmark.task.model_dump(mode="json"),
            },
            "profiles": {
                "generator": _public_profile(self.generator_profile),
                "judge": _public_profile(self.judge_profile),
                "same_model_judge": self.same_model_judge,
            },
            "candidate": self.generation.result.model_dump(mode="json"),
            "scores": {
                "heuristic": self.heuristic_percentage,
                "judge": self.judge_score,
                "combined": self.combined_score,
                "gap": self.score_gap,
            },
            "heuristic_metrics": [
                {
                    "id": metric.metric_id,
                    "status": metric.status,
                    "points": metric.points,
                    "maximum": metric.maximum,
                    "detail": metric.detail,
                }
                for metric in self.heuristic_metrics
            ],
            "judge": {
                **self.judge.result.model_dump(mode="json"),
                "computed_total": self.judge_score,
                "computed_verdict": self.judge.result.verdict,
            },
            "execution": {
                "generation": self.generation.metadata(),
                "judge": self.judge.metadata(),
            },
        }


BENCHMARKS: dict[str, IntentBenchmark] = {
    "flux-portrait-intent-basic": IntentBenchmark(
        benchmark_id="flux-portrait-intent-basic",
        title="Short human portrait intent",
        description=(
            "Measures whether the model can turn a short Russian user request into a coherent, "
            "visually specific FLUX prompt without receiving a ready-made production brief."
        ),
        task=PromptTask(
            family=PromptFamily.FLUX,
            operation=PromptOperation.GENERATE,
            scenario=PromptScenario.PORTRAIT,
            modifiers=(PromptModifier.SAFE,),
            checkpoint_profile="flux-intent-benchmark-v1",
        ),
        input_text=(
            "Сделай атмосферный портрет взрослой девушки-керамиста в её мастерской. "
            "Хочется, чтобы кадр выглядел естественно, дорого и немного уютно."
        ),
    ),
}


def _public_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": profile.get("id"),
        "name": profile.get("name"),
        "kind": profile.get("kind"),
        "cli_type": profile.get("cli_type"),
        "model": profile.get("model"),
    }


def _contains_any(text: str, markers: tuple[str, ...]) -> list[str]:
    lowered = text.casefold()
    return [marker for marker in markers if marker.casefold() in lowered]


def _coverage_metric(
    *,
    metric_id: str,
    prompt: str,
    markers: tuple[str, ...],
    maximum: int,
    label: str,
) -> IntentHeuristicMetric:
    found = _contains_any(prompt, markers)
    if found:
        return IntentHeuristicMetric(
            metric_id,
            "pass",
            maximum,
            maximum,
            f"{label}: " + ", ".join(found[:4]),
        )
    return IntentHeuristicMetric(
        metric_id,
        "fail",
        0,
        maximum,
        f"No concrete {label.lower()} was found.",
    )


def evaluate_intent_heuristics(
    benchmark: IntentBenchmark,
    result: PromptResult,
) -> tuple[IntentHeuristicMetric, ...]:
    prompt = result.positive_prompt.strip()
    metrics: list[IntentHeuristicMetric] = []

    core_groups = {
        "adult": ("adult", "grown woman", "woman in her twenties", "woman in her thirties"),
        "female": ("woman", "female", "young woman"),
        "ceramic_artist": ("ceramic artist", "ceramist", "potter", "pottery artist"),
        "workshop": ("workshop", "pottery studio", "ceramic studio", "atelier"),
    }
    covered_core = [
        group
        for group, markers in core_groups.items()
        if _contains_any(prompt, markers)
    ]
    core_points = round(15 * len(covered_core) / len(core_groups))
    core_status: IntentStatus = (
        "pass" if len(covered_core) == len(core_groups) else
        "warn" if len(covered_core) >= 3 else
        "fail"
    )
    metrics.append(IntentHeuristicMetric(
        "core_intent",
        core_status,
        core_points,
        15,
        f"Preserved {len(covered_core)}/4 core groups: " + ", ".join(covered_core),
    ))

    metrics.append(_coverage_metric(
        metric_id="invented_camera_language",
        prompt=prompt,
        markers=(
            "close-up", "close up", "medium shot", "medium portrait", "three-quarter",
            "eye-level", "eye level", "lens", "framing", "camera", "portrait crop",
        ),
        maximum=10,
        label="Camera or framing language",
    ))
    metrics.append(_coverage_metric(
        metric_id="invented_lighting",
        prompt=prompt,
        markers=(
            "window light", "side light", "key light", "fill light", "rim light",
            "diffused light", "soft light", "warm light", "shadow", "backlight",
        ),
        maximum=10,
        label="Motivated lighting",
    ))
    metrics.append(_coverage_metric(
        metric_id="invented_environment_detail",
        prompt=prompt,
        markers=(
            "pottery wheel", "kiln", "shelves", "ceramic tools", "bowls", "vessels",
            "clay", "workbench", "studio shelves", "handmade ceramics",
        ),
        maximum=10,
        label="Workshop detail",
    ))
    metrics.append(_coverage_metric(
        metric_id="tactile_materials",
        prompt=prompt,
        markers=(
            "skin texture", "linen", "clay dust", "matte ceramic", "glazed ceramic",
            "wood grain", "fabric texture", "handmade surface", "material response",
        ),
        maximum=10,
        label="Tactile material language",
    ))

    atmosphere_groups = {
        "natural": ("natural", "unposed", "authentic", "candid", "relaxed"),
        "refined": ("refined", "editorial", "elegant", "polished", "restrained"),
        "cozy": ("cozy", "warm", "intimate", "inviting", "softly lit"),
    }
    atmosphere_covered = [
        group
        for group, markers in atmosphere_groups.items()
        if _contains_any(prompt, markers)
    ]
    atmosphere_points = 5 * len(atmosphere_covered)
    atmosphere_status: IntentStatus = (
        "pass" if len(atmosphere_covered) == 3 else
        "warn" if len(atmosphere_covered) == 2 else
        "fail"
    )
    metrics.append(IntentHeuristicMetric(
        "atmosphere_translation",
        atmosphere_status,
        atmosphere_points,
        15,
        "Translated mood groups: " + (", ".join(atmosphere_covered) or "none"),
    ))

    input_words = {word.casefold() for word in _WORD_RE.findall(benchmark.input_text)}
    output_words = [word.casefold() for word in _WORD_RE.findall(prompt)]
    novel_words = {word for word in output_words if word not in input_words}
    novelty_ratio = len(novel_words) / max(1, len(set(output_words)))
    if len(output_words) >= 65 and novelty_ratio >= 0.65:
        expansion = IntentHeuristicMetric(
            "non_trivial_expansion", "pass", 15, 15,
            f"{len(output_words)} words with {novelty_ratio:.0%} lexical novelty.",
        )
    elif len(output_words) >= 40 and novelty_ratio >= 0.45:
        expansion = IntentHeuristicMetric(
            "non_trivial_expansion", "warn", 8, 15,
            f"{len(output_words)} words with {novelty_ratio:.0%} novelty; expansion is useful but limited.",
        )
    else:
        expansion = IntentHeuristicMetric(
            "non_trivial_expansion", "fail", 0, 15,
            f"{len(output_words)} words with {novelty_ratio:.0%} novelty; likely paraphrase or shallow expansion.",
        )
    metrics.append(expansion)

    sentence_count = len(_SENTENCE_RE.findall(prompt))
    if sentence_count >= 3:
        metrics.append(IntentHeuristicMetric(
            "coherent_structure", "pass", 5, 5,
            f"{sentence_count} developed sentences found.",
        ))
    elif sentence_count == 2:
        metrics.append(IntentHeuristicMetric(
            "coherent_structure", "warn", 4, 5,
            "Two coherent sentences found.",
        ))
    else:
        metrics.append(IntentHeuristicMetric(
            "coherent_structure", "warn" if len(output_words) >= 50 else "fail",
            3 if len(output_words) >= 50 else 0,
            5,
            "The result is compressed into one sentence or fragment.",
        ))

    metrics.append(IntentHeuristicMetric(
        "flux_negative_policy",
        "pass" if result.negative_prompt == "" else "fail",
        5 if result.negative_prompt == "" else 0,
        5,
        "FLUX negative_prompt is empty." if result.negative_prompt == "" else
        "FLUX benchmark expects an empty negative_prompt.",
    ))

    buzzwords = [item for item in _GENERIC_BUZZWORDS if item in prompt.casefold()]
    metrics.append(IntentHeuristicMetric(
        "anti_buzzword",
        "pass" if not buzzwords else "fail",
        5 if not buzzwords else 0,
        5,
        "No generic quality slogans found." if not buzzwords else
        "Generic slogans found: " + ", ".join(buzzwords),
    ))
    return tuple(metrics)


def intent_status(
    report: IntentBenchmarkReport,
    minimum_score: int,
) -> IntentStatus:
    hard_failures = {
        metric.metric_id
        for metric in report.heuristic_metrics
        if metric.status == "fail"
        and metric.metric_id in {"core_intent", "flux_negative_policy"}
    }
    if hard_failures:
        return "fail"
    if report.combined_score >= minimum_score:
        return "warn" if report.score_gap > 25 else "pass"
    if report.combined_score >= max(0, minimum_score - 15):
        return "warn"
    return "fail"


def run_intent_benchmark(
    *,
    benchmark: IntentBenchmark,
    generator_profile: dict[str, Any],
    judge_profile: dict[str, Any],
    generator: OpenCodePromptExecutor | None = None,
    judge: OpenCodeIntentJudgeExecutor | None = None,
) -> IntentBenchmarkReport:
    generation = (generator or OpenCodePromptExecutor()).execute(
        profile=generator_profile,
        task=benchmark.task,
        user_input=benchmark.input_text,
    )
    judge_execution = (judge or OpenCodeIntentJudgeExecutor()).execute(
        profile=judge_profile,
        family=benchmark.task.family.value,
        user_request=benchmark.input_text,
        candidate=generation.result,
    )
    return IntentBenchmarkReport(
        benchmark=benchmark,
        generator_profile=generator_profile,
        judge_profile=judge_profile,
        generation=generation,
        judge=judge_execution,
        heuristic_metrics=evaluate_intent_heuristics(benchmark, generation.result),
    )


def _status_style(status: IntentStatus) -> str:
    return {"pass": "bold green", "warn": "bold yellow", "fail": "bold red"}[status]


def _print_benchmarks(console: Console) -> None:
    table = Table(title="Prompt intent benchmarks")
    table.add_column("ID", style="bold cyan")
    table.add_column("Family")
    table.add_column("Input language")
    table.add_column("Purpose")
    for benchmark in BENCHMARKS.values():
        table.add_row(
            benchmark.benchmark_id,
            benchmark.task.family.value,
            "Russian",
            benchmark.description,
        )
    console.print(table)


def _print_report(
    console: Console,
    report: IntentBenchmarkReport,
    *,
    minimum_score: int,
    show_bundle: bool,
) -> None:
    console.print(Panel(
        Text(report.benchmark.input_text),
        title="Raw human request",
        border_style="blue",
    ))

    candidate = Table(title="Generated PromptResult", show_header=False)
    candidate.add_column("Field", style="bold cyan", no_wrap=True)
    candidate.add_column("Value", overflow="fold")
    candidate.add_row("positive_prompt", report.generation.result.positive_prompt)
    candidate.add_row("negative_prompt", report.generation.result.negative_prompt or "<empty>")
    console.print(candidate)

    heuristic = Table(title="Deterministic intent checks")
    heuristic.add_column("Status")
    heuristic.add_column("Metric")
    heuristic.add_column("Points")
    heuristic.add_column("Detail")
    for metric in report.heuristic_metrics:
        heuristic.add_row(
            Text(metric.status.upper(), style=_status_style(metric.status)),
            metric.metric_id,
            f"{metric.points}/{metric.maximum}",
            metric.detail,
        )
    console.print(heuristic)

    scores = report.judge.result.scores
    judge_table = Table(title="Model judge rubric")
    judge_table.add_column("Criterion")
    judge_table.add_column("Points")
    for name, maximum in (
        ("intent_fidelity", 20),
        ("useful_visual_expansion", 20),
        ("atmosphere_translation", 15),
        ("composition_and_camera", 10),
        ("lighting", 10),
        ("environment_and_materials", 10),
        ("coherence_and_model_fit", 10),
        ("restraint_and_consistency", 5),
    ):
        judge_table.add_row(name, f"{getattr(scores, name)}/{maximum}")
    console.print(judge_table)

    if report.judge.result.strengths:
        console.print(Panel(
            "\n".join(f"• {item}" for item in report.judge.result.strengths),
            title="Judge strengths",
            border_style="green",
        ))
    if report.judge.result.weaknesses:
        console.print(Panel(
            "\n".join(f"• {item}" for item in report.judge.result.weaknesses),
            title="Judge weaknesses",
            border_style="yellow",
        ))
    console.print(Panel(
        report.judge.result.rationale,
        title="Judge rationale",
        border_style="magenta",
    ))

    status = intent_status(report, minimum_score)
    summary = Table(show_header=False, box=None)
    summary.add_column(style="bold cyan")
    summary.add_column()
    summary.add_row("Heuristic score", f"{report.heuristic_percentage}/100")
    summary.add_row("Judge score", f"{report.judge_score}/100")
    summary.add_row("Combined score", f"{report.combined_score}/100")
    summary.add_row("Score gap", f"{report.score_gap} points")
    summary.add_row("Minimum", f"{minimum_score}/100")
    summary.add_row("Same-model judge", "yes" if report.same_model_judge else "no")
    summary.add_row("Generation latency", f"{report.generation.latency_ms} ms")
    summary.add_row("Judge latency", f"{report.judge.latency_ms} ms")
    summary.add_row("Result", status.upper())
    console.print(Panel(
        summary,
        title="Intent benchmark summary",
        border_style={"pass": "green", "warn": "yellow", "fail": "red"}[status],
    ))

    if show_bundle:
        console.print(Panel(
            Text(report.generation.bundle.render()),
            title="Generator InstructionBundle",
            border_style="magenta",
        ))


def _write_json(path_value: str, report: IntentBenchmarkReport) -> Path:
    path = normalize_path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.ai.intent_benchmark",
        description="Evaluate prompt intent expansion through generation plus an isolated model judge.",
    )
    parser.add_argument("--no-color", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List intent benchmarks.")

    run = subparsers.add_parser("run", help="Run one intent benchmark through OpenCode.")
    run.add_argument("benchmark", choices=tuple(BENCHMARKS))
    run.add_argument("--profile", help="Generator OpenCode profile ID or exact name.")
    run.add_argument(
        "--judge-profile",
        help="Judge OpenCode profile ID or exact name. Defaults to the generator profile.",
    )
    run.add_argument("--config", help="Override the application config.json path.")
    run.add_argument("--minimum-score", type=int, default=80)
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
        config_path = (
            normalize_path(args.config)
            if args.config
            else build_runtime_paths().config
        )
        store = AIProfileStore(config_path)
        generator_resolved = resolve_opencode_profile(
            store,
            selector=args.profile,
            requires_image=False,
        )
        judge_resolved = (
            resolve_opencode_profile(
                store,
                selector=args.judge_profile,
                requires_image=False,
            )
            if args.judge_profile
            else generator_resolved
        )
        generator_profile = dict(generator_resolved.profile)
        judge_profile = dict(judge_resolved.profile)
        if args.timeout is not None:
            if not 5 <= args.timeout <= 600:
                raise SmokeRunnerError(
                    "Timeout must be between 5 and 600 seconds.",
                    code="invalid_timeout",
                )
            generator_profile["timeout_seconds"] = args.timeout
            judge_profile["timeout_seconds"] = args.timeout

        benchmark = BENCHMARKS[args.benchmark]
        header = Table(show_header=False, box=None)
        header.add_column(style="bold cyan")
        header.add_column()
        header.add_row("Benchmark", f"{benchmark.benchmark_id} · {benchmark.title}")
        header.add_row("Generator", f"{generator_profile['name']} · {generator_profile['model']}")
        header.add_row("Judge", f"{judge_profile['name']} · {judge_profile['model']}")
        header.add_row("Judge mode", "same model" if generator_profile["id"] == judge_profile["id"] else "separate profile")
        header.add_row("Minimum score", f"{args.minimum_score}/100")
        console.print(Panel(header, title="Prompt intent benchmark", border_style="cyan"))

        with console.status("Generating prompt from raw intent…", spinner="dots"):
            generation = OpenCodePromptExecutor().execute(
                profile=generator_profile,
                task=benchmark.task,
                user_input=benchmark.input_text,
            )
        with console.status("Evaluating candidate with model judge…", spinner="dots"):
            judge_execution = OpenCodeIntentJudgeExecutor().execute(
                profile=judge_profile,
                family=benchmark.task.family.value,
                user_request=benchmark.input_text,
                candidate=generation.result,
            )
        report = IntentBenchmarkReport(
            benchmark=benchmark,
            generator_profile=generator_profile,
            judge_profile=judge_profile,
            generation=generation,
            judge=judge_execution,
            heuristic_metrics=evaluate_intent_heuristics(benchmark, generation.result),
        )
        _print_report(
            console,
            report,
            minimum_score=args.minimum_score,
            show_bundle=args.show_bundle,
        )
        if args.json_out:
            console.print(f"JSON report: {_write_json(args.json_out, report)}")
        return 0 if intent_status(report, args.minimum_score) == "pass" else 3
    except (OpenCodePromptExecutionError, OpenCodeIntentJudgeExecutionError) as exc:
        detail = f"stage={exc.stage} · code={exc.code}\n{exc}"
        if args.debug and exc.technical_error:
            detail += f"\n\nTechnical detail:\n{exc.technical_error}"
        console.print(Panel(
            Text(detail),
            title="Intent benchmark execution failed",
            border_style="red",
        ))
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
            title="Intent benchmark configuration error",
            border_style="red",
        ))
        return 2


if __name__ == "__main__":
    sys.exit(main())
