"""Extract reusable GUI skill prefixes from MobileWorld trajectories."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mobile_world.runtime.utils.models import (
    ANSWER,
    APP_DICT,
    COMMON_APP_MAPPER,
    FINISHED,
    OPEN_APP,
    STATUS,
    UNKNOWN,
    JSONAction,
)
from mobile_world.skills.config import SkillConfig
from mobile_world.skills.models import Skill, SkillStep

_TERMINAL_OR_UNREUSABLE = {ANSWER, FINISHED, STATUS, UNKNOWN, None}
_PACKAGE_TO_APP = {package_name: app_name for package_name, app_name in COMMON_APP_MAPPER.items()}
for _app_name, _package_name in APP_DICT.items():
    _PACKAGE_TO_APP.setdefault(_package_name, _app_name)


def _first_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _slug_words(text: str, *, limit: int = 8) -> str:
    words = re.findall(r"[\w\u4e00-\u9fff]+", text, re.UNICODE)
    if not words:
        return "mobileworld-skill"
    return "-".join(words[:limit]).lower()


class SkillExtractor:
    """Build skills from MobileWorld legacy trajectory artifacts."""

    def __init__(self, config: SkillConfig):
        self.config = config

    def extract(
        self,
        *,
        task_name: str,
        task_goal: str,
        score: float,
        reason: str,
        artifact_paths: dict[str, str],
        task_metadata: dict[str, Any] | None = None,
    ) -> tuple[Skill | None, dict[str, Any]]:
        success = score >= self.config.success_threshold
        if not self.config.extract_skills:
            return None, {"status": "skipped", "decision": "extract_skills_disabled"}
        if not success and not self.config.extract_failed_skills:
            return None, {"status": "skipped", "decision": "failed_task_extraction_disabled"}

        legacy_path = Path(artifact_paths.get("legacy_log_path", ""))
        if not legacy_path.exists():
            return None, {"status": "skipped", "decision": "missing_trajectory"}

        legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
        traj = legacy.get("0", {}).get("traj", [])
        if not isinstance(traj, list) or not traj:
            return None, {"status": "skipped", "decision": "empty_trajectory"}

        prefix_limit = self.config.max_extract_steps if success else self.config.failed_prefix_max_steps
        skill_steps: list[SkillStep] = []
        for entry in traj:
            if not isinstance(entry, dict):
                continue
            action_payload = entry.get("action")
            if not isinstance(action_payload, dict):
                continue
            action_type = action_payload.get("action_type")
            if action_type in _TERMINAL_OR_UNREUSABLE:
                break
            try:
                action = JSONAction(**action_payload)
            except Exception:
                continue
            step_info = entry.get("step_info") if isinstance(entry.get("step_info"), dict) else {}
            skill_steps.append(
                SkillStep(
                    step=len(skill_steps) + 1,
                    action=action,
                    source_step=entry.get("step"),
                    foreground_app=_first_text(step_info.get("foreground_app")),
                    foreground_package=_first_text(step_info.get("foreground_package")),
                )
            )
            if len(skill_steps) >= prefix_limit:
                break

        if not skill_steps:
            return None, {"status": "skipped", "decision": "no_reusable_prefix"}

        app_name, foreground_app, foreground_package, app_inferred = self._resolve_app(
            traj=traj,
            task_metadata=task_metadata or {},
        )
        skill_steps = self._ensure_open_app_prefix(
            steps=skill_steps,
            app_name=app_name,
            app_inferred=app_inferred,
        )

        source_kind = "success" if success else "failed-prefix"
        skill = Skill(
            name=_slug_words(task_goal or task_name),
            description=f"Reusable GUI prefix extracted from {task_name}",
            task_goal=task_goal,
            app_name=app_name,
            foreground_app=foreground_app,
            foreground_package=foreground_package,
            app_inferred=app_inferred,
            steps=skill_steps,
            tags=list(task_metadata.get("tags", []) or []),
            source={
                "task_name": task_name,
                "score": score,
                "reason": reason,
                "source_kind": source_kind,
                "legacy_log_path": str(legacy_path),
            },
            metadata={
                "apps": list(task_metadata.get("apps", []) or []),
                "mobileworld_success": success,
            },
        )
        return skill, {
            "status": "extracted",
            "decision": source_kind,
            "app_inferred": app_inferred,
            "foreground_app": foreground_app,
            "foreground_package": foreground_package,
            "steps": len(skill_steps),
        }

    def _resolve_app(
        self,
        *,
        traj: list[dict[str, Any]],
        task_metadata: dict[str, Any],
    ) -> tuple[str | None, str | None, str | None, bool]:
        for entry in traj:
            if not isinstance(entry, dict):
                continue
            step_info = entry.get("step_info") if isinstance(entry.get("step_info"), dict) else {}
            foreground_package = _first_text(step_info.get("foreground_package"))
            foreground_app = _first_text(step_info.get("foreground_app"))
            if foreground_app or foreground_package:
                app_name = foreground_app or _PACKAGE_TO_APP.get(foreground_package, foreground_package)
                return app_name, foreground_app or app_name, foreground_package, True

        for entry in traj:
            action = entry.get("action") if isinstance(entry, dict) else None
            if isinstance(action, dict) and action.get("action_type") == OPEN_APP:
                app_name = _first_text(action.get("app_name"))
                if app_name:
                    return app_name, app_name, None, True

        apps = [app for app in task_metadata.get("apps", []) if isinstance(app, str)]
        for app in apps:
            if not app.startswith("MCP-"):
                return app, app, None, True
        return None, None, None, False

    def _ensure_open_app_prefix(
        self,
        *,
        steps: list[SkillStep],
        app_name: str | None,
        app_inferred: bool,
    ) -> list[SkillStep]:
        if not app_name or not app_inferred:
            return steps
        if steps and steps[0].action.action_type == OPEN_APP:
            return steps
        prefixed = [
            SkillStep(
                step=1,
                action=JSONAction(action_type=OPEN_APP, app_name=app_name),
                source_step=None,
                foreground_app=app_name,
            )
        ]
        for idx, step in enumerate(steps, start=2):
            step.step = idx
            prefixed.append(step)
        return prefixed
