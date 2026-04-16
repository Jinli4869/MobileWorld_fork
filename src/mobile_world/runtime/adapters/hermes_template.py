"""Hermes adapter scaffold template."""

from __future__ import annotations

from typing import Any

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


class HermesTemplateAdapter(FrameworkAdapter):
    """Scaffold adapter for future Hermes integration."""

    def __init__(
        self,
        *,
        model_name: str | None = None,
        llm_base_url: str | None = None,
        api_key: str | None = None,
        **_: Any,
    ) -> None:
        self.model_name = model_name
        self.llm_base_url = llm_base_url
        self.api_key = api_key
        self._initialized = False

    def initialize(self, payload: AdapterInitializeInput) -> AdapterInitializeResult:
        self._initialized = True
        # TODO(framework): initialize Hermes planner/executor state.
        return AdapterInitializeResult(
            ok=True,
            message=f"Hermes template initialized for {payload.task_name}",
            adapter_state={"template": True, "framework": "hermes"},
        )

    def step(self, payload: AdapterStepInput) -> AdapterStepResult:
        if not self._initialized:
            return AdapterStepResult(
                prediction=None,
                action={"action_type": "unknown"},
                done=True,
                info={"error": "adapter_not_initialized"},
            )
        # TODO(framework): wire Hermes action parser to canonical action payload.
        return AdapterStepResult(
            prediction="hermes_template_wait_fallback",
            action={"action_type": "wait"},
            done=False,
            info={"framework": "hermes", "template": True, "step": payload.step_index},
        )

    def finalize(self, payload: AdapterFinalizeInput) -> AdapterFinalizeResult:
        self._initialized = False
        # TODO(framework): export Hermes execution metadata.
        return AdapterFinalizeResult(
            ok=True,
            summary=f"Hermes template finalized for {payload.task_name}",
            final_state={"score": payload.score, "reason": payload.reason},
        )

    def emit_artifacts(self, run_id: str, output_dir: str) -> AdapterArtifactsResult:
        _ = (run_id, output_dir)
        # TODO(framework): emit framework-specific artifacts.
        return AdapterArtifactsResult(artifacts=[])
