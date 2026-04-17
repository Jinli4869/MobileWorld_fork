# Phase 07: Conformance Artifact Contract Closure - Pattern Map

**Mapped:** 2026-04-17  
**Files analyzed:** 6  
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/mobile_world/runtime/utils/trajectory_logger.py` | utility | file-I/O | `src/mobile_world/runtime/utils/trajectory_logger.py` | exact |
| `src/mobile_world/core/runner.py` | service | batch | `src/mobile_world/core/runner.py` | exact |
| `tests/protocol/test_canonical_trajectory_contract.py` | test | file-I/O | `tests/protocol/test_phase3_1_metrics_kpi.py` | role-match |
| `tests/protocol/test_phase2_tool_router_policy.py` | test | file-I/O | `tests/protocol/test_phase2_tool_router_policy.py` | exact |
| `tests/protocol/test_phase7_conformance_artifact_contract.py` | test | request-response | `tests/protocol/test_phase6_reporting_conformance_reproducibility.py` | exact |
| `tests/protocol/test_phase6_reporting_conformance_reproducibility.py` *(implied helper-fixture extension target from Wave 0 gap #3)* | test | file-I/O | `tests/protocol/test_phase6_reporting_conformance_reproducibility.py` | exact |

## Pattern Assignments

### `src/mobile_world/runtime/utils/trajectory_logger.py` (utility, file-I/O)

**Analog:** `src/mobile_world/runtime/utils/trajectory_logger.py`  
**Supporting analog:** `src/mobile_world/runtime/protocol/trace_converter.py` (header-first canonical rows)

**Imports pattern** (`src/mobile_world/runtime/utils/trajectory_logger.py:1-14`):
```python
import json
import os
from datetime import datetime

from loguru import logger
from PIL import Image, ImageDraw

from mobile_world.runtime.protocol.events import CanonicalTrajectoryHeader
from mobile_world.runtime.protocol.normalization import (
    normalize_metrics_event,
    normalize_score_event,
    normalize_step_event,
)
from mobile_world.runtime.utils.models import Observation
```

**Core artifact write pattern** (`src/mobile_world/runtime/utils/trajectory_logger.py:142-176`, `:223-235`, `:270-285`):
```python
def _write_canonical_meta(...):
    _, meta_path = self._canonical_paths()
    existing_meta = self._read_json_or_default(meta_path, default={})
    header = CanonicalTrajectoryHeader(...).model_dump()
    for key in ("tool_manifest", "policy_manifest", "token_usage", "evaluator_audit", "metrics_summary", "adapter_artifacts"):
        if key in existing_meta:
            header[key] = existing_meta[key]
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(header, f, ensure_ascii=False, indent=4)

