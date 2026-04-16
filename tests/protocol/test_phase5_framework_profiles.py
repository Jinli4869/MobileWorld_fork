"""Phase 5 framework expansion and CLI profile tests."""

import json

from mobile_world.agents.registry import create_framework_adapter, list_framework_profiles
from mobile_world.core.api.info import list_framework_profiles_info
from mobile_world.core.cli import create_parser
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
                "judge_model": "qwen3-vl-plus",
            }
        ),
        encoding="utf-8",
    )
    payload = load_framework_config(str(config_path))
    assert payload["framework_profile"] == "nanobot_opengui"
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
        ]
    )
    assert args.framework_profile == "nanobot_opengui"
    assert args.framework_config == "framework-profile.json"


def test_framework_inventory_exposes_capabilities_and_conformance():
    infos = list_framework_profiles_info()
    by_name = {item.profile_name: item for item in infos}
    assert "openclaw_template" in by_name
    assert "hermes_template" in by_name
    assert "nanobot_opengui" in by_name
    assert "gui_action" in by_name["openclaw_template"].capabilities
    assert by_name["openclaw_template"].conformance in {"pass", "fail"}
