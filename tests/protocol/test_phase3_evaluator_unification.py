"""Phase 3 evaluator unification protocol tests."""

import json
from pathlib import Path

from mobile_world.runtime.protocol.evaluator import (
    EvaluatorInput,
    EvidenceReference,
    TaskNativeEvaluator,
    TrajectoryJudgeVerdict,
    create_evaluator,
    list_evaluators,
)
from mobile_world.runtime.utils.trajectory_logger import (
    CANONICAL_LOG_FILE_NAME,
    CANONICAL_META_FILE_NAME,
    LOG_FILE_NAME,
    TrajLogger,
)


class DummyEnv:
    """Simple fake env exposing deterministic get_task_score API."""

    def __init__(self, score: float, reason: str):
        self._score = score
        self._reason = reason
        self.called_with: str | None = None

    def get_task_score(self, task_type: str) -> tuple[float, str]:
        self.called_with = task_type
        return self._score, self._reason


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def test_evaluator_registry_contains_task_native():
    assert "task_native" in list_evaluators()
    evaluator = create_evaluator("task_native")
    assert isinstance(evaluator, TaskNativeEvaluator)


def test_task_native_evaluator_preserves_deterministic_primary_score():
    env = DummyEnv(score=1.0, reason="task complete")
    evaluator = TaskNativeEvaluator(enable_trajectory_judge=False)
    result = evaluator.evaluate(
        env,
        EvaluatorInput(
            task_name="task_gamma",
            task_goal="finish the goal",
            run_id="task_gamma-0",
            artifact_paths={},
        ),
    )
    assert env.called_with == "task_gamma"
    assert result.score == 1.0
    assert result.reason == "task complete"
    assert result.audit.primary_signal == "task_native"
    assert result.audit.config["enable_trajectory_judge"] is False
    assert any(check.name == "reason_non_empty" and check.passed for check in result.audit.consistency_checks)
    assert any(ref.ref_type == "task_eval" for ref in result.evidence_refs)


def test_task_native_evaluator_records_judge_config_and_disagreement():
    def fake_judge(_, config):
        return TrajectoryJudgeVerdict(
            available=True,
            success=False,
            reason="judge saw missing confirmation",
            model=config.judge_model,
            evidence_refs=[
                EvidenceReference(
                    ref_id="judge-1",
                    ref_type="judge",
                    uri="memory://judge",
                    description="Mocked judge evidence",
                )
            ],
        )

    env = DummyEnv(score=1.0, reason="task complete")
    evaluator = TaskNativeEvaluator(
        enable_trajectory_judge=True,
        judge_model="mock-judge",
        judge_api_key="sk-test",
        judge_api_base="http://judge.local/v1",
        judge_fn=fake_judge,
    )
    result = evaluator.evaluate(
        env,
        EvaluatorInput(
            task_name="task_delta",
            task_goal="finish the goal",
            run_id="task_delta-0",
            artifact_paths={"canonical_log_path": "/tmp/fake-trace.jsonl"},
        ),
    )

    assert result.score == 1.0
    assert result.audit.config["enable_trajectory_judge"] is True
    assert result.audit.config["judge_model"] == "mock-judge"
    assert result.audit.judge is not None
    assert result.audit.judge.available is True
    assert result.audit.judge.model == "mock-judge"
    judge_agreement = next(
        check for check in result.audit.consistency_checks if check.name == "judge_agreement"
    )
    assert judge_agreement.passed is False
    assert any(ref.ref_type == "judge" for ref in result.evidence_refs)


def test_logger_persists_evaluator_audit_and_score_evidence(tmp_path: Path):
    traj_logger = TrajLogger(str(tmp_path), "task_epsilon")
    audit = {
        "evaluator_name": "task_native",
        "primary_signal": "task_native",
        "score": 0.75,
        "reason": "partially complete",
        "evidence_refs": [{"ref_id": "deterministic-task-eval", "ref_type": "task_eval"}],
        "consistency_checks": [{"name": "reason_non_empty", "passed": True}],
    }
    traj_logger.log_evaluator_audit(audit)
    traj_logger.log_score(
        score=0.75,
        reason="partially complete",
        evaluator_name="task_native",
        evidence_refs=[{"ref_id": "deterministic-task-eval", "ref_type": "task_eval"}],
    )

    task_dir = tmp_path / "task_epsilon"
    legacy = _read_json(task_dir / LOG_FILE_NAME)
    meta = _read_json(task_dir / CANONICAL_META_FILE_NAME)
    events = _read_jsonl(task_dir / CANONICAL_LOG_FILE_NAME)

    assert legacy["0"]["evaluator_audit"]["evaluator_name"] == "task_native"
    assert meta["evaluator_audit"]["primary_signal"] == "task_native"
    assert events[-2]["type"] == "evaluator_audit"
    assert events[-1]["type"] == "score"
    assert events[-1]["evaluator"] == "task_native"
    assert events[-1]["evidence_refs"][0]["ref_type"] == "task_eval"

