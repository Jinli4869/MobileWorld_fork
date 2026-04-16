"""Evaluator contracts and registry for framework-agnostic scoring."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from loguru import logger
from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    """Return UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


class EvidenceReference(BaseModel):
    """Machine-readable reference to score evidence."""

    ref_id: str
    ref_type: str
    uri: str | None = None
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConsistencyCheck(BaseModel):
    """One evaluator consistency assertion."""

    name: str
    passed: bool
    details: str = ""


class TrajectoryJudgeConfig(BaseModel):
    """Optional trajectory judge backend configuration."""

    enable_trajectory_judge: bool = False
    judge_model: str = "qwen3-vl-plus"
    judge_api_key: str | None = None
    judge_api_base: str | None = None
    judge_timeout_seconds: float = 30.0
    max_step_events: int = 30
    success_threshold: float = 0.99


class TrajectoryJudgeVerdict(BaseModel):
    """Judge output normalized for evaluator audit."""

    available: bool = False
    success: bool | None = None
    reason: str = ""
    model: str | None = None
    error: str | None = None
    evidence_refs: list[EvidenceReference] = Field(default_factory=list)


class EvaluatorInput(BaseModel):
    """Evaluator input payload for one task run."""

    task_name: str
    task_goal: str | None = None
    run_id: str
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationAudit(BaseModel):
    """Audit payload persisted for every score."""

    schema_version: str = "1.0.0"
    created_at: str = Field(default_factory=utc_now_iso)
    evaluator_name: str
    primary_signal: str
    score: float
    reason: str
    evidence_refs: list[EvidenceReference] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    deterministic: dict[str, Any] = Field(default_factory=dict)
    judge: TrajectoryJudgeVerdict | None = None
    consistency_checks: list[ConsistencyCheck] = Field(default_factory=list)


class EvaluatorResult(BaseModel):
    """Framework-agnostic evaluator output."""

    evaluator_name: str
    score: float
    reason: str
    evidence_refs: list[EvidenceReference] = Field(default_factory=list)
    audit: EvaluationAudit


class BaseEvaluator(ABC):
    """Base evaluator contract."""

    name: str = "base"

    @abstractmethod
    def evaluate(self, env: Any, payload: EvaluatorInput) -> EvaluatorResult:
        """Evaluate one task run and return canonical scoring output."""
        raise NotImplementedError


