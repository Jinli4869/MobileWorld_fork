"""Phase 4 nanobot reference integration protocol tests."""

import json
from pathlib import Path

from PIL import Image

from mobile_world.agents.registry import create_framework_adapter
from mobile_world.core.runner import _execute_single_task
from mobile_world.runtime.adapters.nanobot_opengui import NanobotOpenGUIAdapter
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
from mobile_world.runtime.utils.models import Observation
from mobile_world.runtime.utils.trajectory_logger import (
    CANONICAL_LOG_FILE_NAME,
    CANONICAL_META_FILE_NAME,
    LOG_FILE_NAME,
    METRICS_FILE_NAME,
    TrajLogger,
)


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


class DummyEnv:
    def __init__(self):
        self.actions: list[str] = []

    def get_task_goal(self, task_type: str) -> str:
        return f"goal:{task_type}"

    def initialize_task(self, task_name: str) -> Observation:
        _ = task_name
        return Observation(screenshot=Image.new("RGB", (20, 20), color="white"))

    def execute_action(self, action):
        self.actions.append(action.action_type)
        return Observation(screenshot=Image.new("RGB", (20, 20), color="white"))

    def get_task_score(self, task_type: str) -> tuple[float, str]:
        return 1.0, f"ok:{task_type}"

    def tear_down_task(self, task_type: str):
        return {"status": "success", "task_type": task_type}


class ScriptedAdapter(FrameworkAdapter):
    def __init__(self) -> None:
        self.initialized = False
        self.finalized = False
        self.final_metrics: dict | None = None

    def initialize(self, payload: AdapterInitializeInput) -> AdapterInitializeResult:
        self.initialized = True
        return AdapterInitializeResult(ok=True, message=f"init:{payload.task_name}")

    def step(self, payload: AdapterStepInput) -> AdapterStepResult:
        _ = payload
        return AdapterStepResult(
            prediction="adapter-predict",
            action={"action_type": "wait"},
            done=True,
            info={
                "token_usage": {
                    "prompt_tokens": 2,
                    "completion_tokens": 1,
                    "cached_tokens": 0,
                    "total_tokens": 3,
                }
            },
        )

    def finalize(self, payload: AdapterFinalizeInput) -> AdapterFinalizeResult:
        self.finalized = True
        self.final_metrics = payload.metrics
        return AdapterFinalizeResult(ok=True, summary="done")

    def emit_artifacts(self, run_id: str, output_dir: str) -> AdapterArtifactsResult:
        return AdapterArtifactsResult(
            artifacts=[
                ArtifactRecord(
                    path=str(Path(output_dir) / f"{run_id}.adapter.json"),
                    artifact_type="adapter_trace",
                    description="scripted adapter artifact",
                )
            ]
        )


def test_create_framework_adapter_nanobot_profile():
    adapter = create_framework_adapter(
        "nanobot_opengui",
        model_name="test-model",
        llm_base_url="http://localhost:8080/v1",
    )
    assert isinstance(adapter, NanobotOpenGUIAdapter)
    init = adapter.initialize(
        AdapterInitializeInput(
            task_name="task_phase4",
            task_goal="finish task",
            run_id="task_phase4-0",
            options={},
        )
    )
    assert init.ok is True
    step = adapter.step(
        AdapterStepInput(
            run_id="task_phase4-0",
            task_name="task_phase4",
            step_index=1,
            observation={"nanobot_done": True},
        )
    )
    assert step.action["action_type"] == "wait"
    assert step.done is True


def test_runner_executes_with_framework_adapter_and_preserves_artifact_shape(tmp_path: Path):
    env = DummyEnv()
    adapter = ScriptedAdapter()
    traj_logger = TrajLogger(str(tmp_path), "task_phase4")

    steps, score = _execute_single_task(
        env=env,
        agent=None,
        task_name="task_phase4",
        max_step=5,
        traj_logger=traj_logger,
        framework_adapter=adapter,
    )

    task_dir = tmp_path / "task_phase4"
    legacy = _read_json(task_dir / LOG_FILE_NAME)
    meta = _read_json(task_dir / CANONICAL_META_FILE_NAME)
    events = _read_jsonl(task_dir / CANONICAL_LOG_FILE_NAME)
    metrics = _read_json(task_dir / METRICS_FILE_NAME)

    assert steps == 1
    assert score == 1.0
    assert adapter.initialized is True
    assert adapter.finalized is True
    assert adapter.final_metrics is not None
    assert legacy["0"]["adapter_artifacts"][0]["artifact_type"] == "adapter_trace"
    assert meta["adapter_artifacts"][0]["artifact_type"] == "adapter_trace"
    assert any(event["type"] == "adapter_artifacts" for event in events)
    assert any(event["type"] == "score" for event in events)
    assert metrics["reliability"]["tool_success_rate"] == 1.0
