"""Normalization helpers from legacy runtime payloads to canonical protocol events."""

from __future__ import annotations

import json
from typing import Any

from mobile_world.runtime.protocol.events import (
    CanonicalMetricsEvent,
    CanonicalScoreEvent,
    CanonicalStepEvent,
    MetricsQualityFlags,
)


def _ensure_json_serializable(value: Any) -> Any:
    """Best-effort conversion to a JSON-serializable value."""
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(k): _ensure_json_serializable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_ensure_json_serializable(v) for v in value]
        if hasattr(value, "model_dump"):
            return _ensure_json_serializable(value.model_dump())
        return str(value)


def normalize_action(action: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize legacy action payload to canonical serializable dictionary."""
    if not action:
        return {}
    return _ensure_json_serializable(action)


def normalize_observation(observation: Any) -> dict[str, Any]:
    """Normalize observation carrier for canonical event fields."""
    if observation is None:
        return {"ask_user_response": None, "tool_call": None}
    ask_user_response = getattr(observation, "ask_user_response", None)
    tool_call = getattr(observation, "tool_call", None)
    return {
        "ask_user_response": ask_user_response,
        "tool_call": _ensure_json_serializable(tool_call),
    }


def normalize_step_event(
    *,
    task_name: str,
    task_goal: str,
    run_id: str,
    step: int,
    prediction: str | None,
    action: dict[str, Any] | None,
    observation: Any,
    token_usage: dict[str, int] | None,
    info: dict[str, Any] | None = None,
) -> CanonicalStepEvent:
    """Create canonical step event from legacy runtime payloads."""
    normalized_action = normalize_action(action)
    normalized_obs = normalize_observation(observation)
    normalized_usage = _ensure_json_serializable(token_usage) if token_usage else None
    normalized_info = _ensure_json_serializable(info) if info else {}
    return CanonicalStepEvent(
        task_name=task_name,
        task_goal=task_goal,
        run_id=run_id,
        step=step,
        prediction=prediction,
        action=normalized_action,
        action_type=normalized_action.get("action_type"),
        ask_user_response=normalized_obs["ask_user_response"],
        tool_call=normalized_obs["tool_call"],
        token_usage=normalized_usage,
        info=normalized_info,
    )


def normalize_score_event(
    *,
    task_name: str,
    run_id: str,
    score: float,
    reason: str,
    evaluator: str | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
) -> CanonicalScoreEvent:
    """Create canonical score event from legacy runtime payloads."""
    normalized_refs = _ensure_json_serializable(evidence_refs) if evidence_refs else []
    return CanonicalScoreEvent(
        task_name=task_name,
        run_id=run_id,
        score=float(score),
        reason=str(reason),
        evaluator=evaluator,
        evidence_refs=normalized_refs,
    )


def normalize_metrics_event(
    *,
    task_name: str,
    run_id: str,
    quality_flags: dict[str, str] | MetricsQualityFlags,
    token_usage: dict[str, Any],
    latency: dict[str, Any],
    reliability: dict[str, Any],
    cost: dict[str, Any] | None = None,
    info: dict[str, Any] | None = None,
) -> CanonicalMetricsEvent:
    """Create canonical metrics summary event."""
    if isinstance(quality_flags, dict):
        quality = MetricsQualityFlags(**quality_flags)
    else:
        quality = quality_flags
    return CanonicalMetricsEvent(
        task_name=task_name,
        run_id=run_id,
        quality_flags=quality,
        token_usage=_ensure_json_serializable(token_usage),
        latency=_ensure_json_serializable(latency),
        reliability=_ensure_json_serializable(reliability),
        cost=_ensure_json_serializable(cost or {}),
        info=_ensure_json_serializable(info or {}),
    )
