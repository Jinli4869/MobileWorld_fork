"""Phase 6 reporting, conformance, and reproducibility tests."""

from __future__ import annotations

import json
from pathlib import Path

from mobile_world.core.cli import create_parser
from mobile_world.runtime.protocol.conformance import run_conformance_suite
from mobile_world.runtime.protocol.reporting import aggregate_framework_runs
from mobile_world.runtime.protocol.reproducibility import evaluate_reproducibility
from mobile_world.runtime.protocol.trace_converter import (
    LEGACY_TRAJECTORY_SCHEMA_VERSION,
    convert_legacy_trajectory,
)
from mobile_world.runtime.utils.trajectory_logger import (
    CANONICAL_LOG_FILE_NAME,
    CANONICAL_META_FILE_NAME,
    EVALUATOR_AUDIT_FILE_NAME,
    LOG_FILE_NAME,
    METRICS_FILE_NAME,
    SCORE_FILE_NAME,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def _task_artifact_bundle(
    root: Path,
    *,
    task_name: str,
    score: float,
    total_tokens: int,
    ttft_ms: float,
    tool_success_rate: float,
    invalid_action_rate: float,
    cost_per_success: float,
    judge_agreement: bool,
) -> None:
    task_dir = root / task_name
    task_dir.mkdir(parents=True, exist_ok=True)

    metrics = {
        "quality_flags": {"token_usage": "native", "latency": "estimated", "cost": "native"},
        "token_usage": {
            "total": {
                "prompt_tokens": total_tokens // 2,
                "completion_tokens": total_tokens // 2,
                "cached_tokens": 0,
                "total_tokens": total_tokens,
            },
            "avg_total_tokens_per_step": total_tokens / 2,
        },
        "latency": {
            "ttft_ms": ttft_ms,
            "ttfa_ms": ttft_ms + 20.0,
            "tts_ms": ttft_ms + 120.0,
            "step_latency_ms": {"p50": 210.0, "p95": 260.0},
            "tool_latency_ms": {"p50": 80.0, "p95": 120.0},
        },
        "reliability": {
            "total_steps": 2,
            "tool_success_rate": tool_success_rate,
            "tool_retry_rate": 0.0,
            "invalid_action_rate": invalid_action_rate,
        },
        "cost": {"cost_per_success": cost_per_success, "source": "native"},
    }
    audit = {
        "score": score,
        "reason": "synthetic",
        "evidence_refs": [{"ref_id": "r1", "ref_type": "task_eval"}],
        "consistency_checks": [
            {"name": "reason_non_empty", "passed": True},
            {"name": "evidence_refs_present", "passed": True},
            {"name": "judge_agreement", "passed": judge_agreement},
        ],
    }

    _write_json(task_dir / METRICS_FILE_NAME, metrics)
    _write_json(task_dir / EVALUATOR_AUDIT_FILE_NAME, audit)
    _write_json(task_dir / LOG_FILE_NAME, {"0": {"traj": [], "metrics_summary": metrics}})
    _write_json(
        task_dir / CANONICAL_META_FILE_NAME,
        {
            "tool_manifest": {"allow_user_interaction": False},
            "policy_manifest": {"profile_name": "qwen3vl"},
            "metrics_summary": metrics,
            "evaluator_audit": audit,
        },
    )
    _write_jsonl(
        task_dir / CANONICAL_LOG_FILE_NAME,
        [
            {
                "type": "header",
                "schema_version": "1.0.0",
                "task_name": task_name,
                "task_goal": "synthetic goal",
                "run_id": f"{task_name}-0",
            },
            {
                "type": "step",
                "schema_version": "1.0.0",
                "task_name": task_name,
                "task_goal": "synthetic goal",
                "run_id": f"{task_name}-0",
                "step": 1,
                "action": {"action_type": "click"},
            },
            {
                "type": "metrics",
                "schema_version": "1.0.0",
                "task_name": task_name,
                "run_id": f"{task_name}-0",
            },
            {
                "type": "score",
                "schema_version": "1.0.0",
                "task_name": task_name,
                "run_id": f"{task_name}-0",
                "score": score,
                "reason": "synthetic",
            },
        ],
    )
    (task_dir / SCORE_FILE_NAME).write_text(f"score: {score}\nreason: synthetic", encoding="utf-8")


def _task_mixed_summary(
    task_dir: Path,
    *,
    adb_calls: int,
    gui_task_calls: int,
    deeplink_calls: int,
    gui_steps: int,
) -> None:
    summary = {
        "execution_mode": "mixed",
        "adb_calls": adb_calls,
        "gui_task_calls": gui_task_calls,
        "deeplink_calls": deeplink_calls,
        "gui_steps": gui_steps,
        "trace_refs": [],
    }
    _write_json(task_dir / "nanobot_mixed_summary.json", summary)


def _write_run_manifest(
    run_root: Path,
    *,
    framework_profile: str,
    evaluation_mode: str,
    allow_adb_bypass: bool,
    task_names: list[str],
) -> None:
    _write_json(
        run_root / "run_manifest.json",
        {
            "schema_version": "1.0.0",
            "generated_at": "2026-01-01T00:00:00",
            "framework_profile": framework_profile,
            "evaluation_mode": evaluation_mode,
            "allow_adb_bypass": allow_adb_bypass,
            "task_set": sorted(task_names),
            "task_set_fingerprint": "test",
            "path_fingerprints": {
                "framework_config_path": {"path": None, "exists": False, "fingerprint": None, "path_type": None},
                "nanobot_fork_path": {"path": None, "exists": False, "fingerprint": None, "path_type": None},
                "nanobot_config_path": {"path": None, "exists": False, "fingerprint": None, "path_type": None},
                "gui_claw_path": {"path": None, "exists": False, "fingerprint": None, "path_type": None},
            },
        },
    )


def test_convert_legacy_trajectory_to_canonical(tmp_path: Path):
    legacy_dir = tmp_path / "legacy_task"
    legacy_dir.mkdir(parents=True)
    legacy = {
        "0": {
            "tools": [{"name": "click"}],
            "traj": [
                {
                    "step": 1,
                    "prediction": "do click",
                    "action": {"action_type": "click", "x": 1, "y": 2},
                    "ask_user_response": None,
                    "tool_call": None,
                    "token_usage": {
                        "prompt_tokens": 5,
                        "completion_tokens": 3,
                        "cached_tokens": 0,
                        "total_tokens": 8,
                    },
                    "step_info": {"predict_latency_ms": 120.0},
                }
            ],
            "score": 1.0,
            "reason": "done",
            "metrics_summary": {
                "quality_flags": {"token_usage": "native", "latency": "estimated", "cost": "unavailable"},
                "token_usage": {"avg_total_tokens_per_step": 8.0},
                "latency": {"ttft_ms": 120.0},
                "reliability": {"tool_success_rate": 1.0, "tool_retry_rate": 0.0, "invalid_action_rate": 0.0},
                "cost": {"cost_per_success": None},
            },
        }
    }
    legacy_path = legacy_dir / LOG_FILE_NAME
    _write_json(legacy_path, legacy)
    output_path = legacy_dir / "converted.canonical.jsonl"

    result = convert_legacy_trajectory(
        legacy_traj_path=str(legacy_path),
        output_path=str(output_path),
        task_name="legacy_task",
        task_goal="legacy goal",
    )

    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line]
    assert result["ok"] is True
    assert rows[0]["type"] == "header"
    assert rows[0]["metadata"]["source_schema_version"] == LEGACY_TRAJECTORY_SCHEMA_VERSION
    assert any(row["type"] == "step" for row in rows)
    assert any(row["type"] == "score" for row in rows)
    assert any(row["type"] == "metrics" for row in rows)