def _append_canonical_event(self, event: dict) -> None:
    with open(canonical_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

canonical_step = normalize_step_event(...)
self._append_canonical_event(canonical_step.model_dump())

def log_tool_manifest(self, manifest: dict) -> None:
    legacy["0"]["tool_manifest"] = manifest
    meta["tool_manifest"] = manifest
```

**Error handling pattern** (`src/mobile_world/runtime/utils/trajectory_logger.py:130-140`):
```python
@staticmethod
def _read_json_or_default(path: str, default: dict | None = None) -> dict:
    ...
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return default.copy()
```

**Validation/schema pattern** (`src/mobile_world/runtime/protocol/trace_converter.py:78-90`):
```python
header = CanonicalTrajectoryHeader(
    task_name=resolved_task_name,
    task_goal=resolved_goal,
    run_id=resolved_run_id,
    tools=task_payload.get("tools", []) or [],
    metadata={...},
).model_dump()
rows: list[dict[str, Any]] = [header]
```

**Testing pattern** (`tests/protocol/test_phase3_1_metrics_kpi.py:124-135`):
```python
task_dir = tmp_path / "task_metrics"
legacy = _read_json(task_dir / LOG_FILE_NAME)
meta = _read_json(task_dir / CANONICAL_META_FILE_NAME)
events = _read_jsonl(task_dir / CANONICAL_LOG_FILE_NAME)

assert legacy["0"]["metrics_summary"]["quality_flags"]["latency"] == "estimated"
assert meta["metrics_summary"]["token_usage"]["avg_total_tokens_per_step"] == 3.0
assert any(event["type"] == "metrics_step" for event in events)
assert any(event["type"] == "metrics" for event in events)
```

---

### `src/mobile_world/core/runner.py` (service, batch)

**Analog:** `src/mobile_world/core/runner.py`

**Imports pattern** (`src/mobile_world/core/runner.py:12-39`):
```python
from mobile_world.agents.base import BaseAgent, MCPAgent
from mobile_world.agents.registry import create_agent, create_framework_adapter
...
from mobile_world.runtime.protocol.capability_policy import resolve_capability_policy
...
from mobile_world.runtime.protocol.validation import ProtocolValidationError, run_protocol_preflight
...
from mobile_world.runtime.utils.trajectory_logger import METRICS_FILE_NAME, TrajLogger
```

**Core policy/manifest pattern** (`src/mobile_world/core/runner.py:361-387`):
```python
capability_decision = resolve_capability_policy(...)

if enable_mcp:
    ...
    traj_logger.log_tools(env.tools)

traj_logger.log_tool_manifest(capability_decision.as_manifest())
tool_router = UnifiedToolRouter(capability_decision)
evaluator = create_evaluator(...)
```

**Error handling/retry pattern** (`src/mobile_world/core/runner.py:374-382`, `:430-439`):
```python
try:
    env.set_mcp_timeout(...)
    env.reset_tools(...)
except Exception as e:
    logger.exception(f"Error resetting tools for task {task_name}: {e}")
    return None

...
except Exception as e:
    if "Device is not healthy" in str(e) and retry_on_device_unhealthy > 0:
        ...
        traj_logger.reset_traj()
        continue
    else:
        logger.exception(f"Error executing task {task_name}")
        return None
```

**Validation gate pattern** (`src/mobile_world/core/runner.py:527-535`):
```python
try:
    validation_report = run_protocol_preflight(strict=True)
except ProtocolValidationError:
    logger.exception("Protocol pre-flight validation failed")
    raise
```

**Testing pattern** (`tests/protocol/test_phase4_nanobot_reference_integration.py:139-168`):
```python
steps, score = _execute_single_task(..., traj_logger=traj_logger, framework_adapter=adapter)
...
events = _read_jsonl(task_dir / CANONICAL_LOG_FILE_NAME)
assert any(event["type"] == "adapter_artifacts" for event in events)
assert any(event["type"] == "score" for event in events)
```

---

### `tests/protocol/test_canonical_trajectory_contract.py` (test, file-I/O)

**Analog:** `tests/protocol/test_phase3_1_metrics_kpi.py`

**Imports/helper pattern** (`tests/protocol/test_canonical_trajectory_contract.py:3-26`):
```python
import json
from pathlib import Path

from PIL import Image

from mobile_world.runtime.utils.models import Observation
from mobile_world.runtime.utils.trajectory_logger import (...)

def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        ...
        rows.append(json.loads(line))
    return rows
```

**Artifact assertion pattern** (`tests/protocol/test_canonical_trajectory_contract.py:47-96`):
```python
logger.log_traj(...)
logger.log_score(score=1.0, reason="task completed")

events = _load_jsonl(canonical_jsonl_path)
assert len(events) == 2
step_event = events[0]
score_event = events[1]

assert step_event["type"] == "step"
assert score_event["type"] == "score"
```

**Companion assertion style to reuse** (`tests/protocol/test_phase3_1_metrics_kpi.py:130-135`):
```python
assert any(event["type"] == "metrics_step" for event in events)
assert any(event["type"] == "metrics" for event in events)
```

**Auth/guard pattern:** None in protocol tests.

---

### `tests/protocol/test_phase2_tool_router_policy.py` (test, file-I/O)

**Analog:** `tests/protocol/test_phase2_tool_router_policy.py`

**Imports/router policy pattern** (`tests/protocol/test_phase2_tool_router_policy.py:6-18`):
```python
from mobile_world.runtime.protocol.capability_policy import (
    CapabilityDecision,
    resolve_capability_policy,
)
from mobile_world.runtime.protocol.tool_router import UnifiedToolRouter
from mobile_world.runtime.utils.models import JSONAction
from mobile_world.runtime.utils.trajectory_logger import (...)
```

**Artifact assertion pattern** (`tests/protocol/test_phase2_tool_router_policy.py:109-132`):
```python
traj_logger.log_tool_manifest(manifest)
traj_logger.log_tool_error(step=3, error={"code": "CAPABILITY_DENIED", "message": "denied"})

legacy = _read_json(task_dir / LOG_FILE_NAME)
canonical_meta = _read_json(task_dir / CANONICAL_META_FILE_NAME)
canonical_events = _read_jsonl(task_dir / CANONICAL_LOG_FILE_NAME)

assert legacy["0"]["tool_manifest"]["source"] == "policy:test"
assert canonical_meta["tool_manifest"]["mcp_timeout_seconds"] == 120
assert canonical_events[-1]["type"] == "tool_error"
```

**Extension target for Plan 07-02**:
- Keep this test module as the regression owner for logger/runner policy manifest persistence.
- Extend existing artifact assertions with `policy_manifest` checks in legacy + canonical metadata.
- Rename only in Task 3 after Task 1/2 selectors run against the current test name.

**Auth/guard pattern:** None in protocol tests.

---

### `tests/protocol/test_phase7_conformance_artifact_contract.py` (test, request-response)

**Analog:** `tests/protocol/test_phase6_reporting_conformance_reproducibility.py`  
**Supporting analog:** `tests/protocol/test_phase4_nanobot_reference_integration.py` (runtime artifact generation via `_execute_single_task`)

**Imports + conformance invocation pattern** (`tests/protocol/test_phase6_reporting_conformance_reproducibility.py:8-23`, `:254-271`):
```python
from mobile_world.runtime.protocol.conformance import run_conformance_suite
from mobile_world.runtime.utils.trajectory_logger import (...)

def test_conformance_suite_passes_for_valid_artifacts(tmp_path: Path):
    run_root = tmp_path / "run_conformance"
    _task_artifact_bundle(...)

    report = run_conformance_suite(str(run_root))
    assert report["checked_tasks"] == 1
    assert report["ok"] is True
    assert report["tasks"][0]["ok"] is True
```

**Runtime-generated artifact pattern** (`tests/protocol/test_phase4_nanobot_reference_integration.py:144-168`):
```python
steps, score = _execute_single_task(
    env=env,
    agent=None,
    task_name="task_phase4",
    max_step=5,
    traj_logger=traj_logger,
    framework_adapter=adapter,
)
...
events = _read_jsonl(task_dir / CANONICAL_LOG_FILE_NAME)
assert any(event["type"] == "score" for event in events)
```

**Validation oracle pattern** (`src/mobile_world/runtime/protocol/conformance.py:134-155`):
```python
events = _read_jsonl(required_files["canonical_log"])
event_types = {event.get("type") for event in events}
add_check("canonical.header_present", "header" in event_types)
...
meta = _read_json(required_files["canonical_meta"])
add_check("meta.tool_manifest_present", "tool_manifest" in meta)
add_check("meta.policy_manifest_present", "policy_manifest" in meta)
```

**Error handling pattern:** Keep tests deterministic; assert report payloads instead of try/except.

---

### `tests/protocol/test_phase6_reporting_conformance_reproducibility.py` (test, file-I/O)

**Analog:** `tests/protocol/test_phase6_reporting_conformance_reproducibility.py`

**Imports/helper writer pattern** (`tests/protocol/test_phase6_reporting_conformance_reproducibility.py:26-37`):
```python
def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")
```

**Synthetic bundle pattern (extension point)** (`tests/protocol/test_phase6_reporting_conformance_reproducibility.py:39-138`):
```python
def _task_artifact_bundle(...):
    ...
    _write_json(task_dir / CANONICAL_META_FILE_NAME, {..., "policy_manifest": {...}, ...})
    _write_jsonl(task_dir / CANONICAL_LOG_FILE_NAME, [{"type": "header", ...}, {"type": "step", ...}, ...])
```

**Conformance assertion pattern** (`tests/protocol/test_phase6_reporting_conformance_reproducibility.py:268-271`):
```python
report = run_conformance_suite(str(run_root))
assert report["checked_tasks"] == 1
assert report["ok"] is True
assert report["tasks"][0]["ok"] is True
```

**Auth/guard pattern:** None in protocol tests.

---

## Shared Patterns

### Capability Manifest Source-of-Truth
**Source:** `src/mobile_world/runtime/protocol/capability_policy.py:70-79`  
**Apply to:** `src/mobile_world/core/runner.py`, `src/mobile_world/runtime/utils/trajectory_logger.py`, phase-7 conformance test fixtures
```python
def as_manifest(self) -> dict:
    return {
        "enabled_tool_classes": sorted(self.enabled_tool_classes),
        "enabled_mcp_tools": sorted(self.enabled_mcp_tools),
        "mcp_timeout_seconds": self.mcp_timeout_seconds,
        "source": self.source,
        "task_tags": sorted(self.task_tags),
        "profile_name": self.profile_name,
    }
```

### Canonical Header Model
**Source:** `src/mobile_world/runtime/protocol/events.py:27-39`  
**Apply to:** Canonical JSONL/header emission and test assertions
```python
class CanonicalTrajectoryHeader(BaseModel):
    type: Literal["header"] = "header"
    schema_version: str = CANONICAL_TRAJECTORY_SCHEMA_VERSION
    ...
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### Conformance Contract Checks (acceptance oracle)
**Source:** `src/mobile_world/runtime/protocol/conformance.py:136-155`  
**Apply to:** New Phase 7 regression test assertions and artifact generation setup
```python
add_check("canonical.header_present", "header" in event_types)
...
add_check("meta.policy_manifest_present", "policy_manifest" in meta)
```

### JSONL Serialization Convention
**Source:** `src/mobile_world/runtime/utils/trajectory_logger.py:173-176`, `src/mobile_world/runtime/protocol/trace_converter.py:45-50`  
**Apply to:** runtime logger writes and test fixture writers
```python
f.write(json.dumps(event_or_row, ensure_ascii=False))
f.write("\n")
```

### Protocol Preflight Before Eval
**Source:** `src/mobile_world/core/runner.py:527-535`  
**Apply to:** Any runner-level integration behavior touched by Phase 7
```python
validation_report = run_protocol_preflight(strict=True)
```

## No Analog Found

None.

## Metadata

**Analog search scope:** `src/mobile_world/runtime/**`, `src/mobile_world/core/**`, `tests/protocol/**`  
**Files scanned:** 83 candidates (`rg --files` over scope), 21 files read in detail  
**Pattern extraction date:** 2026-04-17
