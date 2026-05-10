from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from loguru import logger

from mobile_world.agents.base import MCPAgent
from mobile_world.agents.utils.helpers import pil_to_base64
from mobile_world.runtime.utils.models import JSONAction
from mobile_world.runtime.utils.parsers import parse_json_markdown

OPENGUI_DEFAULT_PROMPT = """You are an OpenGUI-style mobile GUI agent.

Goal:
{goal}

Available tools:
{tools}

Return exactly one JSON object with:
- action_type: the next executable action
- intent: why this action is the right next step now
- summary: the current observed state and task completion progress

Use concise intent and summary strings. For coordinates, use a 0-{max_coordinate}
relative grid as [x, y]. Do not include screenshot resolution in the answer.

Valid action_type values include:
tap, long_press, double_tap, input_text, scroll, swipe, drag, open_app,
back, home, enter, wait, ask_user, answer, done.

Recent intents:
{recent_intents}

Latest state summary:
{latest_summary}
"""

_ACTION_TYPE_ALIASES = {
    "tap": "click",
    "touch": "click",
    "press": "click",
    "type": "input_text",
    "enter_text": "input_text",
    "write": "input_text",
    "back": "navigate_back",
    "home": "navigate_home",
    "enter": "keyboard_enter",
    "done": "answer",
    "complete": "answer",
}


@dataclass
class OpenGUITurn:
    action: dict[str, Any]
    intent: str
    summary: str
    raw_response: str


def _scale_pair(
    coordinate: Any,
    image_width: int,
    image_height: int,
    scale_factor: int | tuple[int, int],
) -> tuple[int, int]:
    if not isinstance(coordinate, list | tuple) or len(coordinate) != 2:
        raise ValueError(f"Invalid coordinate: {coordinate}")

    scale_x, scale_y = (
        (scale_factor, scale_factor) if isinstance(scale_factor, int) else scale_factor
    )
    return (
        round(float(coordinate[0]) * image_width / scale_x),
        round(float(coordinate[1]) * image_height / scale_y),
    )