def _extract_json_obj(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return text
    return text[start : end + 1]


def _load_step_events(path: Path, limit: int = 30) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("type") == "step":
                rows.append(row)
    return rows[-limit:] if limit > 0 else rows


def _default_trajectory_judge(payload: EvaluatorInput, config: TrajectoryJudgeConfig) -> TrajectoryJudgeVerdict:
    if not config.judge_api_key:
        return TrajectoryJudgeVerdict(
            available=False,
            model=config.judge_model,
            reason="judge_api_key_missing",
            error="judge_api_key_missing",
        )
    canonical_log_path = payload.artifact_paths.get("canonical_log_path")
    if not canonical_log_path:
        return TrajectoryJudgeVerdict(
            available=False,
            model=config.judge_model,
            reason="canonical_log_path_missing",
            error="canonical_log_path_missing",
        )
    trace_path = Path(canonical_log_path)
    if not trace_path.exists():
        return TrajectoryJudgeVerdict(
            available=False,
            model=config.judge_model,
            reason="canonical_log_not_found",
            error="canonical_log_not_found",
        )

    step_events = _load_step_events(trace_path, limit=config.max_step_events)
    if not step_events:
        return TrajectoryJudgeVerdict(
            available=False,
            model=config.judge_model,
            reason="no_step_events",
            error="no_step_events",
        )

    try:
        from openai import OpenAI
    except ImportError:
        return TrajectoryJudgeVerdict(
            available=False,
            model=config.judge_model,
            reason="openai_sdk_unavailable",
            error="openai_sdk_unavailable",
        )

    excerpt = [
        {
            "step": row.get("step"),
            "prediction": row.get("prediction"),
            "action_type": row.get("action_type"),
            "tool_call": row.get("tool_call"),
            "ask_user_response": row.get("ask_user_response"),
        }
        for row in step_events
    ]
    system_prompt = (
        "You are a benchmark evaluator. Return strict JSON only: "
        '{"success": true/false, "reason": "one sentence", "evidence_refs": []}.'
    )
    user_prompt = (
        f"task_name={payload.task_name}\n"
        f"task_goal={payload.task_goal or ''}\n"
        f"run_id={payload.run_id}\n"
        f"step_events={json.dumps(excerpt, ensure_ascii=False)}\n"
        "Judge whether the task succeeded from the trace evidence."
    )

    try:
        client = (
            OpenAI(api_key=config.judge_api_key, base_url=config.judge_api_base)
            if config.judge_api_base
            else OpenAI(api_key=config.judge_api_key)
        )
        response = client.chat.completions.create(
            model=config.judge_model,
            temperature=0.0,
            timeout=config.judge_timeout_seconds,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            return TrajectoryJudgeVerdict(
                available=False,
                model=config.judge_model,
                reason="empty_judge_output",
                error="empty_judge_output",
            )
        obj = json.loads(_extract_json_obj(content))
        success = bool(obj.get("success", False))
        reason = str(obj.get("reason", "")).strip() or "judge_reason_missing"
        evidence_refs = []
        for index, item in enumerate(obj.get("evidence_refs", [])):
            if isinstance(item, dict):
                evidence_refs.append(
                    EvidenceReference(
                        ref_id=str(item.get("ref_id", f"judge-evidence-{index}")),
                        ref_type=str(item.get("ref_type", "judge")),
                        uri=item.get("uri"),
                        description=str(item.get("description", "")),
                        metadata=dict(item.get("metadata", {})),
                    )
                )
        if not evidence_refs:
            evidence_refs.append(
                EvidenceReference(
                    ref_id="judge-verdict",
                    ref_type="judge",
                    uri=canonical_log_path,
                    description="Trajectory judge verdict",
                    metadata={"model": config.judge_model},
                )
            )
        return TrajectoryJudgeVerdict(
            available=True,
            success=success,
            reason=reason,
            model=config.judge_model,
            evidence_refs=evidence_refs,
        )
    except Exception as exc:
        logger.warning("Trajectory judge invocation failed: {}", exc)
        return TrajectoryJudgeVerdict(
            available=False,
            model=config.judge_model,
            reason=f"judge_call_failed:{type(exc).__name__}",
            error=str(exc),
        )


class TaskNativeEvaluator(BaseEvaluator):
    """Bridge deterministic `env.get_task_score` into canonical evaluator contract."""

    name = "task_native"

    def __init__(
        self,
        *,
        enable_trajectory_judge: bool = False,
        judge_model: str = "qwen3-vl-plus",
        judge_api_key: str | None = None,
        judge_api_base: str | None = None,
        judge_timeout_seconds: float = 30.0,
        success_threshold: float = 0.99,
        judge_fn: Callable[[EvaluatorInput, TrajectoryJudgeConfig], TrajectoryJudgeVerdict] | None = None,
    ) -> None:
        self.judge_config = TrajectoryJudgeConfig(
            enable_trajectory_judge=enable_trajectory_judge,
            judge_model=judge_model,
            judge_api_key=judge_api_key,
            judge_api_base=judge_api_base,
            judge_timeout_seconds=judge_timeout_seconds,
            success_threshold=success_threshold,
        )
        self._judge_fn = judge_fn or _default_trajectory_judge

    def _run_trajectory_judge(self, payload: EvaluatorInput) -> TrajectoryJudgeVerdict:
        if not self.judge_config.enable_trajectory_judge:
            return TrajectoryJudgeVerdict(
                available=False,
                model=self.judge_config.judge_model,
                reason="trajectory_judge_disabled",
                error="trajectory_judge_disabled",
            )
        return self._judge_fn(payload, self.judge_config)

    def _build_consistency_checks(
        self,
        *,
        score: float,
        reason: str,
        evidence_refs: list[EvidenceReference],
        judge_verdict: TrajectoryJudgeVerdict | None,
    ) -> list[ConsistencyCheck]:
        checks = [
            ConsistencyCheck(
                name="reason_non_empty",
                passed=bool(reason.strip()),
                details="Deterministic reason should be non-empty.",
            ),
            ConsistencyCheck(
                name="evidence_refs_present",
                passed=len(evidence_refs) > 0,
                details="At least one evidence reference must be attached to every score.",
            ),
        ]
        if judge_verdict is None:
            checks.append(
                ConsistencyCheck(
                    name="trajectory_judge_enabled",
                    passed=True,
                    details="Trajectory judge disabled by config.",
                )
            )
            return checks

        checks.append(
            ConsistencyCheck(
                name="trajectory_judge_available",
                passed=judge_verdict.available,
                details=judge_verdict.reason or "",
            )
        )
        if judge_verdict.available and judge_verdict.success is not None:
            deterministic_success = score >= self.judge_config.success_threshold
            checks.append(
                ConsistencyCheck(
                    name="judge_agreement",
                    passed=deterministic_success == judge_verdict.success,
                    details=(
                        f"deterministic_success={deterministic_success}, "
                        f"judge_success={judge_verdict.success}"
                    ),
                )
            )
        return checks

    def evaluate(self, env: Any, payload: EvaluatorInput) -> EvaluatorResult:
        score, reason = env.get_task_score(task_type=payload.task_name)
        score = float(score)
        reason = str(reason)

        evidence_refs = [
            EvidenceReference(
                ref_id="deterministic-task-eval",
                ref_type="task_eval",
                description="Primary deterministic task score from MobileWorld task server.",
                metadata={"task_name": payload.task_name},
            )
        ]
        if payload.artifact_paths.get("canonical_log_path"):
            evidence_refs.append(
                EvidenceReference(
                    ref_id="canonical-trace",
                    ref_type="trajectory",
                    uri=payload.artifact_paths["canonical_log_path"],
                    description="Canonical trajectory used for audit and optional judge checks.",
                )
            )

        judge_verdict: TrajectoryJudgeVerdict | None = None
        if self.judge_config.enable_trajectory_judge:
            judge_verdict = self._run_trajectory_judge(payload)
            if judge_verdict.available:
                evidence_refs.extend(judge_verdict.evidence_refs)

        consistency_checks = self._build_consistency_checks(
            score=score,
            reason=reason,
            evidence_refs=evidence_refs,
            judge_verdict=judge_verdict,
        )
        audit = EvaluationAudit(
            evaluator_name=self.name,
            primary_signal="task_native",
            score=score,
            reason=reason,
            evidence_refs=evidence_refs,
            config={
                "enable_trajectory_judge": self.judge_config.enable_trajectory_judge,
                "judge_model": self.judge_config.judge_model,
                "judge_api_base": self.judge_config.judge_api_base,
                "judge_api_key_set": bool(self.judge_config.judge_api_key),
                "judge_timeout_seconds": self.judge_config.judge_timeout_seconds,
                "success_threshold": self.judge_config.success_threshold,
            },
            deterministic={
                "score": score,
                "reason": reason,
                "source": "env.get_task_score",
            },
            judge=judge_verdict,
            consistency_checks=consistency_checks,
        )
        return EvaluatorResult(
            evaluator_name=self.name,
            score=score,
            reason=reason,
            evidence_refs=evidence_refs,
            audit=audit,
        )


EvaluatorFactory = Callable[..., BaseEvaluator]
_EVALUATOR_REGISTRY: dict[str, EvaluatorFactory] = {}


def register_evaluator(name: str, factory: EvaluatorFactory, *, overwrite: bool = False) -> None:
    """Register evaluator factory by name."""
    if not overwrite and name in _EVALUATOR_REGISTRY:
        raise ValueError(f"Evaluator already registered: {name}")
    _EVALUATOR_REGISTRY[name] = factory


def get_evaluator_factory(name: str) -> EvaluatorFactory:
    """Return evaluator factory for name."""
    if name not in _EVALUATOR_REGISTRY:
        raise KeyError(f"Evaluator not registered: {name}")
    return _EVALUATOR_REGISTRY[name]


def create_evaluator(name: str, **kwargs: Any) -> BaseEvaluator:
    """Create evaluator instance from registry."""
    factory = get_evaluator_factory(name)
    return factory(**kwargs)


def list_evaluators() -> list[str]:
    """List registered evaluator names."""
    return sorted(_EVALUATOR_REGISTRY.keys())


def clear_evaluators() -> None:
    """Clear evaluator registry."""
    _EVALUATOR_REGISTRY.clear()


register_evaluator("task_native", TaskNativeEvaluator, overwrite=True)

