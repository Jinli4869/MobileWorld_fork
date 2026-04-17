"""Phase 8 framework-profile policy flow protocol tests."""

import asyncio
import json
from pathlib import Path
from queue import Queue

from mobile_world.core.cli import create_parser
from mobile_world.core.subcommands import eval as eval_subcommand
from mobile_world.core import runner as runner_module
from mobile_world.runtime.protocol.capability_policy import CapabilityDecision
from mobile_world.runtime.utils.trajectory_logger import CANONICAL_META_FILE_NAME, LOG_FILE_NAME

# Canonical Phase 8 verification command used by plan and validation artifacts.
PHASE8_COMBINED_REGRESSION_CMD = (
    "UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase8_framework_profile_policy_flow.py tests/protocol/test_phase5_framework_profiles.py"
)


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


def test_policy_manifest_profile_name_matches_effective_profile(monkeypatch, tmp_path: Path):
    _run_process_task(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        task_name="task_phase8_framework_manifest",
        framework_profile="nanobot_opengui",
    )
    _run_process_task(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        task_name="task_phase8_builtin_manifest",
        framework_profile=None,
    )

    framework_task_dir = tmp_path / "task_phase8_framework_manifest"
    builtin_task_dir = tmp_path / "task_phase8_builtin_manifest"

    framework_legacy = _read_json(framework_task_dir / LOG_FILE_NAME)
    framework_meta = _read_json(framework_task_dir / CANONICAL_META_FILE_NAME)
    builtin_legacy = _read_json(builtin_task_dir / LOG_FILE_NAME)
    builtin_meta = _read_json(builtin_task_dir / CANONICAL_META_FILE_NAME)

    assert framework_legacy["0"]["policy_manifest"]["profile_name"] == "nanobot_opengui"
    assert framework_meta["policy_manifest"]["profile_name"] == "nanobot_opengui"
    assert builtin_legacy["0"]["policy_manifest"]["profile_name"] == "qwen3vl"
    assert builtin_meta["policy_manifest"]["profile_name"] == "qwen3vl"


def test_eval_framework_profile_flow_preserves_profile_semantics(monkeypatch, tmp_path: Path):
    captured_kwargs: dict = {}

    def _fake_run_agent_with_evaluation(**kwargs):
        captured_kwargs.update(kwargs)
        return [], []

    monkeypatch.setattr(eval_subcommand, "run_agent_with_evaluation", _fake_run_agent_with_evaluation)

    parser = create_parser()
    args = parser.parse_args(
        [
            "eval",
            "--agent-type",
            "qwen3vl",
            "--framework-profile",
            "nanobot_opengui",
            "--output",
            str(tmp_path / "logs"),
        ]
    )

    asyncio.run(eval_subcommand.execute(args))

    assert captured_kwargs["framework_profile"] == "nanobot_opengui"
    assert captured_kwargs["agent_type"] == "qwen3vl"
