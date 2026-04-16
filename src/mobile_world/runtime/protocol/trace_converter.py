"""Legacy trajectory conversion helpers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from mobile_world.runtime.protocol.events import (
    CANONICAL_TRAJECTORY_SCHEMA_VERSION,
    CanonicalTrajectoryHeader,
)
from mobile_world.runtime.protocol.normalization import (
    normalize_metrics_event,
    normalize_score_event,
    normalize_step_event,
)
from mobile_world.runtime.utils.trajectory_logger import (
    CANONICAL_LOG_FILE_NAME,
    LOG_FILE_NAME,
)

LEGACY_TRAJECTORY_SCHEMA_VERSION = "legacy-traj.v1"
TRACE_CONVERTER_VERSION = "1.0.0"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Legacy trajectory must be a JSON object: {path}")
    return payload


def _extract_task_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "0" in payload and isinstance(payload["0"], dict):
        return payload["0"]
    for value in payload.values():
        if isinstance(value, dict) and isinstance(value.get("traj"), list):
            return value
    raise ValueError("Legacy trajectory does not contain a task payload with `traj` entries.")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def convert_legacy_trajectory(
    *,
    legacy_traj_path: str,
    output_path: str | None = None,
    task_name: str | None = None,
    task_goal: str = "",
    run_id: str | None = None,
) -> dict[str, Any]:
    """Convert one legacy `traj.json` artifact into canonical JSONL events."""
    source_path = Path(legacy_traj_path).expanduser()
    if not source_path.exists():
        raise FileNotFoundError(f"Legacy trajectory not found: {source_path}")

    payload = _read_json(source_path)
    task_payload = _extract_task_payload(payload)

    resolved_task_name = task_name or source_path.parent.name or "legacy_task"
    resolved_goal = task_payload.get("task_goal") or task_goal or ""
    resolved_run_id = run_id or f"{resolved_task_name}-converted"
    target_path = (
        Path(output_path).expanduser()
        if output_path
        else source_path.parent / CANONICAL_LOG_FILE_NAME
    )

    header = CanonicalTrajectoryHeader(
        task_name=resolved_task_name,
        task_goal=resolved_goal,
        run_id=resolved_run_id,
        tools=task_payload.get("tools", []) or [],
        metadata={
            "source_trajectory_path": str(source_path),
            "source_schema_version": LEGACY_TRAJECTORY_SCHEMA_VERSION,
            "converter_version": TRACE_CONVERTER_VERSION,
            "target_schema_version": CANONICAL_TRAJECTORY_SCHEMA_VERSION,
        },
    ).model_dump()
    rows: list[dict[str, Any]] = [header]

    legacy_steps = task_payload.get("traj", []) or []
    for step_entry in legacy_steps:
        if not isinstance(step_entry, dict):
            continue
        step_index = int(step_entry.get("step", 0) or 0)
        if step_index <= 0:
            continue
        observation = SimpleNamespace(
            ask_user_response=step_entry.get("ask_user_response"),
            tool_call=step_entry.get("tool_call"),
        )
        step_event = normalize_step_event(
            task_name=resolved_task_name,
            task_goal=resolved_goal,
            run_id=resolved_run_id,
            step=step_index,
            prediction=step_entry.get("prediction"),
            action=step_entry.get("action", {}),
            observation=observation,
            token_usage=step_entry.get("token_usage"),
            info=step_entry.get("step_info") if isinstance(step_entry.get("step_info"), dict) else {},
        )
        rows.append(step_event.model_dump())

    if task_payload.get("score") is not None:
        score_event = normalize_score_event(
            task_name=resolved_task_name,
            run_id=resolved_run_id,
            score=float(task_payload.get("score")),
            reason=str(task_payload.get("reason", "legacy_score")),
            evaluator=task_payload.get("evaluator"),
            evidence_refs=task_payload.get("evidence_refs", []),
        )
        rows.append(score_event.model_dump())

    metrics_summary = task_payload.get("metrics_summary")
    if isinstance(metrics_summary, dict):
        metrics_event = normalize_metrics_event(
            task_name=resolved_task_name,
            run_id=resolved_run_id,
            quality_flags=metrics_summary.get("quality_flags", {}),
            token_usage=metrics_summary.get("token_usage", {}),
            latency=metrics_summary.get("latency", {}),
            reliability=metrics_summary.get("reliability", {}),
            cost=metrics_summary.get("cost", {}),
            info={"source": "legacy_conversion"},
        )
        rows.append(metrics_event.model_dump())

    _write_jsonl(target_path, rows)
    return {
        "ok": True,
        "legacy_path": str(source_path),
        "canonical_path": str(target_path),
        "task_name": resolved_task_name,
        "run_id": resolved_run_id,
        "events_written": len(rows),
        "steps_written": len([row for row in rows if row.get("type") == "step"]),
        "score_written": any(row.get("type") == "score" for row in rows),
        "metrics_written": any(row.get("type") == "metrics" for row in rows),
    }


def convert_legacy_directory(
    *,
    legacy_root: str,
    output_root: str | None = None,
) -> list[dict[str, Any]]:
    """Convert all legacy task trajectories under one root directory."""
    root = Path(legacy_root).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Legacy root not found: {root}")

    results: list[dict[str, Any]] = []
    for task_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        legacy_file = task_dir / LOG_FILE_NAME
        if not legacy_file.exists():
            continue
        out_path = None
        if output_root:
            out_path = str(Path(output_root).expanduser() / task_dir.name / CANONICAL_LOG_FILE_NAME)
        results.append(
            convert_legacy_trajectory(
                legacy_traj_path=str(legacy_file),
                output_path=out_path,
                task_name=task_dir.name,
            )
        )
    return results