def test_aggregate_framework_runs_builds_kpi_panels(tmp_path: Path):
    run_a = tmp_path / "nanobot_run"
    run_b = tmp_path / "openclaw_run"
    _task_artifact_bundle(
        run_a,
        task_name="task_alpha",
        score=1.0,
        total_tokens=100,
        ttft_ms=140.0,
        tool_success_rate=1.0,
        invalid_action_rate=0.0,
        cost_per_success=0.12,
        judge_agreement=True,
    )
    _task_artifact_bundle(
        run_a,
        task_name="task_beta",
        score=0.2,
        total_tokens=90,
        ttft_ms=150.0,
        tool_success_rate=0.7,
        invalid_action_rate=0.2,
        cost_per_success=0.2,
        judge_agreement=False,
    )
    _task_artifact_bundle(
        run_b,
        task_name="task_alpha",
        score=1.0,
        total_tokens=80,
        ttft_ms=110.0,
        tool_success_rate=1.0,
        invalid_action_rate=0.0,
        cost_per_success=0.09,
        judge_agreement=True,
    )
    _task_artifact_bundle(
        run_b,
        task_name="task_beta",
        score=1.0,
        total_tokens=120,
        ttft_ms=130.0,
        tool_success_rate=0.9,
        invalid_action_rate=0.1,
        cost_per_success=0.11,
        judge_agreement=True,
    )

    report = aggregate_framework_runs(
        framework_runs={"nanobot": str(run_a), "openclaw": str(run_b)},
        success_threshold=0.99,
    )

    assert report["common_tasks"] == ["task_alpha", "task_beta"]
    assert report["leaderboard"][0]["framework"] == "openclaw"
    efficiency = {row["framework"]: row for row in report["kpi_panels"]["efficiency"]}
    assert efficiency["nanobot"]["tokens_per_success"] == 100.0
    assert efficiency["openclaw"]["tokens_per_success"] == 100.0


