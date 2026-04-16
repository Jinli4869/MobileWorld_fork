"""OpenClaw adapter scaffold template."""

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


class OpenClawTemplateAdapter(FrameworkAdapter):
    """Scaffold adapter for future OpenClaw integration."""

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
        self._step_count = 0

    def initialize(self, payload: AdapterInitializeInput) -> AdapterInitializeResult:
        self._initialized = True
        self._step_count = 0
        # TODO(framework): initialize OpenClaw runtime/session with task metadata.
        return AdapterInitializeResult(
            ok=True,
            message=f"OpenClaw template initialized for {payload.task_name}",
            adapter_state={"template": True, "framework": "openclaw"},
        )

    def step(self, payload: AdapterStepInput) -> AdapterStepResult:
        self._step_count += 1
        if not self._initialized:
            return AdapterStepResult(
                prediction=None,
                action={"action_type": "unknown"},
                done=True,
                info={"error": "adapter_not_initialized"},
            )
        # TODO(framework): map OpenClaw action output to MobileWorld canonical JSONAction payload.
        return AdapterStepResult(
            prediction="openclaw_template_wait_fallback",
            action={"action_type": "wait"},
            done=False,
            info={"framework": "openclaw", "template": True, "step": payload.step_index},
        )

    def finalize(self, payload: AdapterFinalizeInput) -> AdapterFinalizeResult:
        self._initialized = False
        # TODO(framework): flush session state and optional traces from OpenClaw runtime.
        return AdapterFinalizeResult(
            ok=True,
            summary=f"OpenClaw template finalized for {payload.task_name}",
            final_state={"score": payload.score, "reason": payload.reason, "steps": self._step_count},
        )

    def emit_artifacts(self, run_id: str, output_dir: str) -> AdapterArtifactsResult:
        _ = (run_id, output_dir)
        # TODO(framework): emit framework-native trace/log artifacts.
        return AdapterArtifactsResult(artifacts=[])
