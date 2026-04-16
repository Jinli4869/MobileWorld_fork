"""Protocol pre-flight validation gates for adapter and canonical schema contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from mobile_world.runtime.protocol.adapter import FrameworkAdapter
from mobile_world.runtime.protocol.events import (
    CANONICAL_TRAJECTORY_SCHEMA_VERSION,
    CanonicalScoreEvent,
    CanonicalStepEvent,
)
from mobile_world.runtime.protocol.registry import list_registrations


class ValidationIssue(BaseModel):
    """Single validation issue."""

    code: str
    message: str
    remedy: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    """Validation result report."""

    ok: bool = True
    checked_adapters: list[str] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)

    def add_issue(
        self,
        *,
        code: str,
        message: str,
        remedy: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.ok = False
        self.issues.append(
            ValidationIssue(
                code=code,
                message=message,
                remedy=remedy,
                context=context or {},
            )
        )


class ProtocolValidationError(RuntimeError):
    """Raised when protocol pre-flight validation fails."""

    def __init__(self, report: ValidationReport):
        self.report = report
        lines = ["Protocol pre-flight validation failed:"]
        for issue in report.issues:
            suffix = f" Remedy: {issue.remedy}" if issue.remedy else ""
            lines.append(f"- [{issue.code}] {issue.message}.{suffix}")
        super().__init__("\n".join(lines))


def validate_adapter_contracts() -> ValidationReport:
    """Validate registered adapters implement required lifecycle contract."""
    report = ValidationReport()
    registrations = list_registrations()
    if not registrations:
        report.add_issue(
            code="ADPT-NO-REGISTRATION",
            message="No adapters registered in protocol registry",
            remedy="Register built-in or framework adapters before evaluation",
        )
        return report

    for registration in registrations:
        profile = registration.profile
        report.checked_adapters.append(profile.name)
        adapter_class = registration.adapter_class
        if not issubclass(adapter_class, FrameworkAdapter):
            report.add_issue(
                code="ADPT-INVALID-CLASS",
                message=f"Adapter '{profile.name}' does not expose a valid FrameworkAdapter class",
                remedy="Register a class inheriting FrameworkAdapter",
            )
            continue

        missing = [
            method
            for method in ("initialize", "step", "finalize", "emit_artifacts")
            if getattr(adapter_class, method, None) is None
        ]
        if missing:
            report.add_issue(
                code="ADPT-LIFECYCLE-INCOMPLETE",
                message=f"Adapter '{profile.name}' missing lifecycle methods: {', '.join(missing)}",
                remedy="Implement initialize/step/finalize/emit_artifacts on adapter class",
            )

    return report


def validate_canonical_schema() -> ValidationReport:
    """Validate canonical schema objects are constructible and versioned."""
    report = ValidationReport()
    try:
        step = CanonicalStepEvent(
            task_name="schema_check_task",
            task_goal="schema_check_goal",
            run_id="schema-check-run",
            step=1,
            prediction="ok",
            action={"action_type": "wait"},
        )
        score = CanonicalScoreEvent(
            task_name="schema_check_task",
            run_id="schema-check-run",
            score=1.0,
            reason="schema_check",
        )
        if step.schema_version != CANONICAL_TRAJECTORY_SCHEMA_VERSION:
            report.add_issue(
                code="TRCE-SCHEMA-VERSION-MISMATCH",
                message="Canonical step schema version mismatch",
                remedy="Align step event schema_version with canonical constant",
            )
        if score.schema_version != CANONICAL_TRAJECTORY_SCHEMA_VERSION:
            report.add_issue(
                code="TRCE-SCORE-SCHEMA-VERSION-MISMATCH",
                message="Canonical score schema version mismatch",
                remedy="Align score event schema_version with canonical constant",
            )
    except Exception as exc:  # pragma: no cover - exercised in tests
        report.add_issue(
            code="TRCE-SCHEMA-CONSTRUCTION-FAILED",
            message=f"Canonical schema object construction failed: {type(exc).__name__}: {exc}",
            remedy="Fix canonical event model definitions",
        )
    return report


def run_protocol_preflight(*, strict: bool = True) -> ValidationReport:
    """Run full protocol pre-flight checks."""
    final = ValidationReport()
    adapter_report = validate_adapter_contracts()
    schema_report = validate_canonical_schema()

    final.checked_adapters.extend(adapter_report.checked_adapters)
    final.issues.extend(adapter_report.issues)
    final.issues.extend(schema_report.issues)
    final.ok = not final.issues

    if strict and not final.ok:
        raise ProtocolValidationError(final)
    return final
