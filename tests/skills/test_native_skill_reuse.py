import json
from pathlib import Path

from PIL import Image

from mobile_world.agents.base import BaseAgent
from mobile_world.agents.implementations.general_e2e_agent import GeneralE2EAgentMCP
from mobile_world.agents.registry import create_agent
from mobile_world.core.cli import create_parser
from mobile_world.core.runner import _execute_single_task
from mobile_world.runtime.protocol.evaluator import EvaluationAudit, EvaluatorResult
from mobile_world.runtime.protocol.metrics import MetricsCollector
from mobile_world.runtime.protocol.reporting import aggregate_framework_runs
from mobile_world.runtime.utils.models import JSONAction, Observation
from mobile_world.runtime.utils.trajectory_logger import (
    EVALUATOR_AUDIT_FILE_NAME,
    METRICS_FILE_NAME,
    SCORE_FILE_NAME,
    SKILL_SUMMARY_FILE_NAME,
    TrajLogger,
)
from mobile_world.skills.agent import SkillAugmentedAgent
from mobile_world.skills.config import SkillConfig
from mobile_world.skills.extractor import SkillExtractor
from mobile_world.skills.library import SkillLibrary
from mobile_world.skills.models import Skill, SkillStep


class DummyAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.predict_calls = 0

    def predict(self, observation):
        self.predict_calls += 1
        self._total_completion_tokens += 7
        return "fallback", JSONAction(action_type="wait")

    def reset(self):
        pass


class FinalizeRecordingAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.finalize_kwargs = None

    def predict(self, observation):
        return "done", JSONAction(action_type="answer", text="done")

    def finalize_task(self, **kwargs):
        self.finalize_kwargs = kwargs
        return {"skill_enabled": True}

    def reset(self):
        pass


class DummyEnv:
    tools = []

    def __init__(self):
        self.obs = _obs()

    def get_task_goal(self, task_type):
        return "Open Mail"

    def initialize_task(self, task_name):
        return self.obs

    def execute_action(self, action):
        return self.obs

    def tear_down_task(self, task_type):
        return {"ok": True}


class DummyEvaluator:
    name = "dummy"

    def evaluate(self, env, payload):
        return EvaluatorResult(
            evaluator_name=self.name,
            score=0.5,
            reason="synthetic",
            audit=EvaluationAudit(
                evaluator_name=self.name,
                primary_signal="synthetic",
                score=0.5,
                reason="synthetic",
            ),
        )


def _obs() -> Observation:
    return Observation(
        screenshot=Image.new("RGB", (20, 20), color="white"),
        foreground_app="Mail",
        foreground_package="com.gmailclone",
        current_activity="com.gmailclone/.MainActivity",
    )


def test_skill_library_add_search_update_cleanup(tmp_path: Path):
    config = SkillConfig(enabled=True, store_root=str(tmp_path), cleanup_failure_streak=2)
    library = SkillLibrary(config)
    skill = Skill(
        name="open mail inbox",
        task_goal="Open the Mail inbox",
        app_name="Mail",
        foreground_app="Mail",
        foreground_package="com.gmailclone",
        steps=[SkillStep(step=1, action=JSONAction(action_type="open_app", app_name="Mail"))],
    )

    library.add_or_update(skill)
    matches = library.search(task_goal="Open Mail inbox", foreground_app="Mail")

    assert library.count() == 1
    assert matches[0].skill.id == skill.id
    assert matches[0].score >= config.skill_threshold

    library.update_result(skill.id, success=False)
    library.update_result(skill.id, success=False)
    assert library.cleanup() == 1
    assert library.count() == 0


def test_skill_augmented_agent_hit_then_fallback(tmp_path: Path):
    config = SkillConfig(enabled=True, store_root=str(tmp_path), skill_threshold=0.1)
    library = SkillLibrary(config)
    library.add_or_update(
        Skill(
            name="open mail",
            task_goal="Open Mail",
            app_name="Mail",
            foreground_app="Mail",
            steps=[
                SkillStep(step=1, action=JSONAction(action_type="open_app", app_name="Mail")),
                SkillStep(step=2, action=JSONAction(action_type="click", x=4, y=5)),
            ],
        )
    )
    base = DummyAgent()
    wrapper = SkillAugmentedAgent(base, config)
    wrapper.initialize("Open Mail")

    _, first_action = wrapper.predict({"foreground_app": "Mail", "foreground_package": None})
    first_info = wrapper.consume_last_step_info()
    _, second_action = wrapper.predict({"foreground_app": "Mail", "foreground_package": None})
    _, fallback_action = wrapper.predict({"foreground_app": "Mail", "foreground_package": None})
    fallback_info = wrapper.consume_last_step_info()

    assert first_action.action_type == "open_app"
    assert first_info["skill_phase"] == "skill"
    assert second_action.action_type == "click"
    assert fallback_action.action_type == "wait"
    assert fallback_info["skill_phase"] == "fallback"
    assert base.predict_calls == 1


