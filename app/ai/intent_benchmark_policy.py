from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .intent_benchmark_core import IntentBenchmarkReport, IntentStatus


def strict_intent_status(
    report: "IntentBenchmarkReport",
    minimum_score: int,
) -> "IntentStatus":
    """Return a conservative benchmark status without changing numeric scores.

    A clean PASS requires the full core intent and every scenario-specific coverage
    rule to pass. Missing one of those signals is still useful output, but it is
    surfaced as WARN so a high same-model judge score cannot hide the omission.
    """

    metrics = {metric.metric_id: metric for metric in report.heuristic_metrics}
    core = metrics.get("core_intent")
    family_policy = metrics.get("family_prompt_policy")

    if core is not None and core.status == "fail":
        return "fail"
    if family_policy is not None and family_policy.status == "fail":
        return "fail"

    coverage_ids = {rule.metric_id for rule in report.benchmark.coverage_rules}
    failed_coverage = any(
        metric.status == "fail" and metric.metric_id in coverage_ids
        for metric in report.heuristic_metrics
    )
    incomplete_core = core is not None and core.status != "pass"

    if report.combined_score >= minimum_score:
        if (
            incomplete_core
            or failed_coverage
            or report.missing_required_intents
            or report.score_gap > 25
        ):
            return "warn"
        return "pass"

    if report.combined_score >= max(0, minimum_score - 15):
        return "warn"
    return "fail"
