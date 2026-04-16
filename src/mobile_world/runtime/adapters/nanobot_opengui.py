"""Nanobot/OpenGUI reference adapter implementation."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from mobile_world.runtime.protocol.adapter import (
    AdapterArtifactsResult,
    AdapterFinalizeInput,
    AdapterFinalizeResult,
    AdapterInitializeInput,
    AdapterInitializeResult,
    AdapterStepInput,
    AdapterStepResult,
    ArtifactRecord,
    FrameworkAdapter,
)

_TERMINAL_ACTIONS = {"finished", "answer", "unknown", "error_env"}


def _resolve_nanobot_fork_path(explicit: str | None) -> Path | None:
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if candidate.exists():
            return candidate
        return None
    env_candidate = os.getenv("NANOBOT_FORK_PATH")
    if env_candidate:
        path = Path(env_candidate).expanduser().resolve()
        if path.exists():
            return path
    default_candidate = Path("~/Project/nanobot_fork").expanduser()
    if default_candidate.exists():
        return default_candidate.resolve()
    return None


def _load_opengui_eval_function(root: Path | None) -> Callable[..., dict[str, Any]] | None:
    if root is None:
        return None
    eval_py = root / "opengui" / "evaluation.py"
    if not eval_py.exists():
        return None
    try:
        module_name = f"_mobile_world_opengui_eval_{hash(str(eval_py))}"
        spec = importlib.util.spec_from_file_location(module_name, str(eval_py))
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fn = getattr(module, "evaluate_gui_trajectory_sync", None)
        if callable(fn):
            return fn
    except ModuleNotFoundError as exc:
        logger.warning(
            "OpenGUI evaluation dependency missing ({}). Optional judge path disabled.",
            exc,
        )
    except Exception as exc:
        logger.warning("Failed to load OpenGUI evaluation module from {}: {}", eval_py, exc)
    return None


class NanobotOpenGUIAdapter(FrameworkAdapter):
    """Reference adapter that preserves MobileWorld runtime ownership."""

    def __init__(
        self,
        *,
        model_name: str | None = None,
        llm_base_url: str | None = None,
        api_key: str | None = None,
        nanobot_fork_path: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.llm_base_url = llm_base_url
        self.api_key = api_key
        self.nanobot_root = _resolve_nanobot_fork_path(nanobot_fork_path)
        self._opengui_eval = _load_opengui_eval_function(self.nanobot_root)
        self._initialized = False
        self._state: dict[str, Any] = {}
        self._artifacts: list[ArtifactRecord] = []

    @staticmethod
    def _normalize_action(action: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(action, dict):
            return {"action_type": "wait"}
        action_type = action.get("action_type")
        if not isinstance(action_type, str) or not action_type.strip():
            normalized = dict(action)
            normalized["action_type"] = "wait"
            return normalized
        return dict(action)

    def initialize(self, payload: AdapterInitializeInput) -> AdapterInitializeResult:
        self._initialized = True
        self._state = {
            "task_name": payload.task_name,
            "task_goal": payload.task_goal,
            "run_id": payload.run_id,
            "options": dict(payload.options),
            "steps": 0,
        }
        return AdapterInitializeResult(
            ok=True,
            message="nanobot_opengui reference adapter initialized",
            adapter_state={
                "framework": "nanobot_opengui",
                "nanobot_root": str(self.nanobot_root) if self.nanobot_root else None,
                "opengui_eval_available": self._opengui_eval is not None,
            },
        )

    def step(self, payload: AdapterStepInput) -> AdapterStepResult:
        if not self._initialized:
            return AdapterStepResult(
                prediction=None,
                action={"action_type": "unknown"},
                done=True,
                info={"error": "adapter_not_initialized"},
            )

        self._state["steps"] = int(self._state.get("steps", 0)) + 1
        obs = payload.observation if isinstance(payload.observation, dict) else {}
        injected_action = obs.get("nanobot_action")
        injected_prediction = obs.get("nanobot_prediction")
        injected_done = bool(obs.get("nanobot_done", False))
        injected_info = obs.get("nanobot_info")

        action = self._normalize_action(injected_action if isinstance(injected_action, dict) else None)
        prediction = (
            str(injected_prediction)
            if injected_prediction is not None
            else "nanobot_reference_adapter_fallback"
        )
        done = injected_done or action.get("action_type") in _TERMINAL_ACTIONS
        info = {
            "framework": "nanobot_opengui",
            "reference_mode": True,
            "opengui_eval_available": self._opengui_eval is not None,
        }
        if isinstance(injected_info, dict):
            info.update(injected_info)

        return AdapterStepResult(prediction=prediction, action=action, done=done, info=info)

    def _run_optional_opengui_evaluation(
        self,
        *,
        payload: AdapterFinalizeInput,
    ) -> dict[str, Any] | None:
        if self._opengui_eval is None:
            return None
        options = self._state.get("options", {})
        if not bool(options.get("enable_opengui_judge", False)):
            return None

        api_key = (
            options.get("judge_api_key")
            or options.get("api_key")
            or self.api_key
            or os.getenv("JUDGE_API_KEY")
            or os.getenv("API_KEY")
        )
        if not api_key:
            return {"success": False, "reason": "missing_judge_api_key"}

        trace_path = options.get("trace_path")
        if trace_path is None:
            output_dir = Path(options.get("output_dir", "."))
            trace_path = output_dir / "traj.canonical.jsonl"
        trace_path = Path(trace_path).expanduser()
        if not trace_path.exists():
            return {"success": False, "reason": "trace_path_not_found", "trace_path": str(trace_path)}

        output_dir = Path(options.get("output_dir", ".")).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{payload.run_id}.opengui_eval.json"
        result = self._opengui_eval(
            instruction=self._state.get("task_goal", payload.task_name),
            trace_path=trace_path,
            model=str(options.get("judge_model", "qwen3-vl-plus")),
            api_key=api_key,
            api_base=options.get("judge_api_base"),
            task_id=payload.task_name,
            output_path=output_path,
        )
        self._artifacts.append(
            ArtifactRecord(
                path=str(output_path),
                artifact_type="opengui_judge",
                description="Optional OpenGUI judge output produced by reference adapter",
                metadata={"task_name": payload.task_name, "run_id": payload.run_id},
            )
        )
        return result

    def finalize(self, payload: AdapterFinalizeInput) -> AdapterFinalizeResult:
        judge_result = None
        try:
            judge_result = self._run_optional_opengui_evaluation(payload=payload)
        except Exception:
            logger.exception("Optional OpenGUI judge invocation failed")
            judge_result = {"success": False, "reason": "opengui_judge_exception"}

        self._initialized = False
        final_state = {
            "score": payload.score,
            "reason": payload.reason,
            "metrics": payload.metrics,
            "steps": self._state.get("steps", 0),
        }
        if judge_result is not None:
            final_state["opengui_judge"] = judge_result

        summary = f"nanobot_opengui adapter finalized for task {payload.task_name}"
        if judge_result is not None:
            summary += " (with optional OpenGUI judge)"
        return AdapterFinalizeResult(ok=True, summary=summary, final_state=final_state)

    def emit_artifacts(self, run_id: str, output_dir: str) -> AdapterArtifactsResult:
        _ = (run_id, output_dir)  # output_dir reserved for future adapter-side exports
        return AdapterArtifactsResult(artifacts=list(self._artifacts))
