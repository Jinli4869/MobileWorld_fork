"""Persistent skill data models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from mobile_world.runtime.utils.models import JSONAction


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class SkillStep(BaseModel):
    """One reusable MobileWorld GUI action in a skill prefix."""

    step: int
    action: JSONAction
    source_step: int | None = None
    foreground_app: str | None = None
    foreground_package: str | None = None


class Skill(BaseModel):
    """A reusable GUI action prefix learned from MobileWorld trajectories."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    task_goal: str
    app_name: str | None = None
    foreground_app: str | None = None
    foreground_package: str | None = None
    app_inferred: bool = False
    steps: list[SkillStep] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    failure_streak: int = 0
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)

    @property
    def success_rate(self) -> float:
        if self.usage_count <= 0:
            return 0.0
        return round(self.success_count / self.usage_count, 6)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()
