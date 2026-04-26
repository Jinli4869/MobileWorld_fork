"""Skill action queue executor."""

from __future__ import annotations

from mobile_world.runtime.utils.models import JSONAction
from mobile_world.skills.models import Skill


class SkillExecutor:
    """Returns one stored MobileWorld action at a time."""

    def __init__(self, skill: Skill):
        self.skill = skill
        self._index = 0

    @property
    def exhausted(self) -> bool:
        return self._index >= len(self.skill.steps)

    def next_action(self) -> JSONAction | None:
        if self.exhausted:
            return None
        action = self.skill.steps[self._index].action
        self._index += 1
        return action

    @property
    def returned_steps(self) -> int:
        return self._index