def test_aggregate_framework_runs_supports_leaderboards_by_mode(tmp_path: Path):
    run_mixed = tmp_path / "mixed_run"
    run_standard = tmp_path / "standard_run"

    _task_artifact_bundle(
        run_mixed,
        task_name="task_alpha",
        score=1.0,
        total_tokens=200,
        ttft_ms=120.0,
        tool_success_rate=1.0,
        invalid_action_rate=0.0,
        cost_per_success=0.11,
        judge_agreement=True,
    )
    _task_artifact_bundle(
        run_mixed,
        task_name="task_beta",
        score=0.2,
        total_tokens=140,
        ttft_ms=130.0,
        tool_success_rate=0.7,
        invalid_action_rate=0.2,
        cost_per_success=0.17,
        judge_agreement=False,
    )
    _task_mixed_summary(
        run_mixed / "task_alpha",
        adb_calls=2,
        gui_task_calls=1,
        deeplink_calls=0,
        gui_steps=8,
    )
    _task_mixed_summary(
        run_mixed / "task_beta",
        adb_calls=4,
        gui_task_calls=2,
        deeplink_calls=1,
        gui_steps=12,
    )
    _write_run_manifest(
        run_mixed,
        framework_profile="nanobot_opengui",
        evaluation_mode="mixed",
        allow_adb_bypass=True,
        task_names=["task_alpha", "task_beta"],
    )

    _task_artifact_bundle(
        run_standard,
        task_name="task_alpha",
        score=1.0,
        total_tokens=90,
        ttft_ms=80.0,
        tool_success_rate=1.0,
        invalid_action_rate=0.0,
        cost_per_success=0.08,
        judge_agreement=True,
    )
    _task_artifact_bundle(
        run_standard,
        task_name="task_beta",
        score=1.0,
        total_tokens=100,
        ttft_ms=90.0,
        tool_success_rate=0.9,
        invalid_action_rate=0.0,
        cost_per_success=0.09,
        judge_agreement=True,
    )

    report = aggregate_framework_runs(
        framework_runs={"nanobot": str(run_mixed), "openclaw": str(run_standard)},
        success_threshold=0.99,
    )

    assert report["common_tasks"] == ["task_alpha", "task_beta"]
    assert report["framework_modes"]["nanobot"]["evaluation_mode"] == "mixed"
    assert report["framework_modes"]["openclaw"]["evaluation_mode"] == "standard"
    assert report["leaderboards"]["mixed"][0]["framework"] == "nanobot"
    assert report["leaderboards"]["standard"][0]["framework"] == "openclaw"
    assert "lane_metrics" in report["leaderboards"]["mixed"][0]
    assert report["leaderboards"]["mixed"][0]["lane_metrics"]["adb_calls"] == 6
    assert report["leaderboard"][0]["framework"] == "openclaw"
    assert any(
        "mixed leaderboard allows ADB/deeplink/gui_task bypass lanes" in note
        for note in report["comparability_notes"]
    )


