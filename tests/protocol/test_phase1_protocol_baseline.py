"""Phase 1 protocol baseline contract tests."""

from dataclasses import dataclass

import pytest

from mobile_world.agents.registry import (
    AGENT_CONFIGS,
    create_framework_adapter,
    list_framework_profiles,
    register_adapter_profile,
)
from mobile_world.runtime.protocol.adapter import (
    AdapterArtifactsResult,
    AdapterFinalizeInput,
    AdapterFinalizeResult,
    AdapterInitializeInput,
    AdapterInitializeResult,
    AdapterStepInput,
    AdapterStepResult,
    FrameworkAdapter,
)
from mobile_world.runtime.protocol.registry import AdapterProfile, clear_adapters, register_adapter
from mobile_world.runtime.protocol.validation import (
    ProtocolValidationError,
    run_protocol_preflight,
    validate_adapter_contracts,
)


class DummyAdapter(FrameworkAdapter):
    """Minimal valid adapter for contract tests."""

    def initialize(self, payload: AdapterInitializeInput) -> AdapterInitializeResult:
        return AdapterInitializeResult(ok=True, message=f"init:{payload.task_name}")

    def step(self, payload: AdapterStepInput) -> AdapterStepResult:
        return AdapterStepResult(
            prediction="ok",
            action={"action_type": "wait"},
            done=True,
            info={"step_index": payload.step_index},
        )

    def finalize(self, payload: AdapterFinalizeInput) -> AdapterFinalizeResult:
        return AdapterFinalizeResult(ok=True, summary="done")

    def emit_artifacts(self, run_id: str, output_dir: str) -> AdapterArtifactsResult:
        return AdapterArtifactsResult(artifacts=[])


@dataclass
class DummyFactoryAdapter(DummyAdapter):
    model_name: str = "test-model"


def _dummy_factory(**kwargs):
    return DummyFactoryAdapter(model_name=kwargs["model_name"])


def test_builtin_profiles_registered():
    profiles = set(list_framework_profiles())
    expected = set(AGENT_CONFIGS.keys())
    assert expected.issubset(profiles)


def test_adapter_contract_validation_reports_invalid_registration():
    clear_adapters()
    register_adapter(
        profile=AdapterProfile(
            name="invalid-adapter",
            framework="test",
            capabilities=[],
            metadata={},
        ),
        adapter_class=object,  # intentionally invalid
    )
    report = validate_adapter_contracts()
    assert report.ok is False
    assert any(issue.code == "ADPT-INVALID-CLASS" for issue in report.issues)


def test_preflight_raises_when_no_registration():
    clear_adapters()
    with pytest.raises(ProtocolValidationError):
        run_protocol_preflight(strict=True)


def test_preflight_non_strict_returns_report():
    clear_adapters()
    report = run_protocol_preflight(strict=False)
    assert report.ok is False
    assert any(issue.code == "ADPT-NO-REGISTRATION" for issue in report.issues)


def test_create_framework_adapter_prefers_registered_factory():
    register_adapter_profile(
        "dummy-framework",
        framework="test",
        adapter_class=DummyAdapter,
        factory=_dummy_factory,
        capabilities=["test"],
        metadata={"source": "tests"},
        overwrite=True,
    )
    adapter = create_framework_adapter(
        "dummy-framework",
        model_name="model-x",
        llm_base_url="http://localhost:1234",
    )
    assert isinstance(adapter, DummyFactoryAdapter)
    assert adapter.model_name == "model-x"
