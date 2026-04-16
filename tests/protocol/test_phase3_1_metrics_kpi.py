"""Phase 3.1 metrics instrumentation protocol tests."""

import json
from pathlib import Path

from PIL import Image

from mobile_world.runtime.protocol.metrics import MetricsCollector
from mobile_world.runtime.utils.models import Observation
from mobile_world.runtime.utils.trajectory_logger import (
    CANONICAL_LOG_FILE_NAME,
    CANONICAL_META_FILE_NAME,
    LOG_FILE_NAME,
    METRICS_FILE_NAME,
    TrajLogger,
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def test_metrics_collector_computes_kpis_with_ttft_fallback():
    collector = MetricsCollector(task_name="task_kpi", run_id="task_kpi-0", task_started_at=10.0)

    # Step 1: no token deltas, TTFT should still fallback to predict wall-clock latency.
    step1_preview = collector.preview_step(
        step=1,
        action_type="click",
        step_started_at=10.0,
        prediction_done_at=10.2,
        total_usage={"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0, "total_tokens": 0},
    )
    collector.complete_step(
        step_preview=step1_preview,
        step_finished_at=10.5,
        tool_latency_ms=120.0,
        tool_attempted=True,
        tool_success=True,
        tool_retry=False,
        invalid_action=False,
    )

    # Step 2: token deltas become available.
    step2_preview = collector.preview_step(
        step=2,
        action_type="unknown",
        step_started_at=11.0,
        prediction_done_at=11.3,
        total_usage={
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "cached_tokens": 1,
            "total_tokens": 14,
        },
    )
    collector.complete_step(
        step_preview=step2_preview,
        step_finished_at=11.35,
        tool_latency_ms=None,
        tool_attempted=False,
        tool_success=False,
        tool_retry=False,
        invalid_action=True,
    )

    summary, event = collector.finalize(score_recorded_at=12.0)

    assert summary["quality_flags"]["latency"] == "estimated"
    assert summary["quality_flags"]["token_usage"] == "native"
    assert summary["token_usage"]["avg_total_tokens_per_step"] == 7.0
    assert summary["latency"]["ttft_ms"] == 200.0
    assert summary["latency"]["ttft_source"] == "estimated_from_predict_latency"
    assert summary["reliability"]["tool_success_rate"] == 1.0
    assert summary["reliability"]["invalid_action_rate"] == 0.5

    event_obj = event.model_dump()
    assert event_obj["type"] == "metrics"
    assert event_obj["latency"]["ttft_source"] == "estimated_from_predict_latency"
    assert event_obj["quality_flags"]["token_usage"] == "native"


def test_traj_logger_persists_metrics_events_and_summary(tmp_path: Path):
    traj_logger = TrajLogger(str(tmp_path), "task_metrics")

    screenshot = Image.new("RGB", (24, 24), color="white")
    obs = Observation(screenshot=screenshot, ask_user_response=None, tool_call=None)
    traj_logger.log_traj(
        task_name="task_metrics",
        task_goal="collect metrics",
        step=1,
        prediction="do something",
        action={"action_type": "click", "x": 5, "y": 6},
        obs=obs,
        token_usage={"prompt_tokens": 2, "completion_tokens": 1, "cached_tokens": 0, "total_tokens": 3},
        step_info={"predict_latency_ms": 100.0},
    )
    traj_logger.log_metrics_event(
        step=1,
        metrics={"step_latency_ms": 180.0, "tool_latency_ms": 50.0, "invalid_action": False},
    )
    traj_logger.log_run_kpi_summary(
        task_name="task_metrics",
        run_id="task_metrics-0",
        summary={
            "quality_flags": {"token_usage": "native", "latency": "estimated", "cost": "unavailable"},
            "token_usage": {"avg_total_tokens_per_step": 3.0},
            "latency": {"ttft_ms": 100.0, "step_latency_ms": {"p50": 180.0, "p95": 180.0}},
            "reliability": {"tool_success_rate": 1.0, "tool_retry_rate": 0.0, "invalid_action_rate": 0.0},
            "cost": {"cost_per_success": None, "source": "unavailable"},
        },
    )

    task_dir = tmp_path / "task_metrics"
    legacy = _read_json(task_dir / LOG_FILE_NAME)
    meta = _read_json(task_dir / CANONICAL_META_FILE_NAME)
    events = _read_jsonl(task_dir / CANONICAL_LOG_FILE_NAME)
    summary = _read_json(task_dir / METRICS_FILE_NAME)

    assert legacy["0"]["traj"][0]["step_info"]["step_latency_ms"] == 180.0
    assert legacy["0"]["metrics_summary"]["quality_flags"]["latency"] == "estimated"
    assert meta["metrics_summary"]["token_usage"]["avg_total_tokens_per_step"] == 3.0
    assert summary["reliability"]["tool_success_rate"] == 1.0
    assert any(event["type"] == "metrics_step" for event in events)
    assert any(event["type"] == "metrics" for event in events)
