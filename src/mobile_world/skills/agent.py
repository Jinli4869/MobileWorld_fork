"""Agent wrapper that reuses MobileWorld-native GUI skills."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from mobile_world.agents.base import BaseAgent
from mobile_world.runtime.utils.models import UNKNOWN, JSONAction
from mobile_world.skills.config import SkillConfig
from mobile_world.skills.executor import SkillExecutor
from mobile_world.skills.extractor import SkillExtractor
from mobile_world.skills.library import SkillLibrary, SkillMatch

SKILL_SUMMARY_FILE_NAME = "mobileworld_skill_summary.json"


class SkillAugmentedAgent(BaseAgent):
    """Wrap a normal MobileWorld agent with native skill reuse/learning."""

    def __init__(self, base_agent: BaseAgent, skill_config: SkillConfig | dict[str, Any]):
        super().__init__()
        self.base_agent = base_agent
        self.config = SkillConfig.from_payload(skill_config)
        self.library = SkillLibrary(self.config)
        self.extractor = SkillExtractor(self.config)
        self._executor: SkillExecutor | None = None
        self._matched: SkillMatch | None = None
        self._retrieval_attempted = False
        self._last_step_info: dict[str, Any] = {}
        self._skill_steps_returned = 0
        self._fallback_steps = 0
        self._total_steps = 0
        self._skill_reuser_completion_tokens = 0
        self._skill_reuser_prompt_tokens = 0
        self._skill_extractor_completion_tokens = 0
        self._skill_extractor_prompt_tokens = 0
        self._last_foreground_app: str | None = None
        self._last_foreground_package: str | None = None
        self._summary: dict[str, Any] = {}

    def initialize(self, instruction: str) -> bool:
        self.instruction = instruction
        self._reset_task_state()
        return self.base_agent.initialize(instruction)

    def _reset_task_state(self) -> None:
        self._executor = None
        self._matched = None
        self._retrieval_attempted = False
        self._last_step_info = {}
        self._skill_steps_returned = 0
        self._fallback_steps = 0
        self._total_steps = 0
        self._last_foreground_app = None
        self._last_foreground_package = None
        self._summary = {
            "skill_enabled": self.config.enabled,
            "mode": self.config.mode,
            "skill_hit": False,
            "matched_skill_id": None,
            "matched_skill_name": None,
            "match_score": None,
            "skill_steps_returned": 0,
            "fallback_steps": 0,
            "total_steps": 0,
        }

    def predict(self, observation: dict[str, Any]) -> tuple[str, JSONAction]:
        self._total_steps += 1
        foreground_app = observation.get("foreground_app")
        foreground_package = observation.get("foreground_package")
        if foreground_app:
            self._last_foreground_app = foreground_app
        if foreground_package:
            self._last_foreground_package = foreground_package
        if self.config.reuse_enabled and not self._retrieval_attempted:
            self._retrieval_attempted = True
            self._matched = self._select_skill(
                foreground_app=foreground_app,
                foreground_package=foreground_package,
            )
            if self._matched is not None:
                self._executor = SkillExecutor(self._matched.skill)
                self._summary.update(
                    {
                        "skill_hit": True,
                        "matched_skill_id": self._matched.skill.id,
                        "matched_skill_name": self._matched.skill.name,
                        "match_score": self._matched.score,
                    }
                )

        if self._executor is not None and not self._executor.exhausted:
            action = self._executor.next_action()
            if action is not None:
                self._skill_steps_returned += 1
                self._last_step_info = {
                    "skill_phase": "skill",
                    "skill_hit": True,
                    "matched_skill_id": self._matched.skill.id if self._matched else None,
                    "matched_skill_name": self._matched.skill.name if self._matched else None,
                    "match_score": self._matched.score if self._matched else None,
                }
                prediction = json.dumps(
                    {
                        "source": "mobileworld_skill",
                        "skill_id": self._last_step_info["matched_skill_id"],
                        "action": action.model_dump(exclude_none=True),
                    },
                    ensure_ascii=False,
                )
                return prediction, action

        self._fallback_steps += 1
        prediction, action = self.base_agent.predict(observation)
        self._last_step_info = {
            "skill_phase": "fallback",
            "skill_hit": self._matched is not None,
            "matched_skill_id": self._matched.skill.id if self._matched else None,
            "matched_skill_name": self._matched.skill.name if self._matched else None,
            "match_score": self._matched.score if self._matched else None,
        }
        if action is None:
            action = JSONAction(action_type=UNKNOWN)
        return prediction, action

    def _select_skill(
        self,
        *,
        foreground_app: str | None,
        foreground_package: str | None,
    ) -> SkillMatch | None:
        matches = self.library.search(
            task_goal=self.instruction or "",
            foreground_app=foreground_app,
            foreground_package=foreground_package,
            top_k=self.config.top_k,
        )
        for match in matches:
            if match.score >= self.config.skill_threshold and self._llm_judges_match(match):
                return match
        return None

    def _llm_judges_match(self, match: SkillMatch) -> bool:
        if not self.config.llm_judge:
            return True
        client = getattr(self.base_agent, "openai_client", None)
        model_name = getattr(self.base_agent, "model_name", None)
        if client is None or not model_name:
            return True
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Decide if a stored GUI action prefix is applicable to the "
                            "current mobile task. Reply only yes or no."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "task_goal": self.instruction,
                                "skill_name": match.skill.name,
                                "skill_goal": match.skill.task_goal,
                                "skill_app": match.skill.app_name,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                max_tokens=8,
            )
            usage = getattr(response, "usage", None)
            if usage is not None:
                self._skill_reuser_completion_tokens += int(
                    getattr(usage, "completion_tokens", 0) or 0
                )
                self._skill_reuser_prompt_tokens += int(getattr(usage, "prompt_tokens", 0) or 0)
            answer = (response.choices[0].message.content or "").strip().lower()
            return answer.startswith(("yes", "true", "1"))
        except Exception:
            logger.exception("Skill LLM applicability judge failed; falling back to lexical match")
            return True

    def consume_last_step_info(self) -> dict[str, Any]:
        info = dict(self._last_step_info)
        self._last_step_info = {}
        return info

    def get_total_token_usage(self) -> dict[str, int]:
        base_usage = self.base_agent.get_total_token_usage()
        completion = int(base_usage.get("completion_tokens", 0) or 0)
        prompt = int(base_usage.get("prompt_tokens", 0) or 0)
        cached = int(base_usage.get("cached_tokens", 0) or 0)
        usage = {
            "completion_tokens": completion
            + self._skill_reuser_completion_tokens
            + self._skill_extractor_completion_tokens,
            "prompt_tokens": prompt
            + self._skill_reuser_prompt_tokens
            + self._skill_extractor_prompt_tokens,
            "cached_tokens": cached,
            "total_tokens": completion
            + self._skill_reuser_completion_tokens
            + self._skill_extractor_completion_tokens
            + prompt
            + self._skill_reuser_prompt_tokens
            + self._skill_extractor_prompt_tokens,
            "base_agent_completion_tokens": completion,
            "skill_reuser_completion_tokens": self._skill_reuser_completion_tokens,
            "skill_extractor_completion_tokens": self._skill_extractor_completion_tokens,
        }
        return usage

    def finalize_task(
        self,
        *,
        task_name: str,
        task_goal: str,
        score: float,
        reason: str,
        artifact_paths: dict[str, str],
        metrics: dict[str, Any] | None = None,
        task_metadata: dict[str, Any] | None = None,
        success_threshold: float | None = None,
    ) -> dict[str, Any]:
        if success_threshold is not None:
            self.config.success_threshold = success_threshold
        store_before = self.library.count()
        mobileworld_success = score >= self.config.success_threshold

        if self._matched is not None:
            self.library.update_result(self._matched.skill.id, success=mobileworld_success)

        extracted_skill = None
        extraction_info: dict[str, Any] = {"status": "skipped", "decision": "learning_disabled"}
        if self.config.learning_enabled:
            extracted_skill, extraction_info = self.extractor.extract(
                task_name=task_name,
                task_goal=task_goal,
                score=score,
                reason=reason,
                artifact_paths=artifact_paths,
                task_metadata=task_metadata or {},
            )
            if extracted_skill is not None:
                self.library.add_or_update(extracted_skill)
                logger.info("Extracted MobileWorld GUI skill {}", extracted_skill.id)

        removed_count = self.library.cleanup() if self.config.cleanup_failure_streak else 0
        store_after = self.library.count()
        phase_metrics = (metrics or {}).get("skill_phase_metrics", {})
        summary = {
            **self._summary,
            "skill_steps_returned": self._skill_steps_returned,
            "fallback_steps": self._fallback_steps,
            "total_steps": self._total_steps,
            "score": score,
            "reason": reason,
            "success_threshold": self.config.success_threshold,
            "mobileworld_success": mobileworld_success,
            "skill_execution_success": bool(self._matched is not None and mobileworld_success),
            "skill_false_positive": bool(self._matched is not None and not mobileworld_success),
            "foreground_app": extraction_info.get("foreground_app") or self._last_foreground_app,
            "foreground_package": extraction_info.get("foreground_package")
            or self._last_foreground_package,
            "app_inferred": extraction_info.get("app_inferred", False),
            "extraction_status": extraction_info.get("status"),
            "extraction_decision": extraction_info.get("decision"),
            "extract_failed_skills": self.config.extract_failed_skills,
            "skill_store_before_count": store_before,
            "skill_store_after_count": store_after,
            "skill_store_removed_count": removed_count,
            "extracted_skill_id": extracted_skill.id if extracted_skill else None,
            "base_agent_completion_tokens": self.get_total_token_usage().get(
                "base_agent_completion_tokens", 0
            ),
            "skill_reuser_completion_tokens": self._skill_reuser_completion_tokens,
            "skill_extractor_completion_tokens": self._skill_extractor_completion_tokens,
            "skill_phase_avg_predict_latency_ms": phase_metrics.get("skill", {}).get(
                "avg_predict_latency_ms"
            ),
            "fallback_phase_avg_predict_latency_ms": phase_metrics.get("fallback", {}).get(
                "avg_predict_latency_ms"
            ),
        }
        self._write_summary(artifact_paths=artifact_paths, summary=summary)
        self._summary = summary
        return summary

    def _write_summary(self, *, artifact_paths: dict[str, str], summary: dict[str, Any]) -> None:
        legacy_path = artifact_paths.get("legacy_log_path")
        if not legacy_path:
            return
        task_dir = Path(legacy_path).parent
        task_dir.mkdir(parents=True, exist_ok=True)
        with (task_dir / SKILL_SUMMARY_FILE_NAME).open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    def done(self) -> None:
        self.base_agent.done()
        self.instruction = None
        self._reset_task_state()

    def reset(self) -> None:
        self.base_agent.reset()

    def reset_token_usage(self) -> None:
        self.base_agent.reset_token_usage()
        self._skill_reuser_completion_tokens = 0
        self._skill_reuser_prompt_tokens = 0
        self._skill_extractor_completion_tokens = 0
        self._skill_extractor_prompt_tokens = 0
