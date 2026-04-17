"""Cross-framework run artifact loading and aggregation helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mobile_world.runtime.utils.trajectory_logger import (
    EVALUATOR_AUDIT_FILE_NAME,
    METRICS_FILE_NAME,
    SCORE_FILE_NAME,
)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _parse_score(score_path: Path) -> float:
    text = score_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.lower().startswith("score:"):
            return float(line.split(":", 1)[1].strip())
    raise ValueError(f"Unable to parse score from {score_path}")


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _judge_agreement_passed(audit: dict[str, Any]) -> bool | None:
    checks = audit.get("consistency_checks", [])
    if not isinstance(checks, list):
        return None
    for check in checks:
        if not isinstance(check, dict):
            continue
        if check.get("name") == "judge_agreement":
            passed = check.get("passed")
            if isinstance(passed, bool):
                return passed
            return None
    return None


def _load_run_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / "run_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        return _read_json(manifest_path)
    except Exception:
        return {}


@dataclass
class TaskRunRecord:
    task_name: str
    score: float
    metrics: dict[str, Any]
    evaluator_audit: dict[str, Any]
    root_dir: str
    mixed_summary: dict[str, Any] | None = None


@dataclass
class FrameworkRunBundle:
    framework: str
    run_root: str
    records: dict[str, TaskRunRecord]
    run_manifest: dict[str, Any]
    evaluation_mode: str
    allow_adb_bypass: bool


def load_task_run_records(run_root: str) -> dict[str, TaskRunRecord]:
    """Load per-task run artifacts from one benchmark output root."""
    root = Path(run_root).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Run root not found: {root}")

    records: dict[str, TaskRunRecord] = {}
    for task_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        score_path = task_dir / SCORE_FILE_NAME
        if not score_path.exists():
            continue

        metrics_path = task_dir / METRICS_FILE_NAME
        audit_path = task_dir / EVALUATOR_AUDIT_FILE_NAME
        mixed_summary_path = task_dir / "nanobot_mixed_summary.json"

        metrics = _read_json(metrics_path) if metrics_path.exists() else {}
        audit = _read_json(audit_path) if audit_path.exists() else {}
        mixed_summary = _read_json(mixed_summary_path) if mixed_summary_path.exists() else None

        records[task_dir.name] = TaskRunRecord(
            task_name=task_dir.name,
            score=_parse_score(score_path),
            metrics=metrics,
            evaluator_audit=audit,
            root_dir=str(task_dir),
            mixed_summary=mixed_summary,
        )
    return records


def _resolve_evaluation_mode(*, manifest: dict[str, Any], records: dict[str, TaskRunRecord]) -> str:
    mode = manifest.get("evaluation_mode") if isinstance(manifest, dict) else None
    if isinstance(mode, str):
        normalized = mode.strip().lower()
        if normalized in {"standard", "mixed"}:
            return normalized

    has_mixed_summary = any(record.mixed_summary is not None for record in records.values())
    return "mixed" if has_mixed_summary else "standard"


def _resolve_allow_adb_bypass(*, manifest: dict[str, Any], evaluation_mode: str) -> bool:
    value = manifest.get("allow_adb_bypass") if isinstance(manifest, dict) else None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return evaluation_mode == "mixed"


def _framework_summary(
    *,
    framework: str,
    records: dict[str, TaskRunRecord],
    task_names: list[str],
    success_threshold: float,
) -> dict[str, Any]:
    scores: list[float] = []
    ttft_values: list[float] = []
    tool_success_rates: list[float] = []
    invalid_action_rates: list[float] = []
    step_counts: list[float] = []
    successes = 0
    tokens_success_total = 0.0
    cost_per_success_values: list[float] = []
    judge_checks_total = 0
    judge_checks_passed = 0

    for task_name in task_names:
        record = records.get(task_name)
        if record is None:
            continue

        score = float(record.score)
        scores.append(score)
        is_success = score >= success_threshold
        if is_success:
            successes += 1

        token_total = _to_float(
            record.metrics.get("token_usage", {}).get("total", {}).get("total_tokens")
        )
        if is_success and token_total is not None:
            tokens_success_total += token_total

        cost_per_success = _to_float(record.metrics.get("cost", {}).get("cost_per_success"))
        if is_success and cost_per_success is not None:
            cost_per_success_values.append(cost_per_success)

        ttft_ms = _to_float(record.metrics.get("latency", {}).get("ttft_ms"))
        if ttft_ms is not None:
            ttft_values.append(ttft_ms)

        tool_success_rate = _to_float(record.metrics.get("reliability", {}).get("tool_success_rate"))
        if tool_success_rate is not None:
            tool_success_rates.append(tool_success_rate)

        invalid_action_rate = _to_float(record.metrics.get("reliability", {}).get("invalid_action_rate"))
        if invalid_action_rate is not None:
            invalid_action_rates.append(invalid_action_rate)

        total_steps = _to_float(record.metrics.get("reliability", {}).get("total_steps"))
        if total_steps is not None:
            step_counts.append(total_steps)

        judge_agreement = _judge_agreement_passed(record.evaluator_audit)
        if judge_agreement is not None:
            judge_checks_total += 1
            judge_checks_passed += int(judge_agreement)

    task_count = len(task_names)
    success_rate = (successes / task_count) if task_count else 0.0
    tokens_per_success = (tokens_success_total / successes) if successes > 0 else None
    judge_agreement_rate = (
        round(judge_checks_passed / judge_checks_total, 6) if judge_checks_total else None
    )

    return {
        "framework": framework,
        "tasks_compared": task_count,
        "successes": successes,
        "success_rate": round(success_rate, 6),
        "avg_score": _mean(scores),
        "tokens_per_success": round(tokens_per_success, 6) if tokens_per_success is not None else None,
        "cost_per_success": _mean(cost_per_success_values),
        "avg_ttft_ms": _mean(ttft_values),
        "avg_tool_success_rate": _mean(tool_success_rates),
        "avg_invalid_action_rate": _mean(invalid_action_rates),
        "avg_steps": _mean(step_counts),
        "judge_agreement_rate": judge_agreement_rate,
    }


def _mixed_lane_metrics(*, records: dict[str, TaskRunRecord], task_names: list[str]) -> dict[str, Any]:
    adb_calls = 0
    gui_task_calls = 0
    deeplink_calls = 0
    gui_steps = 0

    for task_name in task_names:
        record = records.get(task_name)
        summary = record.mixed_summary if record else None
        if not isinstance(summary, dict):
            continue
        adb_calls += _to_int(summary.get("adb_calls"))
        gui_task_calls += _to_int(summary.get("gui_task_calls"))
        deeplink_calls += _to_int(summary.get("deeplink_calls"))
        gui_steps += _to_int(summary.get("gui_steps"))

    tasks_compared = len(task_names)
    return {
        "adb_calls": adb_calls,
        "gui_task_calls": gui_task_calls,
        "deeplink_calls": deeplink_calls,
        "gui_steps": gui_steps,
        "avg_adb_calls_per_task": round(adb_calls / tasks_compared, 6) if tasks_compared else 0.0,
        "avg_gui_task_calls_per_task": round(gui_task_calls / tasks_compared, 6) if tasks_compared else 0.0,
        "avg_deeplink_calls_per_task": round(deeplink_calls / tasks_compared, 6) if tasks_compared else 0.0,
        "avg_gui_steps_per_task": round(gui_steps / tasks_compared, 6) if tasks_compared else 0.0,
    }


def aggregate_framework_runs(
    *,
    framework_runs: dict[str, str],
    success_threshold: float = 0.99,
) -> dict[str, Any]:
    """Aggregate multiple framework run roots into a comparable report."""
    if not framework_runs:
        raise ValueError("At least one framework run root is required")

    bundles: dict[str, FrameworkRunBundle] = {}
    for framework, run_root in framework_runs.items():
        root = Path(run_root).expanduser()
        records = load_task_run_records(str(root))
        manifest = _load_run_manifest(root)
        mode = _resolve_evaluation_mode(manifest=manifest, records=records)
        allow_bypass = _resolve_allow_adb_bypass(manifest=manifest, evaluation_mode=mode)
        bundles[framework] = FrameworkRunBundle(
            framework=framework,
            run_root=str(root),
            records=records,
            run_manifest=manifest,
            evaluation_mode=mode,
            allow_adb_bypass=allow_bypass,
        )

    framework_names = sorted(bundles.keys())

    task_sets = [set(bundle.records.keys()) for bundle in bundles.values()]
    if not task_sets:
        common_tasks: list[str] = []
    elif len(task_sets) == 1:
        common_tasks = sorted(task_sets[0])
    else:
        common_tasks = sorted(set.intersection(*task_sets))

    summaries: list[dict[str, Any]] = []
    for framework in framework_names:
        bundle = bundles[framework]
        summary = _framework_summary(
            framework=framework,
            records=bundle.records,
            task_names=common_tasks,
            success_threshold=success_threshold,
        )
        summary["evaluation_mode"] = bundle.evaluation_mode
        summary["allow_adb_bypass"] = bundle.allow_adb_bypass
        if bundle.evaluation_mode == "mixed":
            summary["lane_metrics"] = _mixed_lane_metrics(
                records=bundle.records,
                task_names=common_tasks,
            )
        summaries.append(summary)

    def _sort_key(row: dict[str, Any]) -> tuple[float, float]:
        success = float(row.get("success_rate") or 0.0)
        avg_score = row.get("avg_score")
        return success, float(avg_score) if avg_score is not None else -1.0

    standard_leaderboard = sorted(
        [row for row in summaries if row.get("evaluation_mode") == "standard"],
        key=_sort_key,
        reverse=True,
    )
    mixed_leaderboard = sorted(
        [row for row in summaries if row.get("evaluation_mode") == "mixed"],
        key=_sort_key,
        reverse=True,
    )

    task_matrix = []
    for task_name in common_tasks:
        row: dict[str, Any] = {"task_name": task_name}
        for framework in framework_names:
            record = bundles[framework].records.get(task_name)
            row[f"{framework}_score"] = record.score if record else None
        task_matrix.append(row)

    efficiency_panel = [
        {
            "framework": row["framework"],
            "tokens_per_success": row["tokens_per_success"],
            "cost_per_success": row["cost_per_success"],
            "avg_steps": row["avg_steps"],
        }
        for row in summaries
    ]
    latency_panel = [
        {"framework": row["framework"], "avg_ttft_ms": row["avg_ttft_ms"]}
        for row in summaries
    ]
    reliability_panel = [
        {
            "framework": row["framework"],
            "avg_tool_success_rate": row["avg_tool_success_rate"],
            "avg_invalid_action_rate": row["avg_invalid_action_rate"],
        }
        for row in summaries
    ]
    evaluation_quality_panel = [
        {
            "framework": row["framework"],
            "judge_agreement_rate": row["judge_agreement_rate"],
        }
        for row in summaries
    ]

    leaderboards = {
        "standard": standard_leaderboard,
        "mixed": mixed_leaderboard,
    }

    # Backward compatibility for existing consumers.
    legacy_leaderboard = standard_leaderboard if standard_leaderboard else mixed_leaderboard

    framework_modes = {
        name: {
            "evaluation_mode": bundles[name].evaluation_mode,
            "allow_adb_bypass": bundles[name].allow_adb_bypass,
        }
        for name in framework_names
    }

    return {
        "schema_version": "1.1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "config": {
            "success_threshold": success_threshold,
        },
        "common_tasks": common_tasks,
        "frameworks": framework_names,
        "framework_modes": framework_modes,
        "leaderboards": leaderboards,
        "leaderboard": legacy_leaderboard,
        "comparability_notes": [
            "mixed leaderboard allows ADB/deeplink/gui_task bypass lanes and must not be rank-merged directly with standard leaderboard."
        ],
        "kpi_panels": {
            "efficiency": efficiency_panel,
            "latency": latency_panel,
            "reliability": reliability_panel,
            "evaluation_quality": evaluation_quality_panel,
        },
        "task_matrix": task_matrix,
    }


def write_report(*, report: dict[str, Any], output_path: str) -> None:
    """Write a JSON report to disk."""
    path = Path(output_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
