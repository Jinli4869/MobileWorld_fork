"""Phase 7 runtime artifact conformance regression tests."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from mobile_world.core.runner import _execute_single_task
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
from mobile_world.runtime.protocol.conformance import run_conformance_suite
from mobile_world.runtime.utils.models import Observation
from mobile_world.runtime.utils.trajectory_logger import TrajLogger


class _DummyEnv:
    def get_task_goal(self, task_type: str) -> str:
        return f"goal:{task_type}"

    def initialize_task(self, task_name: str) -> Observation:
        _ = task_name
        return Observation(screenshot=Image.new("RGB", (20, 20), color="white"))

    def execute_action(self, action):
        _ = action
        return Observation(screenshot=Image.new("RGB", (20, 20), color="white"))

    def get_task_score(self, task_type: str) -> tuple[float, str]:
        return 1.0, f"ok:{task_type}"

    def tear_down_task(self, task_type: str):
        return {"status": "success", "task_type": task_type}


class _ScriptedAdapter(FrameworkAdapter):
    def initialize(self, payload: AdapterInitializeInput) -> AdapterInitializeResult:
        _ = payload
        return AdapterInitializeResult(ok=True, message="initialized")

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
        _ = payload
        return AdapterFinalizeResult(ok=True, summary="done")

    def emit_artifacts(self, run_id: str, output_dir: str) -> AdapterArtifactsResult:
        _ = run_id, output_dir
        return AdapterArtifactsResult(artifacts=[])


def _generate_runtime_artifacts(run_root: Path, *, task_name: str = "task_phase7") -> tuple[Path, Path]:
    env = _DummyEnv()
    adapter = _ScriptedAdapter()
    traj_logger = TrajLogger(str(run_root), task_name)
    capability_manifest = {
        "profile_name": "phase7-profile",
        "source": "policy:test",
        "allow_gui": True,
        "allow_mcp": False,
        "allow_user_interaction": False,
        "mcp_timeout_seconds": 120,
        "allowed_mcp_tools": [],
    }
    traj_logger.log_tool_manifest(capability_manifest)
    traj_logger.log_policy_manifest(capability_manifest)
    _execute_single_task(
        env=env,
        agent=None,
        task_name=task_name,
        max_step=5,
        traj_logger=traj_logger,
        framework_adapter=adapter,
    )
    return run_root, run_root / task_name


def _checks_by_name(report: dict) -> dict[str, dict]:
    checks = report["tasks"][0]["checks"]
    return {check["name"]: check for check in checks}


def _failed_checks(report: dict) -> set[str]:
    return {check["name"] for check in report["tasks"][0]["checks"] if not check["passed"]}


def test_runtime_artifacts_pass_conformance(tmp_path: Path):
    run_root, _ = _generate_runtime_artifacts(tmp_path / "runtime_run")
    report = run_conformance_suite(str(run_root))
    checks = _checks_by_name(report)

    assert report["checked_tasks"] == 1
    assert report["ok"] is True
    assert checks["canonical.header_present"]["passed"] is True
    assert checks["meta.policy_manifest_present"]["passed"] is True


def test_runtime_artifacts_fail_conformance_when_header_missing(tmp_path: Path):
    run_root, task_dir = _generate_runtime_artifacts(tmp_path / "runtime_run")
    canonical_path = task_dir / "traj.canonical.jsonl"
    canonical_rows = []
    for line in canonical_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if payload.get("type") == "header":
            continue
        canonical_rows.append(payload)
    canonical_path.write_text(
        "".join(f"{json.dumps(row, ensure_ascii=False)}\n" for row in canonical_rows),
        encoding="utf-8",
    )

    report = run_conformance_suite(str(run_root))
    checks = _checks_by_name(report)
    failed_checks = _failed_checks(report)

    assert report["ok"] is False
    assert checks["canonical.header_present"]["passed"] is False
    assert checks["meta.policy_manifest_present"]["passed"] is True
    assert failed_checks == {"canonical.header_present"}


def test_runtime_artifacts_fail_conformance_when_policy_manifest_missing(tmp_path: Path):
    run_root, task_dir = _generate_runtime_artifacts(tmp_path / "runtime_run")
    meta_path = task_dir / "traj.meta.json"
    meta_payload = json.loads(meta_path.read_text(encoding="utf-8"))
    meta_payload.pop("policy_manifest", None)
    meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report = run_conformance_suite(str(run_root))
    checks = _checks_by_name(report)
    failed_checks = _failed_checks(report)

    assert report["ok"] is False
    assert checks["canonical.header_present"]["passed"] is True
    assert checks["meta.policy_manifest_present"]["passed"] is False
    assert failed_checks == {"meta.policy_manifest_present"}
