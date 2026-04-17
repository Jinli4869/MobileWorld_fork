"""Phase 9 reproducibility agreement-gate regression tests."""

from __future__ import annotations

import json
from pathlib import Path

from mobile_world.runtime.protocol.reproducibility import evaluate_reproducibility
from mobile_world.runtime.utils.trajectory_logger import (
    EVALUATOR_AUDIT_FILE_NAME,
    METRICS_FILE_NAME,
    SCORE_FILE_NAME,
)

# Canonical Phase 9 verification command used by plan and validation artifacts.
PHASE9_COMBINED_REGRESSION_CMD = (
    "UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q "
    "tests/protocol/test_phase9_reproducibility_agreement_gate.py "
    "tests/protocol/test_phase6_reporting_conformance_reproducibility.py"
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_task_bundle(
    root: Path,
    *,
    task_name: str,
    score: float,
    include_judge_check: bool,
    judge_agreement: bool = True,
) -> None:
    task_dir = root / task_name
    task_dir.mkdir(parents=True, exist_ok=True)

    metrics = {
        "token_usage": {
            "total": {
                "prompt_tokens": 20,
                "completion_tokens": 20,
                "cached_tokens": 0,
                "total_tokens": 40,
            }
        },
        "latency": {"ttft_ms": 120.0},
        "reliability": {
            "total_steps": 2,
            "tool_success_rate": 1.0,
            "invalid_action_rate": 0.0,
        },
    }
    checks: list[dict] = [
        {"name": "reason_non_empty", "passed": True},
        {"name": "evidence_refs_present", "passed": True},
    ]
    if include_judge_check:
        checks.append({"name": "judge_agreement", "passed": judge_agreement})
    audit = {
        "score": score,
        "reason": "synthetic",
        "evidence_refs": [{"ref_id": "r1", "ref_type": "task_eval"}],
        "consistency_checks": checks,
    }

    _write_json(task_dir / METRICS_FILE_NAME, metrics)
    _write_json(task_dir / EVALUATOR_AUDIT_FILE_NAME, audit)
    (task_dir / SCORE_FILE_NAME).write_text(f"score: {score}\nreason: synthetic", encoding="utf-8")


def test_reproducibility_stability_gate_passes_without_judge_data(tmp_path: Path):
    run1 = tmp_path / "run1"
    run2 = tmp_path / "run2"

    _write_task_bundle(
        run1,
        task_name="task_unavailable",
        score=1.0,
        include_judge_check=False,
    )
    _write_task_bundle(
        run2,
        task_name="task_unavailable",
        score=0.99,
        include_judge_check=False,
    )

    report = evaluate_reproducibility(
        run_roots=[str(run1), str(run2)],
        variance_threshold=0.001,
        judge_agreement_threshold=0.8,
    )

    assert report["ok"] is True
    assert report["stability_metrics"]["variance_passed"] is True
    assert report["evaluation_quality"]["judge_agreement_rate"] is None
    assert report["evaluation_quality"]["judge_checks_total"] == 0
    assert report["evaluation_quality"]["agreement_available"] is False
    assert report["evaluation_quality"]["agreement_status"] == "unavailable"
    assert report["evaluation_quality"]["agreement_passed"] is None
    assert report["gate_summary"]["agreement_gate"]["status"] == "unavailable"
    assert report["gate_summary"]["agreement_gate"]["available"] is False
    assert report["gate_summary"]["overall_status"] == "passed"


def test_reproducibility_fails_when_judge_available_and_below_threshold(tmp_path: Path):
    run1 = tmp_path / "run1"
    run2 = tmp_path / "run2"
    run3 = tmp_path / "run3"

    _write_task_bundle(
        run1,
        task_name="task_enforced",
        score=1.0,
        include_judge_check=True,
        judge_agreement=False,
    )
    _write_task_bundle(
        run2,
        task_name="task_enforced",
        score=0.99,
        include_judge_check=True,
        judge_agreement=False,
    )
    _write_task_bundle(
        run3,
        task_name="task_enforced",
        score=1.0,
        include_judge_check=True,
        judge_agreement=True,
    )

    report = evaluate_reproducibility(
        run_roots=[str(run1), str(run2), str(run3)],
        variance_threshold=0.001,
        judge_agreement_threshold=0.8,
    )

    assert report["stability_metrics"]["variance_passed"] is True
    assert report["evaluation_quality"]["judge_agreement_rate"] == 0.333333
    assert report["evaluation_quality"]["judge_checks_total"] == 3
    assert report["evaluation_quality"]["agreement_available"] is True
    assert report["evaluation_quality"]["agreement_status"] == "failed"
    assert report["evaluation_quality"]["agreement_passed"] is False
    assert report["gate_summary"]["agreement_gate"]["status"] == "failed"
    assert report["gate_summary"]["overall_status"] == "failed"
    assert report["ok"] is False


def test_reproducibility_report_exposes_agreement_availability_state(tmp_path: Path):
    unavailable_run1 = tmp_path / "unavailable1"
    unavailable_run2 = tmp_path / "unavailable2"
    available_run1 = tmp_path / "available1"
    available_run2 = tmp_path / "available2"

    _write_task_bundle(
        unavailable_run1,
        task_name="task_state",
        score=1.0,
        include_judge_check=False,
    )
    _write_task_bundle(
        unavailable_run2,
        task_name="task_state",
        score=1.0,
        include_judge_check=False,
    )
    _write_task_bundle(
        available_run1,
        task_name="task_state",
        score=1.0,
        include_judge_check=True,
        judge_agreement=True,
    )
    _write_task_bundle(
        available_run2,
        task_name="task_state",
        score=1.0,
        include_judge_check=True,
        judge_agreement=True,
    )

    unavailable_report = evaluate_reproducibility(
        run_roots=[str(unavailable_run1), str(unavailable_run2)],
        variance_threshold=0.001,
        judge_agreement_threshold=0.8,
    )
    available_report = evaluate_reproducibility(
        run_roots=[str(available_run1), str(available_run2)],
        variance_threshold=0.001,
        judge_agreement_threshold=0.8,
    )

    assert unavailable_report["evaluation_quality"]["agreement_available"] is False
    assert unavailable_report["evaluation_quality"]["agreement_status"] == "unavailable"
    assert unavailable_report["evaluation_quality"]["agreement_passed"] is None

    assert available_report["evaluation_quality"]["agreement_available"] is True
    assert available_report["evaluation_quality"]["agreement_status"] == "passed"
    assert available_report["evaluation_quality"]["agreement_passed"] is True