def _normalize_action_type(action_type: Any) -> str:
    if not isinstance(action_type, str) or not action_type.strip():
        raise ValueError("action_type is required")
    normalized = action_type.strip().lower().replace(" ", "_")
    return _ACTION_TYPE_ALIASES.get(normalized, normalized)


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _text_field(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return str(value)
    return ""


def _coordinate_action(
    action_type: str,
    payload: dict[str, Any],
    image_width: int,
    image_height: int,
    scale_factor: int | tuple[int, int],
) -> dict[str, Any]:
    if "x" in payload and "y" in payload:
        return {"action_type": action_type, "x": round(payload["x"]), "y": round(payload["y"])}

    x, y = _scale_pair(
        payload.get("coordinate") or payload.get("coordinates"),
        image_width,
        image_height,
        scale_factor,
    )
    return {"action_type": action_type, "x": x, "y": y}


def _line_action(
    action_type: str,
    payload: dict[str, Any],
    image_width: int,
    image_height: int,
    scale_factor: int | tuple[int, int],
) -> dict[str, Any]:
    start = payload.get("start_coordinate") or payload.get("start") or payload.get("coordinate")
    end = payload.get("end_coordinate") or payload.get("end") or payload.get("coordinate2")
    start_x, start_y = _scale_pair(start, image_width, image_height, scale_factor)
    end_x, end_y = _scale_pair(end, image_width, image_height, scale_factor)
    return {
        "action_type": action_type,
        "start_x": start_x,
        "start_y": start_y,
        "end_x": end_x,
        "end_y": end_y,
    }


def parse_opengui_response(
    response: str,
    image_width: int,
    image_height: int,
    scale_factor: int | tuple[int, int] = 1000,
) -> tuple[dict[str, Any], str, str]:
    payload = parse_json_markdown(response)
    if not isinstance(payload, dict):
        raise ValueError("OpenGUI response must be a JSON object")

    intent = _required_text(payload, "intent")
    summary = _required_text(payload, "summary")
    action_type = _normalize_action_type(payload.get("action_type") or payload.get("action"))

    if action_type in {"click", "double_tap", "long_press"}:
        action = _coordinate_action(action_type, payload, image_width, image_height, scale_factor)
    elif action_type in {"drag", "swipe"}:
        action = _line_action(action_type, payload, image_width, image_height, scale_factor)
    elif action_type == "input_text":
        action = {"action_type": "input_text", "text": _text_field(payload, "text", "content")}
    elif action_type == "scroll":
        action = {"action_type": "scroll", "direction": _text_field(payload, "direction") or "down"}
    elif action_type == "open_app":
        action = {"action_type": "open_app", "app_name": _text_field(payload, "app_name", "text")}
    elif action_type in {"navigate_back", "navigate_home", "keyboard_enter", "wait"}:
        action = {"action_type": action_type}
    elif action_type == "ask_user":
        action = {"action_type": "ask_user", "text": _text_field(payload, "text", "question")}
    elif action_type == "answer":
        action = {"action_type": "answer", "text": _text_field(payload, "text", "answer") or summary}
    elif action_type == "status":
        text = summary if payload.get("goal_status") == "complete" else "task failed"
        action = {"action_type": "answer", "text": text}
    else:
        action = {"action_type": "unknown", "text": f"Unsupported action_type: {action_type}"}

    return action, intent, summary


class OpenGUIDefaultAgentMCP(MCPAgent):
    def __init__(
        self,
        model_name: str,
        llm_base_url: str,
        api_key: str = "empty",
        observation_type: str = "screenshot",
        runtime_conf: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        scale_factor: int | tuple[int, int] = 1000,
        **kwargs: Any,
    ) -> None:
        super().__init__(tools=tools or [], **kwargs)
        self.model_name = model_name
        self.llm_base_url = llm_base_url
        self.api_key = api_key
        self.observation_type = observation_type
        self.scale_factor = scale_factor
        self.runtime_conf = {"temperature": 0.0, "max_tokens": 2048}
        self.runtime_conf.update(runtime_conf or {})
        self.intent_history_window = int(self.runtime_conf.pop("intent_history_window", 8))
        self.runtime_conf.pop("history_n_images", None)
        self.turns: list[OpenGUITurn] = []

        self.build_openai_client(self.llm_base_url, self.api_key)

    def initialize_hook(self, instruction: str) -> None:
        self.reset()

    def _format_recent_intents(self) -> str:
        recent = self.turns[-self.intent_history_window :]
        if not recent:
            return "(none)"
        return "\n".join(f"{index + 1}. {turn.intent}" for index, turn in enumerate(recent))

    def _latest_summary(self) -> str:
        return self.turns[-1].summary if self.turns else "(none)"

    def _build_messages(
        self,
        screenshot: Any,
        tool_call: Any,
        ask_user_response: Any,
    ) -> list[dict[str, Any]]:
        max_coordinate = self.scale_factor - 1 if isinstance(self.scale_factor, int) else "999"
        system_prompt = OPENGUI_DEFAULT_PROMPT.format(
            goal=self.instruction,
            tools="\n".join(json.dumps(tool, ensure_ascii=False) for tool in self.tools) or "(none)",
            max_coordinate=max_coordinate,
            recent_intents=self._format_recent_intents(),
            latest_summary=self._latest_summary(),
        )
        user_content: list[dict[str, Any]] = []
        if tool_call is not None:
            user_content.append({"type": "text", "text": f"Tool result: {tool_call}"})
        if ask_user_response is not None:
            user_content.append({"type": "text", "text": f"User response: {ask_user_response}"})
        encoded = pil_to_base64(screenshot)
        user_content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

    def predict(self, observation: dict[str, Any]) -> tuple[str, JSONAction]:
        screenshot = observation["screenshot"]
        image_width, image_height = screenshot.size
        messages = self._build_messages(
            screenshot,
            observation.get("tool_call"),
            observation.get("ask_user_response"),
        )

        response = None
        for attempt in range(3):
            response = self.openai_chat_completions_create(
                model=self.model_name,
                messages=messages,
                retry_times=1,
                **self.runtime_conf,
            )
            if response is not None:
                break
            logger.warning("OpenGUI agent LLM call failed, retrying ({}/3)", attempt + 1)
            time.sleep(1)

        if response is None:
            return "Agent LLM failed", JSONAction(action_type="unknown", text="Agent LLM failed")

        try:
            action, intent, summary = parse_opengui_response(
                response,
                image_width=image_width,
                image_height=image_height,
                scale_factor=self.scale_factor,
            )
            json_action = JSONAction(**action)
        except Exception as exc:
            logger.error(f"Error parsing OpenGUI response: {exc}")
            return response, JSONAction(action_type="unknown", text=str(exc))

        self.turns.append(
            OpenGUITurn(action=json_action.model_dump(exclude_none=True), intent=intent, summary=summary, raw_response=response)
        )
        return response, json_action

    def reset(self) -> None:
        self.turns = []
