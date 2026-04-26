"""Local JSON-backed GUI skill library."""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mobile_world.skills.config import SkillConfig
from mobile_world.skills.models import Skill

_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
_WRITE_LOCK = threading.Lock()


@dataclass
class SkillMatch:
    skill: Skill
    score: float
    reason: str


def _tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    return {token.lower() for token in _TOKEN_RE.findall(text)}


class SkillLibrary:
    """JSON persistence and lexical retrieval for GUI skills."""

    def __init__(self, config: SkillConfig):
        self.config = config
        self.store_root = Path(config.store_root).expanduser()
        self.library_path = self.store_root / "skills.json"
        self.store_root.mkdir(parents=True, exist_ok=True)
        if not self.library_path.exists():
            self._write_raw({"schema_version": "1.0.0", "skills": []})

    def _read_raw(self) -> dict[str, Any]:
        try:
            with self.library_path.open(encoding="utf-8") as f:
                payload = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"schema_version": "1.0.0", "skills": []}
        if not isinstance(payload, dict):
            return {"schema_version": "1.0.0", "skills": []}
        if not isinstance(payload.get("skills"), list):
            payload["skills"] = []
        return payload

    def _write_raw(self, payload: dict[str, Any]) -> None:
        self.store_root.mkdir(parents=True, exist_ok=True)
        with _WRITE_LOCK:
            tmp_path = self.library_path.with_suffix(".json.tmp")
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            tmp_path.replace(self.library_path)

    def list_skills(self) -> list[Skill]:
        payload = self._read_raw()
        skills: list[Skill] = []
        for item in payload.get("skills", []):
            if not isinstance(item, dict):
                continue
            try:
                skills.append(Skill(**item))
            except Exception:
                continue
        return skills

    def count(self) -> int:
        return len(self.list_skills())

    def add_or_update(self, skill: Skill) -> Skill:
        payload = self._read_raw()
        existing = []
        replaced = False
        for item in payload.get("skills", []):
            if not isinstance(item, dict):
                continue
            if item.get("id") == skill.id:
                existing.append(skill.model_dump(mode="json"))
                replaced = True
            else:
                existing.append(item)
        if not replaced:
            existing.append(skill.model_dump(mode="json"))
        payload["skills"] = existing
        self._write_raw(payload)
        return skill

    def update_result(self, skill_id: str | None, *, success: bool) -> Skill | None:
        if not skill_id:
            return None
        skills = self.list_skills()
        updated: Skill | None = None
        payload = self._read_raw()
        serialized = []
        for skill in skills:
            if skill.id == skill_id:
                skill.usage_count += 1
                if success:
                    skill.success_count += 1
                    skill.failure_streak = 0
                else:
                    skill.failure_count += 1
                    skill.failure_streak += 1
                skill.touch()
                updated = skill
            serialized.append(skill.model_dump(mode="json"))
        payload["skills"] = serialized
        self._write_raw(payload)
        return updated

    def cleanup(self) -> int:
        threshold = self.config.cleanup_failure_streak
        payload = self._read_raw()
        kept = []
        removed = 0
        for item in payload.get("skills", []):
            try:
                skill = Skill(**item)
            except Exception:
                removed += 1
                continue
            if skill.failure_streak >= threshold:
                removed += 1
                continue
            kept.append(skill.model_dump(mode="json"))
        payload["skills"] = kept
        self._write_raw(payload)
        return removed

    def search(
        self,
        *,
        task_goal: str,
        foreground_app: str | None = None,
        foreground_package: str | None = None,
        top_k: int | None = None,
    ) -> list[SkillMatch]:
        query_tokens = _tokens(task_goal) | _tokens(foreground_app) | _tokens(foreground_package)
        if not query_tokens:
            return []
        matches: list[SkillMatch] = []
        for skill in self.list_skills():
            text = " ".join(
                [
                    skill.name,
                    skill.description,
                    skill.task_goal,
                    skill.app_name or "",
                    skill.foreground_app or "",
                    skill.foreground_package or "",
                    " ".join(skill.tags),
                ]
            )
            skill_tokens = _tokens(text)
            overlap = query_tokens & skill_tokens
            if not overlap:
                continue
            score = len(overlap) / max(len(query_tokens), 1)
            if foreground_package and skill.foreground_package == foreground_package:
                score += 0.25
            elif foreground_app and skill.foreground_app == foreground_app:
                score += 0.15
            if skill.failure_streak:
                score -= min(0.25, 0.05 * skill.failure_streak)
            score = round(max(0.0, min(score, 1.0)), 6)
            matches.append(SkillMatch(skill=skill, score=score, reason="lexical_overlap"))
        matches.sort(key=lambda item: item.score, reverse=True)
        return matches[: top_k or self.config.top_k]