def test_skill_augmented_agent_miss_calls_base(tmp_path: Path):
    config = SkillConfig(enabled=True, store_root=str(tmp_path), skill_threshold=0.9)
    base = DummyAgent()
    wrapper = SkillAugmentedAgent(base, config)
    wrapper.initialize("Completely unrelated task")

    _, action = wrapper.predict({"foreground_app": "Mail"})
    info = wrapper.consume_last_step_info()

    assert action.action_type == "wait"
    assert info["skill_phase"] == "fallback"
    assert base.predict_calls == 1


def test_extractor_uses_foreground_app_for_open_app_prefix(tmp_path: Path):
    traj_logger = TrajLogger(str(tmp_path), "mail_task")
    traj_logger.log_traj(
        task_name="mail_task",
        task_goal="Open Mail and tap inbox",
        step=1,
        prediction="tap",
        action={"action_type": "click", "x": 1, "y": 2},
        obs=_obs(),
        token_usage={"prompt_tokens": 1, "completion_tokens": 1, "cached_tokens": 0, "total_tokens": 2},
        step_info={"foreground_app": "Mail", "foreground_package": "com.gmailclone"},
    )
    extractor = SkillExtractor(SkillConfig(enabled=True, store_root=str(tmp_path / "skills")))

    skill, info = extractor.extract(
        task_name="mail_task",
        task_goal="Open Mail and tap inbox",
        score=1.0,
        reason="ok",
        artifact_paths=traj_logger.artifact_paths(),
        task_metadata={"apps": ["Mail"], "tags": []},
    )

    assert info["status"] == "extracted"
    assert skill is not None
    assert skill.steps[0].action.action_type == "open_app"
    assert skill.steps[0].action.app_name == "Mail"
    assert skill.foreground_package == "com.gmailclone"


def test_failed_task_extraction_toggle(tmp_path: Path):
    traj_logger = TrajLogger(str(tmp_path), "failed_task")
    traj_logger.log_traj(
        task_name="failed_task",
        task_goal="Open Mail",
        step=1,
        prediction="tap",
        action={"action_type": "click", "x": 1, "y": 2},
        obs=_obs(),
        token_usage={"prompt_tokens": 1, "completion_tokens": 1, "cached_tokens": 0, "total_tokens": 2},
        step_info={"foreground_app": "Mail", "foreground_package": "com.gmailclone"},
    )
    disabled = SkillExtractor(
        SkillConfig(enabled=True, store_root=str(tmp_path / "off"), extract_failed_skills=False)
    )
    enabled = SkillExtractor(
        SkillConfig(enabled=True, store_root=str(tmp_path / "on"), extract_failed_skills=True)
    )

    disabled_skill, disabled_info = disabled.extract(
        task_name="failed_task",
        task_goal="Open Mail",
        score=0.0,
        reason="failed",
        artifact_paths=traj_logger.artifact_paths(),
        task_metadata={"apps": ["Mail"], "tags": []},
    )
    enabled_skill, enabled_info = enabled.extract(
        task_name="failed_task",
        task_goal="Open Mail",
        score=0.0,
        reason="failed",
        artifact_paths=traj_logger.artifact_paths(),
        task_metadata={"apps": ["Mail"], "tags": []},
    )

    assert disabled_skill is None
    assert disabled_info["decision"] == "failed_task_extraction_disabled"
    assert enabled_skill is not None
    assert enabled_info["decision"] == "failed-prefix"


