"""Reproducibility and evaluator-agreement analysis utilities."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from statistics import pvariance
from typing import Any

from mobile_world.runtime.protocol.reporting import load_task_run_records


def _judge_agreement_passed(audit: dict[str, Any]) -> bool | None:
    checks = audit.get("consistency_checks", [])
    if not isinstance(checks, list):
        return None
    for check in checks:
        if not isinstance(check, dict):
            continue
        if check.get("name") == "judge_agreement" and isinstance(check.get("passed"), bool):
            return bool(check["passed"])
    return None


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def evaluate_reproducibility(
    *,
    run_roots: list[str],
    variance_threshold: float = 0.02,
    judge_agreement_threshold: float = 0.8,
) -> dict[str, Any]:
    """Evaluate reproducibility variance and judge agreement across repeated runs."""
    if len(run_roots) < 2:
        raise ValueError("At least two run roots are required for reproducibility analysis")

    loaded_runs = []
    for path in run_roots:
        root = Path(path).expanduser()
        loaded_runs.append({"run_root": str(root), "records": load_task_run_records(str(root))})

    task_sets = [set(item["records"].keys()) for item in loaded_runs]
    common_tasks = sorted(set.intersection(*task_sets)) if task_sets else []

    per_task = []
    variance_values: list[float] = []
    judge_total = 0
    judge_passed = 0
    for task_name in common_tasks:
        scores = [float(item["records"][task_name].score) for item in loaded_runs]
        variance = 0.0 if len(scores) <= 1 else float(pvariance(scores))
        variance_values.append(variance)
        per_task.append(
            {
                "task_name": task_name,
                "scores": scores,
                "mean_score": _mean(scores),
                "score_variance": round(variance, 8),
                "variance_passed": variance <= variance_threshold,
            }
        )
        for item in loaded_runs:
            agreement = _judge_agreement_passed(item["records"][task_name].evaluator_audit)
            if agreement is not None:
                judge_total += 1
                judge_passed += int(agreement)

    reproducibility_variance = _mean(variance_values)
    judge_agreement_rate = round(judge_passed / judge_total, 6) if judge_total else None

    variance_ok = (
        all(row["variance_passed"] for row in per_task) if per_task else False
    )
    agreement_available = judge_total > 0
    agreement_passed = (
        judge_agreement_rate >= judge_agreement_threshold
        if agreement_available and judge_agreement_rate is not None
        else None
    )
    overall_ok = variance_ok and (agreement_passed if agreement_available else True)
    return {
        "ok": overall_ok,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_count": len(loaded_runs),
        "common_tasks": common_tasks,
        "stability_metrics": {
            "reproducibility_variance": reproducibility_variance,
            "variance_threshold": variance_threshold,
            "variance_passed": variance_ok,
        },
        "evaluation_quality": {
            "judge_agreement_rate": judge_agreement_rate,
            "agreement_threshold": judge_agreement_threshold,
            "agreement_passed": agreement_passed,
            "judge_checks_total": judge_total,
        },
        "task_results": per_task,
    }
