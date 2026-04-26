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
    SKILL_SUMMARY_FILE_NAME,
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


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


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
    skill_summary: dict[str, Any] | None = None


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
        skill_summary_path = task_dir / SKILL_SUMMARY_FILE_NAME

        metrics = _read_json(metrics_path) if metrics_path.exists() else {}
        audit = _read_json(audit_path) if audit_path.exists() else {}
        mixed_summary = _read_json(mixed_summary_path) if mixed_summary_path.exists() else None
        skill_summary = _read_json(skill_summary_path) if skill_summary_path.exists() else None

        records[task_dir.name] = TaskRunRecord(
            task_name=task_dir.name,
            score=_parse_score(score_path),
            metrics=metrics,
            evaluator_audit=audit,
            root_dir=str(task_dir),
            mixed_summary=mixed_summary,
            skill_summary=skill_summary,
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
    predict_latency_values: list[float] = []
    completion_per_step_values: list[float] = []
    completion_totals: list[float] = []
    skill_hit_completion_per_step: list[float] = []
    skill_miss_completion_per_step: list[float] = []
    skill_hit_predict_latency: list[float] = []
    skill_miss_predict_latency: list[float] = []
    base_agent_completion_tokens = 0
    skill_reuser_completion_tokens = 0
    skill_extractor_completion_tokens = 0
    successes = 0

    for task_name in task_names:
        record = records.get(task_name)
        if record is None:
            continue

        score = float(record.score)
        scores.append(score)
        is_success = score >= success_threshold
        if is_success:
            successes += 1
        latency = record.metrics.get("latency", {}) if isinstance(record.metrics, dict) else {}
        token_usage = record.metrics.get("token_usage", {}) if isinstance(record.metrics, dict) else {}
        avg_predict = latency.get("avg_predict_latency_ms_per_step")
        avg_completion = token_usage.get("avg_completion_tokens_per_step")
        total_completion = token_usage.get("total", {}).get("completion_tokens") if isinstance(token_usage.get("total"), dict) else None
        if isinstance(avg_predict, (int, float)):
            predict_latency_values.append(float(avg_predict))
        if isinstance(avg_completion, (int, float)):
            completion_per_step_values.append(float(avg_completion))
            if record.skill_summary and record.skill_summary.get("skill_hit"):
                skill_hit_completion_per_step.append(float(avg_completion))
            else:
                skill_miss_completion_per_step.append(float(avg_completion))
        if isinstance(avg_predict, (int, float)):
            if record.skill_summary and record.skill_summary.get("skill_hit"):
                skill_hit_predict_latency.append(float(avg_predict))
            else:
                skill_miss_predict_latency.append(float(avg_predict))
        if isinstance(total_completion, (int, float)):
            completion_totals.append(float(total_completion))
        if isinstance(record.skill_summary, dict):
            base_agent_completion_tokens += int(
                record.skill_summary.get("base_agent_completion_tokens", 0) or 0
            )
            skill_reuser_completion_tokens += int(
                record.skill_summary.get("skill_reuser_completion_tokens", 0) or 0
            )
            skill_extractor_completion_tokens += int(
                record.skill_summary.get("skill_extractor_completion_tokens", 0) or 0
            )

    task_count = len(task_names)
    success_rate = (successes / task_count) if task_count else 0.0

    return {
        "framework": framework,
        "tasks_compared": task_count,
        "successes": successes,
        "success_rate": round(success_rate, 6),
        "avg_score": _mean(scores),
        "avg_predict_latency_ms_per_step": _mean(predict_latency_values),
        "avg_completion_tokens_per_step": _mean(completion_per_step_values),
        "skill_reuse_breakdown": {
            "reuse": {
                "tasks": len(skill_hit_completion_per_step) or len(skill_hit_predict_latency),
                "avg_predict_latency_ms_per_step": _mean(skill_hit_predict_latency),
                "avg_completion_tokens_per_step": _mean(skill_hit_completion_per_step),
            },
            "no_reuse": {
                "tasks": len(skill_miss_completion_per_step) or len(skill_miss_predict_latency),
                "avg_predict_latency_ms_per_step": _mean(skill_miss_predict_latency),
                "avg_completion_tokens_per_step": _mean(skill_miss_completion_per_step),
            },
        },
        "completion_tokens_per_successful_task": round(sum(completion_totals) / successes, 6)
        if successes
        else None,
        "base_agent_completion_tokens": base_agent_completion_tokens,
        "skill_reuser_completion_tokens": skill_reuser_completion_tokens,
        "skill_extractor_completion_tokens": skill_extractor_completion_tokens,
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
        "schema_version": "1.2.0",
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
            "mixed and standard leaderboards are reported separately and should not be rank-merged directly."
        ],
        "task_matrix": task_matrix,
    }


def write_report(*, report: dict[str, Any], output_path: str) -> None:
    """Write a JSON report to disk."""
    path = Path(output_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
