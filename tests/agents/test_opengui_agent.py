from __future__ import annotations

import json

from PIL import Image

from mobile_world.agents.implementations.opengui import (
    OpenGUIDefaultAgentMCP,
    OpenGUITurn,
    parse_opengui_response,
)
from mobile_world.agents.registry import AGENT_CONFIGS
from mobile_world.runtime.utils.models import JSONAction


def _agent(monkeypatch) -> OpenGUIDefaultAgentMCP:
    monkeypatch.setattr(OpenGUIDefaultAgentMCP, "build_openai_client", lambda self, *_: None)
    agent = OpenGUIDefaultAgentMCP(
        model_name="test-model",
        llm_base_url="http://127.0.0.1/v1",
        api_key="empty",
        tools=[],
    )
    agent.initialize("finish the task")
    return agent


def test_parse_opengui_response_keeps_intent_summary_out_of_action() -> None:
    raw = json.dumps(
        {
            "action_type": "tap",
            "coordinate": [500, 250],
            "intent": "Open the search field.",
            "summary": "The app is on the home page.",
        }
    )

    action, intent, summary = parse_opengui_response(
        raw,
        image_width=200,
        image_height=400,
        scale_factor=1000,
    )

    assert action == {"action_type": "click", "x": 100, "y": 100}
    assert intent == "Open the search field."
    assert summary == "The app is on the home page."
    assert JSONAction(**action).action_type == "click"


def test_prompt_uses_recent_intents_and_latest_summary(monkeypatch) -> None:
    agent = _agent(monkeypatch)
    for index in range(10):
        agent.turns.append(
            OpenGUITurn(
                action={"action_type": "wait"},
                intent=f"intent-{index}",
                summary=f"summary-{index}",
                raw_response="{}",
            )
        )

    messages = agent._build_messages(Image.new("RGB", (32, 64)), None, None)
    system_text = messages[0]["content"]

    assert "intent-1" not in system_text
    assert "intent-2" in system_text
    assert "intent-9" in system_text
    assert "summary-9" in system_text
    assert "summary-8" not in system_text


def test_predict_records_intent_summary_and_returns_action(monkeypatch) -> None:
    agent = _agent(monkeypatch)
    agent.openai_chat_completions_create = lambda **_: json.dumps(
        {
            "action_type": "done",
            "intent": "Stop because the requested state is reached.",
            "summary": "The task is complete.",
        }
    )

    raw, action = agent.predict({"screenshot": Image.new("RGB", (100, 200))})

    assert "task is complete" in raw
    assert action == JSONAction(action_type="answer", text="The task is complete.")
    assert agent.turns[-1].intent == "Stop because the requested state is reached."
    assert agent.turns[-1].summary == "The task is complete."


def test_registry_exposes_opengui_agent_type() -> None:
    assert AGENT_CONFIGS["opengui"]["class"] is OpenGUIDefaultAgentMCP