def test_metrics_break_down_skill_and_fallback_phase():
    collector = MetricsCollector(task_name="task", run_id="task-0", task_started_at=0.0)
    skill_step = collector.preview_step(
        step=1,
        action_type="click",
        step_started_at=0.0,
        prediction_done_at=0.05,
        total_usage={"prompt_tokens": 1, "completion_tokens": 1, "cached_tokens": 0, "total_tokens": 2},
        phase="skill",
    )
    collector.complete_step(
        step_preview=skill_step,
        step_finished_at=0.1,
        tool_latency_ms=10.0,
        tool_attempted=True,
        tool_success=True,
        tool_retry=False,
        invalid_action=False,
    )
    fallback_step = collector.preview_step(
        step=2,
        action_type="wait",
        step_started_at=0.2,
        prediction_done_at=0.4,
        total_usage={"prompt_tokens": 4, "completion_tokens": 6, "cached_tokens": 0, "total_tokens": 10},
        phase="fallback",
    )
    collector.complete_step(
        step_preview=fallback_step,
        step_finished_at=0.5,
        tool_latency_ms=10.0,
        tool_attempted=True,
        tool_success=True,
        tool_retry=False,
        invalid_action=False,
    )

    summary, _ = collector.finalize(score_recorded_at=0.6)

    assert summary["token_usage"]["avg_completion_tokens_per_step"] == 3.0
    assert summary["latency"]["avg_predict_latency_ms_per_step"] == 125.0
    assert summary["skill_phase_metrics"]["skill"]["avg_predict_latency_ms"] == 50.0
    assert summary["skill_phase_metrics"]["fallback"]["avg_completion_tokens_per_step"] == 5.0


def test_mobileworld_skills_do_not_import_nanobot_or_opengui():
    skill_root = Path("src/mobile_world/skills")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in skill_root.glob("*.py"))
    assert "nanobot" not in combined.lower()
    assert "opengui" not in combined.lower()


def test_eval_parser_accepts_skill_config_flag():
    parser = create_parser()
    args = parser.parse_args(
        [
            "eval",
            "--agent-type",
            "qwen3vl",
            "--skill-config",
            "/tmp/skills.json",
        ]
    )
    assert args.skill_config == "/tmp/skills.json"


def test_general_e2e_agent_type_is_wrapped_with_native_skills(tmp_path: Path):
    agent = create_agent(
        "general_e2e",
        model_name="qwen3.5-397b-a17b",
        llm_base_url="http://localhost/v1",
        api_key="empty",
        env=DummyEnv(),
        skill_config={"enabled": True, "mode": "learn", "store_root": str(tmp_path)},
    )

    assert isinstance(agent, SkillAugmentedAgent)
    assert isinstance(agent.base_agent, GeneralE2EAgentMCP)
    assert agent.config.learning_enabled is True


def test_runner_does_not_override_skill_success_threshold(tmp_path: Path):
    agent = FinalizeRecordingAgent()
    traj_logger = TrajLogger(str(tmp_path), "mail_task")

    _execute_single_task(
        DummyEnv(),
        agent,
        "mail_task",
        max_step=1,
        traj_logger=traj_logger,
        evaluator=DummyEvaluator(),
        task_metadata={"apps": ["Mail"], "tags": []},
    )

    assert agent.finalize_kwargs is not None
    assert "success_threshold" not in agent.finalize_kwargs


def test_aggregate_reports_skill_reuse_breakdown(tmp_path: Path):
    run_root = tmp_path / "run"
    for task_name, skill_hit, avg_completion, avg_predict, score in [
        ("task_a", True, 1.0, 20.0, 1.0),
        ("task_b", False, 5.0, 100.0, 0.0),
    ]:
        task_dir = run_root / task_name
        task_dir.mkdir(parents=True)
        metrics = {
            "token_usage": {
                "total": {"completion_tokens": int(avg_completion * 2)},
                "avg_completion_tokens_per_step": avg_completion,
            },
            "latency": {"avg_predict_latency_ms_per_step": avg_predict},
        }
        skill_summary = {
            "skill_hit": skill_hit,
            "base_agent_completion_tokens": 10,
            "skill_reuser_completion_tokens": 0,
            "skill_extractor_completion_tokens": 0,
        }
        (task_dir / SCORE_FILE_NAME).write_text(f"score: {score}\nreason: synthetic")
        (task_dir / METRICS_FILE_NAME).write_text(json.dumps(metrics), encoding="utf-8")
        (task_dir / EVALUATOR_AUDIT_FILE_NAME).write_text("{}", encoding="utf-8")
        (task_dir / SKILL_SUMMARY_FILE_NAME).write_text(
            json.dumps(skill_summary), encoding="utf-8"
        )

    report = aggregate_framework_runs(
        framework_runs={"native_skill": str(run_root)},
        success_threshold=0.99,
    )
    summary = report["leaderboard"][0]

    assert summary["avg_completion_tokens_per_step"] == 3.0
    assert summary["avg_predict_latency_ms_per_step"] == 60.0
    assert summary["skill_reuse_breakdown"]["reuse"]["avg_completion_tokens_per_step"] == 1.0
    assert summary["skill_reuse_breakdown"]["no_reuse"]["avg_predict_latency_ms_per_step"] == 100.0
    assert summary["base_agent_completion_tokens"] == 20
