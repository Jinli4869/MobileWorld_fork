"""Phase 8 framework-profile policy flow protocol tests."""

import json
from pathlib import Path
from queue import Queue

from mobile_world.core import runner as runner_module
from mobile_world.runtime.protocol.capability_policy import CapabilityDecision


class DummyEnv:
    """Minimal env stub for _process_task_on_env tests."""

    base_url = "http://127.0.0.1:9999"

    def __init__(self, task_tags: list[str] | None = None):
        self._task_tags = task_tags or []

    def get_task_metadata(self, task_type: str) -> dict:
        _ = task_type
        return {"tags": list(self._task_tags)}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_process_task(
    *,
    monkeypatch,
    tmp_path: Path,
    task_name: str,
    framework_profile: str | None,
    captured_profiles: list[str] | None = None,
    task_tags: list[str] | None = None,
) -> dict:
    env_queue: Queue = Queue(maxsize=1)
    env_queue.put((DummyEnv(task_tags=task_tags), "container-1"))

    def _fake_resolve(
        *,
        task_tags: list[str],
        profile_name: str,
        enable_mcp: bool,
        enable_user_interaction: bool,
        policy_path: str | None = None,
        mcp_allowlist_override: list[str] | None = None,
    ) -> CapabilityDecision:
        _ = enable_mcp, enable_user_interaction, policy_path, mcp_allowlist_override
        if captured_profiles is not None:
            captured_profiles.append(profile_name)
        return CapabilityDecision(
            enabled_tool_classes=["gui"],
            enabled_mcp_tools=[],
            mcp_timeout_seconds=120,
            source="test:phase8",
            task_tags=task_tags,
            profile_name=profile_name,
        )

    monkeypatch.setattr(runner_module, "resolve_capability_policy", _fake_resolve)
    monkeypatch.setattr(runner_module, "create_agent", lambda *args, **kwargs: object())
    monkeypatch.setattr(runner_module, "create_framework_adapter", lambda *args, **kwargs: object())
    monkeypatch.setattr(runner_module, "create_evaluator", lambda *args, **kwargs: object())
    monkeypatch.setattr(runner_module, "_execute_single_task", lambda *args, **kwargs: (1, 1.0))

    return runner_module._process_task_on_env(
        task_name=task_name,
        env_queue=env_queue,
        agent_type="qwen3vl",
        model_name="qwen3-vl-plus",
        llm_base_url="http://localhost:8080/v1",
        api_key=None,
        log_file_root=str(tmp_path),
        max_step=1,
        enable_mcp=False,
        enable_user_interaction=False,
        framework_profile=framework_profile,
        nanobot_fork_path=None,
    )


def test_runner_uses_framework_profile_for_policy_resolution(monkeypatch, tmp_path: Path):
    captured_profiles: list[str] = []
    result = _run_process_task(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        task_name="task_phase8_framework_mode",
        framework_profile="nanobot_opengui",
        captured_profiles=captured_profiles,
    )

    assert result["task_name"] == "task_phase8_framework_mode"
    assert result["score"] == 1.0
    assert captured_profiles == ["nanobot_opengui"]
