"""Canonical trajectory artifact contract tests."""

import json
from pathlib import Path

from PIL import Image

from mobile_world.runtime.utils.models import Observation
from mobile_world.runtime.utils.trajectory_logger import (
    CANONICAL_LOG_FILE_NAME,
    CANONICAL_META_FILE_NAME,
    LOG_FILE_NAME,
    SCORE_FILE_NAME,
    TrajLogger,
)


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def test_trajectory_logger_writes_legacy_and_canonical_artifacts(tmp_path: Path):
    logger = TrajLogger(str(tmp_path), "task_alpha")
    logger.log_tools([{"name": "mcp_demo", "inputSchema": {"type": "object"}}])

    screenshot = Image.new("RGB", (32, 32), color="white")
    obs = Observation(
        screenshot=screenshot,
        ask_user_response="approved",
        tool_call={"name": "mcp_demo", "result": "ok"},
    )
    action = {"action_type": "click", "x": 12, "y": 20}
    token_usage = {
        "prompt_tokens": 5,
        "completion_tokens": 3,
        "cached_tokens": 1,
        "total_tokens": 8,
    }

    logger.log_traj(
        task_name="task_alpha",
        task_goal="click target",
        step=1,
        prediction="tap the target",
        action=action,
        obs=obs,
        token_usage=token_usage,
    )
    logger.log_score(score=1.0, reason="task completed")

    task_dir = tmp_path / "task_alpha"
    legacy_path = task_dir / LOG_FILE_NAME
    canonical_jsonl_path = task_dir / CANONICAL_LOG_FILE_NAME
    canonical_meta_path = task_dir / CANONICAL_META_FILE_NAME
    score_path = task_dir / SCORE_FILE_NAME

    assert legacy_path.exists()
    assert canonical_jsonl_path.exists()
    assert canonical_meta_path.exists()
    assert score_path.exists()

    legacy_obj = json.loads(legacy_path.read_text(encoding="utf-8"))
    assert "0" in legacy_obj
    assert legacy_obj["0"]["traj"][0]["action"]["action_type"] == "click"
    assert legacy_obj["0"]["token_usage"]["total_tokens"] == 8

    canonical_meta = json.loads(canonical_meta_path.read_text(encoding="utf-8"))
    assert canonical_meta["type"] == "header"
    assert canonical_meta["schema_version"] == "1.0.0"
    assert canonical_meta["task_name"] == "task_alpha"
    assert canonical_meta["tools"][0]["name"] == "mcp_demo"

    events = _load_jsonl(canonical_jsonl_path)
    assert len(events) == 2
    step_event = events[0]
    score_event = events[1]

    assert step_event["type"] == "step"
    assert step_event["schema_version"] == "1.0.0"
    assert step_event["task_name"] == "task_alpha"
    assert step_event["action_type"] == "click"
    assert step_event["token_usage"]["total_tokens"] == 8
    assert step_event["tool_call"]["name"] == "mcp_demo"

    assert score_event["type"] == "score"
    assert score_event["schema_version"] == "1.0.0"
    assert score_event["score"] == 1.0
