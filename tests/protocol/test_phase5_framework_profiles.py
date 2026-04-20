"""Phase 5 framework expansion and CLI profile tests."""

import asyncio
import json
from pathlib import Path

from mobile_world.agents.registry import create_framework_adapter, list_framework_profiles
from mobile_world.core.api.info import list_framework_profiles_info
from mobile_world.core.cli import create_parser
from mobile_world.core.subcommands import eval as eval_subcommand
from mobile_world.core.subcommands.eval import load_framework_config


def test_framework_profile_registry_contains_nanobot_profile():
    profiles = set(list_framework_profiles())
    assert "nanobot_opengui" in profiles


def test_create_framework_adapter_for_nanobot_profile(tmp_path: Path):
    nanobot_fork = tmp_path / "nanobot_fork"
    nanobot_fork.mkdir(parents=True)
    nanobot_config = tmp_path / "nanobot-config.json"
    nanobot_config.write_text(
        json.dumps({"provider": {"model": "qwen"}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    adapter = create_framework_adapter(
        "nanobot_opengui",
        model_name="model-y",
        llm_base_url="http://localhost:8080/v1",
        nanobot_fork_path=str(nanobot_fork),
        nanobot_config_path=str(nanobot_config),
        gui_claw_path=str(tmp_path),
        evaluation_mode="mixed",
        allow_adb_bypass=True,
    )
    assert adapter.__class__.__name__ == "NanobotOpenGUIAdapter"


def test_eval_framework_config_loader(tmp_path):
    config_path = tmp_path / "framework-config.json"
    config_path.write_text(
        json.dumps(
            {
                "framework_profile": "nanobot_opengui",
                "nanobot_fork_path": "~/Project/nanobot_fork",
                "nanobot_config_path": "/tmp/nanobot-config.json",
                "gui_claw_path": "/tmp/gui-claw",
                "evaluation_mode": "mixed",
                "allow_adb_bypass": True,
                "nanobot_timeout_seconds": 420,
                "nanobot_enable_planner": False,
                "nanobot_enable_router": True,
                "env_auto_recover": True,
                "env_recover_unhealthy_threshold": 3,
                "judge_model": "qwen3-vl-plus",
            }
        ),
        encoding="utf-8",
    )
    payload = load_framework_config(str(config_path))
    assert payload["framework_profile"] == "nanobot_opengui"
    assert payload["nanobot_config_path"] == "/tmp/nanobot-config.json"
    assert payload["evaluation_mode"] == "mixed"
    assert payload["allow_adb_bypass"] is True
    assert payload["nanobot_timeout_seconds"] == 420
    assert payload["nanobot_enable_planner"] is False
    assert payload["nanobot_enable_router"] is True
    assert payload["env_auto_recover"] is True
    assert payload["env_recover_unhealthy_threshold"] == 3
    assert payload["judge_model"] == "qwen3-vl-plus"


def test_eval_parser_accepts_framework_profile_flags():
    parser = create_parser()
    args = parser.parse_args(
        [
            "eval",
            "--agent-type",
            "qwen3vl",
            "--framework-profile",
            "nanobot_opengui",
            "--framework-config",
            "framework-profile.json",
            "--nanobot-config-path",
            "/tmp/nanobot.json",
            "--gui-claw-path",
            "/tmp/gui-claw",
            "--evaluation-mode",
            "mixed",
            "--allow-adb-bypass",
            "--nanobot-timeout-seconds",
            "420",
            "--no-nanobot-enable-planner",
            "--nanobot-enable-router",
            "--env-auto-recover",
            "--env-recover-unhealthy-threshold",
            "3",
        ]
    )
    assert args.framework_profile == "nanobot_opengui"
    assert args.framework_config == "framework-profile.json"
    assert args.nanobot_config_path == "/tmp/nanobot.json"
    assert args.gui_claw_path == "/tmp/gui-claw"
    assert args.evaluation_mode == "mixed"
    assert args.allow_adb_bypass is True
    assert args.nanobot_timeout_seconds == 420
    assert args.nanobot_enable_planner is False
    assert args.nanobot_enable_router is True
    assert args.env_auto_recover is True
    assert args.env_recover_unhealthy_threshold == 3


def test_framework_inventory_exposes_capabilities_and_conformance():
    infos = list_framework_profiles_info()
    by_name = {item.profile_name: item for item in infos}
    assert "nanobot_opengui" in by_name
    assert "gui_action" in by_name["nanobot_opengui"].capabilities
    assert by_name["nanobot_opengui"].conformance in {"pass", "fail"}


def test_eval_framework_config_profile_selection_is_deterministic(monkeypatch, tmp_path: Path):
    captured_kwargs: dict = {}

    def _fake_run_agent_with_evaluation(**kwargs):
        captured_kwargs.update(kwargs)
        return [], []

    monkeypatch.setattr(eval_subcommand, "run_agent_with_evaluation", _fake_run_agent_with_evaluation)

    nanobot_config = tmp_path / "nanobot-config.json"
    nanobot_config.write_text(json.dumps({"gui": {"backend": "adb"}}, ensure_ascii=False, indent=2), encoding="utf-8")

    config_path = tmp_path / "framework-config.json"
    config_path.write_text(
        json.dumps(
            {
                "framework_profile": "nanobot_opengui",
                "nanobot_config_path": str(nanobot_config),
                "gui_claw_path": str(tmp_path),
                "evaluation_mode": "mixed",
                "allow_adb_bypass": True,
                "nanobot_timeout_seconds": 420,
                "nanobot_enable_planner": False,
                "nanobot_enable_router": True,
                "env_auto_recover": True,
                "env_recover_unhealthy_threshold": 3,
                "judge_model": "qwen3-vl-plus",
            }
        ),
        encoding="utf-8",
    )

    parser = create_parser()
    args = parser.parse_args(
        [
            "eval",
            "--agent-type",
            "qwen3vl",
            "--framework-profile",
            "qwen3vl",
            "--framework-config",
            str(config_path),
            "--output",
            str(tmp_path / "logs"),
        ]
    )

    asyncio.run(eval_subcommand.execute(args))

    assert captured_kwargs["framework_profile"] == "nanobot_opengui"
    assert captured_kwargs["agent_type"] == "qwen3vl"
    assert captured_kwargs["nanobot_config_path"] == str(nanobot_config)
    assert captured_kwargs["gui_claw_path"] == str(tmp_path)
    assert captured_kwargs["evaluation_mode"] == "mixed"
    assert captured_kwargs["allow_adb_bypass"] is True
    assert captured_kwargs["nanobot_timeout_seconds"] == 420
    assert captured_kwargs["nanobot_enable_planner"] is False
    # Router is forced off when planner is off.
    assert captured_kwargs["nanobot_enable_router"] is False
    assert captured_kwargs["env_auto_recover"] is True
    assert captured_kwargs["env_recover_unhealthy_threshold"] == 3

    manifest_path = tmp_path / "logs" / "run_manifest.json"
    assert manifest_path.exists() is True
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["framework_profile"] == "nanobot_opengui"
    assert manifest["evaluation_mode"] == "mixed"
    assert manifest["allow_adb_bypass"] is True
    assert manifest["nanobot_timeout_seconds"] == 420
    assert manifest["nanobot_enable_planner"] is False
    assert manifest["nanobot_enable_router"] is False
    assert manifest["env_auto_recover"] is True
    assert manifest["env_recover_unhealthy_threshold"] == 3
