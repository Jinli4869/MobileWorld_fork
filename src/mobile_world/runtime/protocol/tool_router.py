"""Unified tool router for GUI/MCP/ask-user actions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from mobile_world.runtime.protocol.capability_policy import CapabilityDecision, ToolClass
from mobile_world.runtime.utils.models import ASK_USER, MCP, Observation


class NormalizedToolError(BaseModel):
    """Comparable normalized tool failure payload."""

    code: str
    message: str
    action_type: str | None = None
    tool_class: ToolClass | None = None
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ToolDispatchResult(BaseModel):
    """Result wrapper for one tool dispatch."""

    ok: bool
    observation: Observation | None = None
    error: NormalizedToolError | None = None


ActionClass = Literal["gui", "mcp", "ask_user"]


def classify_action_type(action_type: str | None) -> ActionClass:
    """Classify action type into one tool class bucket."""
    if action_type == MCP:
        return "mcp"
    if action_type == ASK_USER:
        return "ask_user"
    return "gui"


class UnifiedToolRouter:
    """Single action dispatch entrypoint with capability enforcement."""

    def __init__(self, decision: CapabilityDecision):
        self.decision = decision

    def _deny(self, *, code: str, message: str, action_type: str | None, tool_class: ToolClass) -> ToolDispatchResult:
        return ToolDispatchResult(
            ok=False,
            error=NormalizedToolError(
                code=code,
                message=message,
                action_type=action_type,
                tool_class=tool_class,
                retryable=False,
            ),
        )

    def dispatch(self, env: Any, action: Any) -> ToolDispatchResult:
        """Dispatch one action with policy checks and normalized error handling."""
        action_type = getattr(action, "action_type", None)
        tool_class = classify_action_type(action_type)

        if not self.decision.is_tool_class_enabled(tool_class):
            return self._deny(
                code="CAPABILITY_DENIED",
                message=f"Tool class '{tool_class}' is disabled by capability policy",
                action_type=action_type,
                tool_class=tool_class,
            )

        if tool_class == "mcp":
            action_name = getattr(action, "action_name", None)
            if not self.decision.is_mcp_tool_enabled(action_name):
                return self._deny(
                    code="MCP_TOOL_NOT_ALLOWLISTED",
                    message=f"MCP tool '{action_name}' is not enabled by allowlist",
                    action_type=action_type,
                    tool_class=tool_class,
                )

        try:
            observation = env.execute_action(action)
            return ToolDispatchResult(ok=True, observation=observation)
        except Exception as exc:
            return ToolDispatchResult(
                ok=False,
                error=NormalizedToolError(
                    code="TOOL_EXECUTION_ERROR",
                    message=str(exc),
                    action_type=action_type,
                    tool_class=tool_class,
                    retryable=False,
                    details={"exception_type": type(exc).__name__},
                ),
            )

