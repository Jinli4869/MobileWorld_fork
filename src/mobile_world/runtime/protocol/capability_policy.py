"""Capability policy resolution for unified tool routing."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ToolClass = Literal["gui", "mcp", "ask_user"]
TOOL_CLASSES: tuple[ToolClass, ...] = ("gui", "mcp", "ask_user")


class CapabilityPolicyRule(BaseModel):
    """One policy rule with optional tag/profile match."""

    name: str
    match_tags_any: list[str] = Field(default_factory=list)
    match_profiles_any: list[str] = Field(default_factory=list)
    allow_tool_classes: list[ToolClass] = Field(default_factory=list)
    deny_tool_classes: list[ToolClass] = Field(default_factory=list)
    allow_mcp_tools: list[str] = Field(default_factory=list)
    deny_mcp_tools: list[str] = Field(default_factory=list)
    mcp_timeout_seconds: int | None = None

    def matches(self, task_tags: list[str], profile_name: str) -> bool:
        """Return True when rule matches current task/profile context."""
        tag_match = (
            True
            if not self.match_tags_any
            else bool(set(self.match_tags_any).intersection(set(task_tags)))
        )
        profile_match = (
            True if not self.match_profiles_any else profile_name in set(self.match_profiles_any)
        )
        return tag_match and profile_match


class CapabilityPolicyConfig(BaseModel):
    """Config schema for capability policy."""

    schema_version: str = "1.0.0"
    default_tool_classes: list[ToolClass] = Field(default_factory=lambda: ["gui"])
    default_mcp_allowlist: list[str] = Field(default_factory=lambda: ["*"])
    default_mcp_timeout_seconds: int = 120
    rules: list[CapabilityPolicyRule] = Field(default_factory=list)


class CapabilityDecision(BaseModel):
    """Resolved deterministic capability decision for one task run."""

    enabled_tool_classes: list[ToolClass] = Field(default_factory=list)
    enabled_mcp_tools: list[str] = Field(default_factory=list)
    mcp_timeout_seconds: int = 120
    source: str = "default"
    task_tags: list[str] = Field(default_factory=list)
    profile_name: str = ""

    def is_tool_class_enabled(self, tool_class: ToolClass) -> bool:
        return tool_class in set(self.enabled_tool_classes)

    def is_mcp_tool_enabled(self, tool_name: str | None) -> bool:
        if not tool_name:
            return False
        allowlist = set(self.enabled_mcp_tools)
        return "*" in allowlist or tool_name in allowlist

    def as_manifest(self) -> dict:
        """Serializable manifest persisted in run artifacts."""
        return {
            "enabled_tool_classes": sorted(self.enabled_tool_classes),
            "enabled_mcp_tools": sorted(self.enabled_mcp_tools),
            "mcp_timeout_seconds": self.mcp_timeout_seconds,
            "source": self.source,
            "task_tags": sorted(self.task_tags),
            "profile_name": self.profile_name,
        }


def _stable_unique(values: list[str]) -> list[str]:
    """Stable unique for deterministic output order."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _load_policy_config(policy_path: str | None) -> CapabilityPolicyConfig:
    """Load policy config from file path or defaults."""
    if not policy_path:
        env_path = os.getenv("MOBILE_WORLD_CAPABILITY_POLICY_PATH")
        policy_path = env_path
    if not policy_path:
        return CapabilityPolicyConfig()
    path = Path(policy_path)
    if not path.exists():
        raise ValueError(f"Capability policy file not found: {policy_path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return CapabilityPolicyConfig.model_validate(data)


def resolve_capability_policy(
    *,
    task_tags: list[str],
    profile_name: str,
    enable_mcp: bool,
    enable_user_interaction: bool,
    policy_path: str | None = None,
    mcp_allowlist_override: list[str] | None = None,
) -> CapabilityDecision:
    """Resolve capability decision for one task execution."""
    config = _load_policy_config(policy_path)
    enabled_classes = _stable_unique(config.default_tool_classes.copy())

    if enable_mcp and "agent-mcp" in set(task_tags):
        enabled_classes = _stable_unique(enabled_classes + ["mcp"])
    if enable_user_interaction and "agent-user-interaction" in set(task_tags):
        enabled_classes = _stable_unique(enabled_classes + ["ask_user"])

    enabled_mcp_tools = config.default_mcp_allowlist.copy() if "mcp" in enabled_classes else []
    source_parts = ["default"]
    timeout_seconds = config.default_mcp_timeout_seconds

    for rule in config.rules:
        if not rule.matches(task_tags, profile_name):
            continue
        source_parts.append(f"rule:{rule.name}")
        for allow in rule.allow_tool_classes:
            if allow not in enabled_classes:
                enabled_classes.append(allow)
        for deny in rule.deny_tool_classes:
            enabled_classes = [cls for cls in enabled_classes if cls != deny]

        if "mcp" in enabled_classes:
            if rule.allow_mcp_tools:
                enabled_mcp_tools = _stable_unique(enabled_mcp_tools + rule.allow_mcp_tools)
            if rule.deny_mcp_tools:
                deny_set = set(rule.deny_mcp_tools)
                enabled_mcp_tools = [
                    tool for tool in enabled_mcp_tools if tool not in deny_set and tool != ""
                ]

        if rule.mcp_timeout_seconds is not None:
            timeout_seconds = rule.mcp_timeout_seconds

    if mcp_allowlist_override is not None:
        enabled_mcp_tools = _stable_unique(mcp_allowlist_override)
        source_parts.append("override:mcp_allowlist")

    enabled_classes = [cls for cls in enabled_classes if cls in TOOL_CLASSES]
    if "mcp" not in enabled_classes:
        enabled_mcp_tools = []

    return CapabilityDecision(
        enabled_tool_classes=enabled_classes,
        enabled_mcp_tools=enabled_mcp_tools,
        mcp_timeout_seconds=int(timeout_seconds),
        source="|".join(source_parts),
        task_tags=task_tags,
        profile_name=profile_name,
    )

