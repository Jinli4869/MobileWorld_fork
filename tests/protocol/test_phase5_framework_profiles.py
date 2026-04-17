"""Phase 5 framework expansion and CLI profile tests."""

import asyncio
import json
from pathlib import Path

from mobile_world.agents.registry import create_framework_adapter, list_framework_profiles
from mobile_world.core.api.info import list_framework_profiles_info
from mobile_world.core.cli import create_parser
from mobile_world.core.subcommands import eval as eval_subcommand
from mobile_world.core.subcommands.eval import load_framework_config
from mobile_world.runtime.adapters.hermes_template import HermesTemplateAdapter
from mobile_world.runtime.adapters.openclaw_template import OpenClawTemplateAdapter


def test_framework_templates_are_registered():
    profiles = set(list_framework_profiles())
    assert "nanobot_opengui" in profiles
    assert "openclaw_template" in profiles
    assert "hermes_template" in profiles


def test_create_framework_adapter_for_templates():
    openclaw = create_framework_adapter(
        "openclaw_template",
        model_name="model-x",
        llm_base_url="http://localhost:8080/v1",
    )
    hermes = create_framework_adapter(
        "hermes_template",
        model_name="model-y",
        llm_base_url="http://localhost:8080/v1",
    )
    assert isinstance(openclaw, OpenClawTemplateAdapter)
    assert isinstance(hermes, HermesTemplateAdapter)


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
        ]
    )
    assert args.framework_profile == "nanobot_opengui"
    assert args.framework_config == "framework-profile.json"
    assert args.nanobot_config_path == "/tmp/nanobot.json"
    assert args.gui_claw_path == "/tmp/gui-claw"
    assert args.evaluation_mode == "mixed"
    assert args.allow_adb_bypass is True


def test_framework_inventory_exposes_capabilities_and_conformance():
    infos = list_framework_profiles_info()
    by_name = {item.profile_name: item for item in infos}
    assert "openclaw_template" in by_name
    assert "hermes_template" in by_name
    assert "nanobot_opengui" in by_name
    assert "gui_action" in by_name["openclaw_template"].capabilities
    assert by_name["openclaw_template"].conformance in {"pass", "fail"}


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
            "hermes_template",
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

    manifest_path = tmp_path / "logs" / "run_manifest.json"
    assert manifest_path.exists() is True
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["framework_profile"] == "nanobot_opengui"
    assert manifest["evaluation_mode"] == "mixed"
    assert manifest["allow_adb_bypass"] is True
