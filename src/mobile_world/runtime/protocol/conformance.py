"""Conformance suite for benchmark artifacts and protocol contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mobile_world.runtime.protocol.events import CANONICAL_TRAJECTORY_SCHEMA_VERSION
from mobile_world.runtime.protocol.validation import (
    validate_adapter_contracts,
    validate_canonical_schema,
)
from mobile_world.runtime.utils.trajectory_logger import (
    CANONICAL_LOG_FILE_NAME,
    CANONICAL_META_FILE_NAME,
    EVALUATOR_AUDIT_FILE_NAME,
    LOG_FILE_NAME,
    METRICS_FILE_NAME,
    SCORE_FILE_NAME,
)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def validate_metrics_summary(metrics: dict[str, Any]) -> list[str]:
    """Validate required metrics KPI payload shape."""
    issues: list[str] = []
    quality_flags = metrics.get("quality_flags")
    if not isinstance(quality_flags, dict):
        issues.append("metrics.quality_flags_missing")
    else:
        for key in ("token_usage", "latency", "cost"):
            value = quality_flags.get(key)
            if value not in {"native", "estimated", "unavailable"}:
                issues.append(f"metrics.quality_flags_invalid:{key}")

    token_usage = metrics.get("token_usage", {})
    avg_tokens = token_usage.get("avg_total_tokens_per_step")
    if avg_tokens is not None and not _is_number(avg_tokens):
        issues.append("metrics.token_usage.avg_total_tokens_per_step_not_numeric")

    latency = metrics.get("latency", {})
    for key in ("ttft_ms", "ttfa_ms", "tts_ms"):
        value = latency.get(key)
        if value is not None and not _is_number(value):
            issues.append(f"metrics.latency.{key}_not_numeric")
    for bucket in ("step_latency_ms", "tool_latency_ms"):
        values = latency.get(bucket)
        if values is not None:
            if not isinstance(values, dict):
                issues.append(f"metrics.latency.{bucket}_not_object")
                continue
            for percentile in ("p50", "p95"):
                value = values.get(percentile)
                if value is not None and not _is_number(value):
                    issues.append(f"metrics.latency.{bucket}.{percentile}_not_numeric")

    reliability = metrics.get("reliability", {})
    for key in ("tool_success_rate", "tool_retry_rate", "invalid_action_rate"):
        value = reliability.get(key)
        if value is None or not _is_number(value):
            issues.append(f"metrics.reliability.{key}_missing_or_invalid")

    cost = metrics.get("cost", {})
    if not isinstance(cost, dict):
        issues.append("metrics.cost_not_object")
    elif "cost_per_success" not in cost:
        issues.append("metrics.cost.cost_per_success_missing")
    return issues


def validate_evaluator_audit(audit: dict[str, Any]) -> list[str]:
    """Validate evaluator audit payload shape."""
    issues: list[str] = []
    if not _is_number(audit.get("score")):
        issues.append("audit.score_missing_or_invalid")
    reason = audit.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        issues.append("audit.reason_missing_or_empty")
    if not isinstance(audit.get("evidence_refs"), list):
        issues.append("audit.evidence_refs_missing_or_invalid")
    checks = audit.get("consistency_checks")
    if not isinstance(checks, list):
        issues.append("audit.consistency_checks_missing_or_invalid")
    return issues


def validate_task_artifacts(task_dir: str) -> dict[str, Any]:
    """Validate one task artifact bundle."""
    root = Path(task_dir).expanduser()
    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, details: str = "") -> None:
        checks.append({"name": name, "passed": passed, "details": details})

    required_files = {
        "legacy_traj": root / LOG_FILE_NAME,
        "canonical_log": root / CANONICAL_LOG_FILE_NAME,
        "canonical_meta": root / CANONICAL_META_FILE_NAME,
        "score": root / SCORE_FILE_NAME,
        "metrics": root / METRICS_FILE_NAME,
        "evaluator_audit": root / EVALUATOR_AUDIT_FILE_NAME,
    }
    for label, path in required_files.items():
        add_check(f"file_exists.{label}", path.exists(), str(path))

    if not all(path.exists() for path in required_files.values()):
        return {"task_name": root.name, "ok": False, "checks": checks}

    events = _read_jsonl(required_files["canonical_log"])
    event_types = {event.get("type") for event in events}
    add_check("canonical.header_present", "header" in event_types)
    add_check("canonical.score_present", "score" in event_types)
    add_check("canonical.step_present", "step" in event_types)
    add_check("canonical.metrics_present", "metrics" in event_types)

    mismatched = [
        event.get("type")
        for event in events
        if event.get("schema_version") != CANONICAL_TRAJECTORY_SCHEMA_VERSION
    ]
    add_check(
        "canonical.schema_version_consistent",
        len(mismatched) == 0,
        ",".join(str(item) for item in mismatched),
    )

    meta = _read_json(required_files["canonical_meta"])
    add_check("meta.tool_manifest_present", "tool_manifest" in meta)
    add_check("meta.policy_manifest_present", "policy_manifest" in meta)

    metrics = _read_json(required_files["metrics"])
    metric_issues = validate_metrics_summary(metrics)
    add_check(
        "metrics.contract_valid",
        len(metric_issues) == 0,
        ",".join(metric_issues),
    )

    audit = _read_json(required_files["evaluator_audit"])
    audit_issues = validate_evaluator_audit(audit)
    add_check(
        "evaluator.contract_valid",
        len(audit_issues) == 0,
        ",".join(audit_issues),
    )

    ok = all(check["passed"] for check in checks)
    return {"task_name": root.name, "ok": ok, "checks": checks}


def run_conformance_suite(log_root: str) -> dict[str, Any]:
    """Run adapter/schema/task artifact conformance checks for one run root."""
    root = Path(log_root).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Log root not found: {root}")

    adapter_report = validate_adapter_contracts()
    schema_report = validate_canonical_schema()
    task_results = []
    for task_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if (task_dir / SCORE_FILE_NAME).exists():
            task_results.append(validate_task_artifacts(str(task_dir)))

    adapter_issues = [issue.model_dump() for issue in adapter_report.issues]
    schema_issues = [issue.model_dump() for issue in schema_report.issues]
    tasks_ok = all(result["ok"] for result in task_results) if task_results else False
    ok = adapter_report.ok and schema_report.ok and tasks_ok
    return {
        "ok": ok,
        "checked_tasks": len(task_results),
        "adapter_contract": {
            "ok": adapter_report.ok,
            "checked_adapters": adapter_report.checked_adapters,
            "issues": adapter_issues,
        },
        "canonical_schema": {
            "ok": schema_report.ok,
            "issues": schema_issues,
        },
        "tasks": task_results,
    }
