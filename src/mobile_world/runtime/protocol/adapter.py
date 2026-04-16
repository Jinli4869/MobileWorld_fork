"""Protocol contracts for framework adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class AdapterProfile(BaseModel):
    """Metadata for adapter registration and discovery."""

    name: str
    framework: str
    version: str = "0.1.0"
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdapterInitializeInput(BaseModel):
    """Canonical payload for adapter initialization."""

    task_name: str
    task_goal: str
    run_id: str
    options: dict[str, Any] = Field(default_factory=dict)


class AdapterInitializeResult(BaseModel):
    """Result of adapter initialization."""

    ok: bool
    message: str = ""
    adapter_state: dict[str, Any] = Field(default_factory=dict)


class AdapterStepInput(BaseModel):
    """Canonical payload for one adapter step."""

    run_id: str
    task_name: str
    step_index: int
    observation: dict[str, Any] = Field(default_factory=dict)


class AdapterStepResult(BaseModel):
    """Canonical result for one adapter step."""

    prediction: str | None = None
    action: dict[str, Any] = Field(default_factory=dict)
    done: bool = False
    info: dict[str, Any] = Field(default_factory=dict)


class AdapterFinalizeInput(BaseModel):
    """Canonical payload for adapter finalization."""

    run_id: str
    task_name: str
    score: float | None = None
    reason: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class AdapterFinalizeResult(BaseModel):
    """Result of adapter finalization."""

    ok: bool
    summary: str = ""
    final_state: dict[str, Any] = Field(default_factory=dict)


class ArtifactRecord(BaseModel):
    """Single artifact record emitted by adapter."""

    path: str
    artifact_type: str
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdapterArtifactsResult(BaseModel):
    """Artifacts emitted by adapter at run completion."""

    emitted_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp in ISO 8601 format.",
    )
    artifacts: list[ArtifactRecord] = Field(default_factory=list)


class FrameworkAdapter(ABC):
    """Framework-agnostic adapter lifecycle contract."""

    @abstractmethod
    def initialize(self, payload: AdapterInitializeInput) -> AdapterInitializeResult:
        """Initialize the adapter for one task run."""
        raise NotImplementedError

    @abstractmethod
    def step(self, payload: AdapterStepInput) -> AdapterStepResult:
        """Execute one step and return canonical action output."""
        raise NotImplementedError

    @abstractmethod
    def finalize(self, payload: AdapterFinalizeInput) -> AdapterFinalizeResult:
        """Finalize one run and return completion metadata."""
        raise NotImplementedError

    @abstractmethod
    def emit_artifacts(self, run_id: str, output_dir: str) -> AdapterArtifactsResult:
        """Emit adapter-owned artifacts for one run."""
        raise NotImplementedError


TERMINAL_ACTION_TYPES = {"finished", "answer", "unknown", "error_env"}


def is_terminal_action(action_type: str | None) -> bool:
    """Return whether one canonical action type should terminate execution."""
    return action_type in TERMINAL_ACTION_TYPES


class LegacyAgentAdapter(FrameworkAdapter):
    """Bridge adapter wrapping current built-in `BaseAgent` behavior."""

    def __init__(self, agent: Any):
        self._agent = agent
        self._initialized = False

    def initialize(self, payload: AdapterInitializeInput) -> AdapterInitializeResult:
        self._agent.initialize(payload.task_goal)
        self._initialized = True
        return AdapterInitializeResult(
            ok=True,
            message=f"Initialized legacy agent for task {payload.task_name}",
        )

    def step(self, payload: AdapterStepInput) -> AdapterStepResult:
        if not self._initialized:
            return AdapterStepResult(
                prediction=None,
                action={"action_type": "unknown"},
                done=True,
                info={"error": "adapter not initialized"},
            )
        prediction, action = self._agent.predict(payload.observation)
        action_payload = (
            action.model_dump(exclude_none=True)
            if hasattr(action, "model_dump")
            else dict(action) if isinstance(action, dict) else {"raw_action": str(action)}
        )
        done = is_terminal_action(action_payload.get("action_type"))
        return AdapterStepResult(
            prediction=prediction,
            action=action_payload,
            done=done,
        )

    def finalize(self, payload: AdapterFinalizeInput) -> AdapterFinalizeResult:
        self._agent.done()
        self._initialized = False
        return AdapterFinalizeResult(
            ok=True,
            summary=f"Legacy adapter finalized for task {payload.task_name}",
            final_state={"score": payload.score, "reason": payload.reason},
        )

    def emit_artifacts(self, run_id: str, output_dir: str) -> AdapterArtifactsResult:
        return AdapterArtifactsResult(artifacts=[])
