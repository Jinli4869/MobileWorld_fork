"""Canonical event schemas for cross-framework trajectories."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


CANONICAL_TRAJECTORY_SCHEMA_VERSION = "1.0.0"


def utc_now_iso() -> str:
    """Return UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


class MetricsQualityFlags(BaseModel):
    """Quality metadata for metric sources."""

    token_usage: Literal["native", "estimated", "unavailable"] = "unavailable"
    latency: Literal["native", "estimated", "unavailable"] = "unavailable"
    cost: Literal["native", "estimated", "unavailable"] = "unavailable"


class CanonicalTrajectoryHeader(BaseModel):
    """Run-level metadata for canonical trajectory artifacts."""

    type: Literal["header"] = "header"
    schema_version: str = CANONICAL_TRAJECTORY_SCHEMA_VERSION
    created_at: str = Field(default_factory=utc_now_iso)
    task_name: str
    task_goal: str
    run_id: str
    tools: list[dict[str, Any]] = Field(default_factory=list)
    quality_flags: MetricsQualityFlags = Field(default_factory=MetricsQualityFlags)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CanonicalStepEvent(BaseModel):
    """One canonical step event."""

    type: Literal["step"] = "step"
    schema_version: str = CANONICAL_TRAJECTORY_SCHEMA_VERSION
    timestamp: str = Field(default_factory=utc_now_iso)
    task_name: str
    task_goal: str
    run_id: str
    step: int
    prediction: str | None = None
    action: dict[str, Any] = Field(default_factory=dict)
    action_type: str | None = None
    ask_user_response: str | None = None
    tool_call: Any | None = None
    token_usage: dict[str, int] | None = None
    info: dict[str, Any] = Field(default_factory=dict)


class CanonicalScoreEvent(BaseModel):
    """Canonical score event for one task run."""

    type: Literal["score"] = "score"
    schema_version: str = CANONICAL_TRAJECTORY_SCHEMA_VERSION
    timestamp: str = Field(default_factory=utc_now_iso)
    task_name: str
    run_id: str
    score: float
    reason: str
    evaluator: str | None = None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)


class CanonicalMetricsEvent(BaseModel):
    """Canonical run-level metrics summary event."""

    type: Literal["metrics"] = "metrics"
    schema_version: str = CANONICAL_TRAJECTORY_SCHEMA_VERSION
    timestamp: str = Field(default_factory=utc_now_iso)
    task_name: str
    run_id: str
    quality_flags: MetricsQualityFlags = Field(default_factory=MetricsQualityFlags)
    token_usage: dict[str, Any] = Field(default_factory=dict)
    latency: dict[str, Any] = Field(default_factory=dict)
    reliability: dict[str, Any] = Field(default_factory=dict)
    cost: dict[str, Any] = Field(default_factory=dict)
    info: dict[str, Any] = Field(default_factory=dict)
