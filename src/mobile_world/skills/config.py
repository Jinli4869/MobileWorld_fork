"""Configuration for MobileWorld-native GUI skill reuse."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, field_validator

SkillMode = Literal["off", "reuse", "learn", "reuse_and_learn"]


class SkillConfig(BaseModel):
    """Runtime options for native GUI skill reuse."""

    enabled: bool = False
    mode: SkillMode = "reuse_and_learn"
    store_root: str = "./traj_logs/mobileworld_skills"
    extract_skills: bool = True
    extract_failed_skills: bool = True
    skill_threshold: float = 0.6
    top_k: int = 5
    llm_judge: bool = False
    cleanup_failure_streak: int = 3
    success_threshold: float = 0.99
    failed_prefix_max_steps: int = 3
    max_extract_steps: int = 20

    @field_validator("mode", mode="before")
    @classmethod
    def normalize_mode(cls, value: Any) -> str:
        if value is None:
            return "reuse_and_learn"
        normalized = str(value).strip().lower()
        if normalized in {"on", "enabled", "reuse_learn", "reuse-and-learn"}:
            return "reuse_and_learn"
        return normalized

    @field_validator("skill_threshold", "success_threshold")
    @classmethod
    def normalize_threshold(cls, value: float) -> float:
        return max(0.0, min(float(value), 1.0))

    @field_validator("top_k", "cleanup_failure_streak", "failed_prefix_max_steps", "max_extract_steps")
    @classmethod
    def normalize_positive_int(cls, value: int) -> int:
        return max(int(value), 1)

    @classmethod
    def from_payload(cls, payload: Any) -> SkillConfig:
        """Create config from CLI/config payload while preserving disabled default."""
        if payload is None:
            return cls()
        if isinstance(payload, SkillConfig):
            return payload
        if isinstance(payload, str):
            return cls.model_validate_json(Path(payload).expanduser().read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return cls(**payload)
        raise TypeError(f"Unsupported skill_config payload: {type(payload).__name__}")

    @property
    def reuse_enabled(self) -> bool:
        return self.enabled and self.mode in {"reuse", "reuse_and_learn"}

    @property
    def learning_enabled(self) -> bool:
        return self.enabled and self.mode in {"learn", "reuse_and_learn"} and self.extract_skills