def test_conformance_suite_passes_for_valid_artifacts(tmp_path: Path):
    run_root = tmp_path / "run_conformance"
    _task_artifact_bundle(
        run_root,
        task_name="task_gamma",
        score=1.0,
        total_tokens=60,
        ttft_ms=100.0,
        tool_success_rate=1.0,
        invalid_action_rate=0.0,
        cost_per_success=0.05,
        judge_agreement=True,
    )

    report = run_conformance_suite(str(run_root))
    assert report["checked_tasks"] == 1
    assert report["ok"] is True
    assert report["tasks"][0]["ok"] is True


def test_reproducibility_reports_variance_and_judge_agreement(tmp_path: Path):
    run1 = tmp_path / "run1"
    run2 = tmp_path / "run2"
    run3 = tmp_path / "run3"

    _task_artifact_bundle(
        run1,
        task_name="task_delta",
        score=1.0,
        total_tokens=70,
        ttft_ms=101.0,
        tool_success_rate=1.0,
        invalid_action_rate=0.0,
        cost_per_success=0.07,
        judge_agreement=True,
    )
    _task_artifact_bundle(
        run2,
        task_name="task_delta",
        score=0.98,
        total_tokens=68,
        ttft_ms=103.0,
        tool_success_rate=1.0,
        invalid_action_rate=0.0,
        cost_per_success=0.07,
        judge_agreement=True,
    )
    _task_artifact_bundle(
        run3,
        task_name="task_delta",
        score=1.0,
        total_tokens=69,
        ttft_ms=102.0,
        tool_success_rate=1.0,
        invalid_action_rate=0.0,
        cost_per_success=0.07,
        judge_agreement=False,
    )

    report = evaluate_reproducibility(
        run_roots=[str(run1), str(run2), str(run3)],
        variance_threshold=0.001,
        judge_agreement_threshold=0.6,
    )
    assert report["common_tasks"] == ["task_delta"]
    assert report["stability_metrics"]["variance_passed"] is True
    assert report["evaluation_quality"]["judge_agreement_rate"] == 0.666667
    assert report["evaluation_quality"]["agreement_available"] is True
    assert report["evaluation_quality"]["agreement_status"] == "passed"
    assert report["evaluation_quality"]["agreement_passed"] is True
    assert report["gate_summary"]["stability_gate"]["status"] == "passed"
    assert report["gate_summary"]["agreement_gate"]["status"] == "passed"
    assert report["gate_summary"]["overall_status"] == "passed"
    assert report["ok"] is True


def test_benchmark_parser_accepts_phase6_commands():
    parser = create_parser()
    args = parser.parse_args(
        [
            "benchmark",
            "aggregate",
            "--framework-run",
            "nanobot=/tmp/nanobot",
            "--framework-run",
            "openclaw=/tmp/openclaw",
            "--output",
            "/tmp/report.json",
        ]
    )
    assert args.command == "benchmark"
    assert args.benchmark_command == "aggregate"
    assert args.framework_run == ["nanobot=/tmp/nanobot", "openclaw=/tmp/openclaw"]
