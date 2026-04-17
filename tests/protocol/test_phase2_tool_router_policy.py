"""Phase 2 tool router and capability policy tests."""

import json
from pathlib import Path

from mobile_world.runtime.protocol.capability_policy import (
    CapabilityDecision,
    resolve_capability_policy,
)
from mobile_world.runtime.protocol.tool_router import UnifiedToolRouter
from mobile_world.runtime.utils.models import JSONAction
from mobile_world.runtime.utils.trajectory_logger import (
    CANONICAL_LOG_FILE_NAME,
    CANONICAL_META_FILE_NAME,
    LOG_FILE_NAME,
    TrajLogger,
)


class DummyEnv:
    """Simple fake env for router tests."""

    def __init__(self, should_raise: bool = False):
        self.should_raise = should_raise

    def execute_action(self, action):
        if self.should_raise:
            raise RuntimeError("dispatch boom")
        return {"ok": True, "action_type": action.action_type}


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


def test_capability_policy_enablement_by_tags_and_flags():
    decision = resolve_capability_policy(
        task_tags=["agent-mcp"],
        profile_name="qwen3vl",
        enable_mcp=True,
        enable_user_interaction=False,
    )
    assert decision.is_tool_class_enabled("gui")
    assert decision.is_tool_class_enabled("mcp")
    assert not decision.is_tool_class_enabled("ask_user")

    decision_no_mcp_tag = resolve_capability_policy(
        task_tags=[],
        profile_name="qwen3vl",
        enable_mcp=True,
        enable_user_interaction=False,
    )
    assert not decision_no_mcp_tag.is_tool_class_enabled("mcp")


def test_router_denies_disabled_tool_class():
    decision = CapabilityDecision(
        enabled_tool_classes=["gui"],
        enabled_mcp_tools=[],
        mcp_timeout_seconds=120,
        source="test",
        task_tags=[],
        profile_name="unit",
    )
    router = UnifiedToolRouter(decision)
    action = JSONAction(action_type="mcp", action_name="mcp_demo", action_json={})
    result = router.dispatch(DummyEnv(), action)
    assert result.ok is False
    assert result.error.code == "CAPABILITY_DENIED"


def test_router_denies_non_allowlisted_mcp_tool():
    decision = CapabilityDecision(
        enabled_tool_classes=["gui", "mcp"],
        enabled_mcp_tools=["allowed_*"],
        mcp_timeout_seconds=60,
        source="test",
        task_tags=["agent-mcp"],
        profile_name="unit",
    )
    router = UnifiedToolRouter(decision)
    action = JSONAction(action_type="mcp", action_name="blocked_tool", action_json={})
    result = router.dispatch(DummyEnv(), action)
    assert result.ok is False
    assert result.error.code == "MCP_TOOL_NOT_ALLOWLISTED"


def test_router_normalizes_execution_error():
    decision = CapabilityDecision(
        enabled_tool_classes=["gui"],
        enabled_mcp_tools=[],
        mcp_timeout_seconds=120,
        source="test",
        task_tags=[],
        profile_name="unit",
    )
    router = UnifiedToolRouter(decision)
    action = JSONAction(action_type="wait")
    result = router.dispatch(DummyEnv(should_raise=True), action)
    assert result.ok is False
    assert result.error.code == "TOOL_EXECUTION_ERROR"
    assert result.error.details["exception_type"] == "RuntimeError"


def test_tool_and_policy_manifest_and_error_logged_to_artifacts(tmp_path: Path):
    traj_logger = TrajLogger(str(tmp_path), "task_beta")
    manifest = {
        "enabled_tool_classes": ["gui"],
        "enabled_mcp_tools": [],
        "mcp_timeout_seconds": 120,
        "source": "policy:test",
    }
    traj_logger.log_tool_manifest(manifest)
    traj_logger.log_policy_manifest(manifest)
    traj_logger.log_tool_error(step=3, error={"code": "CAPABILITY_DENIED", "message": "denied"})

    task_dir = tmp_path / "task_beta"
    legacy = _read_json(task_dir / LOG_FILE_NAME)
    canonical_meta = _read_json(task_dir / CANONICAL_META_FILE_NAME)
    canonical_events = _read_jsonl(task_dir / CANONICAL_LOG_FILE_NAME)

    assert legacy["0"]["tool_manifest"]["source"] == "policy:test"
    assert legacy["0"]["policy_manifest"]["source"] == "policy:test"
    assert canonical_meta["tool_manifest"]["mcp_timeout_seconds"] == 120
    assert canonical_meta["policy_manifest"]["mcp_timeout_seconds"] == 120
    assert canonical_events[-1]["type"] == "tool_error"
    assert canonical_events[-1]["error"]["code"] == "CAPABILITY_DENIED"
