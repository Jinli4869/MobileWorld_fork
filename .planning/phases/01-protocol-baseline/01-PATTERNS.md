# Phase 01: Protocol Baseline - Pattern Map

**Mapped:** 2026-04-17  
**Files analyzed:** 16  
**Analogs found:** 16 / 16

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/mobile_world/runtime/protocol/__init__.py` | module | import-export | `src/mobile_world/runtime/protocol/__init__.py` | exact |
| `src/mobile_world/runtime/protocol/adapter.py` | model | request-response | `src/mobile_world/agents/base.py` | role-match |
| `src/mobile_world/runtime/protocol/events.py` | model | event-driven | `src/mobile_world/runtime/utils/models.py` | role-match |
| `src/mobile_world/runtime/protocol/registry.py` | store | CRUD | `src/mobile_world/agents/registry.py` | exact |
| `src/mobile_world/runtime/protocol/validation.py` | utility | request-response | `src/mobile_world/runtime/utils/models.py` | role-match |
| `src/mobile_world/runtime/protocol/normalization.py` | utility | transform | `src/mobile_world/runtime/utils/trajectory_logger.py` | dataflow-match |
| `src/mobile_world/core/runner.py` | service | event-driven | `src/mobile_world/core/runner.py` | exact |
| `src/mobile_world/core/subcommands/eval.py` | service | request-response | `src/mobile_world/core/subcommands/eval.py` | exact |
| `src/mobile_world/core/subcommands/test.py` | service | request-response | `src/mobile_world/core/subcommands/test.py` | exact |
| `src/mobile_world/runtime/utils/trajectory_logger.py` | service | file-I/O | `src/mobile_world/runtime/utils/trajectory_logger.py` | exact |
| `src/mobile_world/agents/registry.py` | store | CRUD | `src/mobile_world/agents/registry.py` | exact |
| `src/mobile_world/runtime/utils/models.py` | model | transform | `src/mobile_world/runtime/utils/models.py` | exact |
| `tests/protocol/test_phase1_protocol_baseline.py` | test | request-response | `tests/protocol/test_phase2_tool_router_policy.py` | role-match |
| `tests/protocol/test_canonical_trajectory_contract.py` | test | file-I/O | `tests/protocol/test_phase2_tool_router_policy.py` | role-match |
| `tests/protocol/conftest.py` | test | batch | `tests/protocol/conftest.py` | exact |
| `pyproject.toml` | config | configuration | `pyproject.toml` | exact |

## Pattern Assignments

### `src/mobile_world/runtime/protocol/adapter.py` (model, request-response)

**Analog:** `src/mobile_world/agents/base.py`

**Interface + imports pattern** (`src/mobile_world/agents/base.py:5-13`):
```python
import time
from abc import ABC, abstractmethod
from typing import Any

from loguru import logger
from openai import OpenAI

from mobile_world.runtime.utils.models import JSONAction
```

**Lifecycle contract pattern** (`src/mobile_world/agents/base.py:27-47`):
```python
def initialize(self, instruction: str) -> bool:
    self.instruction = instruction
    logger.debug(f"initialized the agent with the given instruction: {self.instruction}")
    self.initialize_hook(self.instruction)
    return True

@abstractmethod
def predict(self, observation: dict[str, Any]) -> tuple[str, JSONAction]:
    raise NotImplementedError("predict method is not implemented")

def done(self) -> None:
    logger.debug(f"finalizing the agent for the current task: {self.instruction}")
    self.instruction = None
    self.reset()
```

**Retry/error handling pattern** (`src/mobile_world/agents/base.py:95-136`):
```python
while retry_times > 0:
    try:
        response = self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs,
        )
        self._log_openai_usage(response)
        final_content = response.choices[0].message.content.strip()
        return final_content
    except Exception as e:
        logger.warning(f"Error calling OpenAI API: {e}")
        retry_times -= 1
        time.sleep(1)
return None
```

---

### `src/mobile_world/runtime/protocol/events.py` (model, event-driven)

**Analog:** `src/mobile_world/runtime/utils/models.py`

**Constants/version pattern** (`src/mobile_world/runtime/utils/models.py:30-50`):
```python
CANONICAL_TRAJECTORY_SCHEMA_VERSION = "1.0.0"
_ACTION_TYPES = (
    CLICK,
    DOUBLE_TAP,
    SCROLL,
    SWIPE,
    INPUT_TEXT,
    NAVIGATE_HOME,
    NAVIGATE_BACK,
    KEYBOARD_ENTER,
    OPEN_APP,
    STATUS,
    WAIT,
    LONG_PRESS,
    ANSWER,
    FINISHED,
    UNKNOWN,
    DRAG,
    ASK_USER,
    MCP,
)
```

**Pydantic model/validation pattern** (`src/mobile_world/runtime/utils/models.py:128-158`):
```python
@field_validator("action_type")
@classmethod
def validate_action_type(cls, v: str | None) -> str | None:
    if v is not None and v not in _ACTION_TYPES:
        raise ValueError(f"Invalid action type: {v}")
    return v

@field_validator("x", "y", mode="before")
@classmethod
def validate_coordinates(cls, v: int | float | None) -> int | None:
    if v is not None:
        return round(v)
    return v
```

---

### `src/mobile_world/runtime/protocol/registry.py` (store, CRUD)

**Analog:** `src/mobile_world/agents/registry.py`

**Registration wrapper pattern** (`src/mobile_world/agents/registry.py:61-83`):
```python
def register_adapter_profile(
    profile_name: str,
    *,
    framework: str,
    adapter_class: type[FrameworkAdapter],
    factory=None,
    capabilities: list[str] | None = None,
    metadata: dict | None = None,
    overwrite: bool = False,
) -> None:
    profile = AdapterProfile(
        name=profile_name,
        framework=framework,
        capabilities=capabilities or [],
        metadata=metadata or {},
    )
    register_protocol_adapter(
        profile=profile,
        adapter_class=adapter_class,
        factory=factory,
        overwrite=overwrite,
    )
```

**Bootstrap-on-import pattern** (`src/mobile_world/agents/registry.py:86-97`, `282-283`):
```python
def register_builtin_protocol_adapters() -> None:
    for agent_name in AGENT_CONFIGS:
        if has_adapter(agent_name):
            continue
        register_adapter_profile(
            agent_name,
            framework="mobile_world_builtin",
            adapter_class=LegacyAgentAdapter,
            capabilities=["legacy_agent", "gui_action"],
            metadata={"source": "mobile_world.agents.registry"},
        )

register_builtin_protocol_adapters()
register_reference_framework_adapters()
```

**Factory-first resolution pattern** (`src/mobile_world/agents/registry.py:161-185`):
```python
registration = get_adapter_registration(profile_name)
if registration.factory is not None:
    return registration.factory(
        model_name=model_name,
        llm_base_url=llm_base_url,
        api_key=api_key,
        **kwargs,
    )

legacy_agent = create_agent(
    profile_name,
    model_name=model_name,
    llm_base_url=llm_base_url,
    api_key=api_key,
    **kwargs,
)
return registration.adapter_class(legacy_agent)
```

---

### `src/mobile_world/runtime/protocol/validation.py` (utility, request-response)

**Analog:** `src/mobile_world/runtime/utils/models.py`

**Structured validator pattern** (`src/mobile_world/runtime/utils/models.py:128-174`):
```python
@field_validator("action_type")
@classmethod
def validate_action_type(cls, v: str | None) -> str | None:
    if v is not None and v not in _ACTION_TYPES:
        raise ValueError(f"Invalid action type: {v}")
    return v

@field_validator("direction")
@classmethod
def validate_direction(cls, v: str | None) -> str | None:
    if v is not None and v not in _SCROLL_DIRECTIONS:
        raise ValueError(f"Invalid scroll direction: {v}")
    return v
```

**Post-init semantic guard pattern** (`src/mobile_world/runtime/utils/models.py:176-181`):
```python
def model_post_init(self, __context: Any) -> None:
    if self.index is not None:
        if self.x is not None or self.y is not None:
            raise ValueError("Either an index or a <x, y> should be provided.")
```

---

### `src/mobile_world/runtime/protocol/normalization.py` (utility, transform)

**Analog:** `src/mobile_world/runtime/utils/trajectory_logger.py`

**Normalization-before-write pattern** (`src/mobile_world/runtime/utils/trajectory_logger.py:223-235`):
```python
self._write_canonical_meta(task_name, task_goal, task_id, token_usage=token_usage)
canonical_step = normalize_step_event(
    task_name=task_name,
    task_goal=task_goal,
    run_id=f"{task_name}-{task_id}",
    step=step,
    prediction=prediction,
    action=action,
    observation=obs,
    token_usage=token_usage,
    info=step_info or {},
)
self._append_canonical_event(canonical_step.model_dump())
```

**JSON-serialization safety pattern** (`src/mobile_world/runtime/utils/trajectory_logger.py:130-140`):
```python
@staticmethod
def _read_json_or_default(path: str, default: dict | None = None) -> dict:
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default.copy()
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return default.copy()
```

---

### `src/mobile_world/core/runner.py` (service, event-driven)

**Analog:** `src/mobile_world/core/runner.py`

**Protocol imports + dependency wiring** (`src/mobile_world/core/runner.py:19-39`):
```python
from mobile_world.runtime.protocol.adapter import (
    AdapterFinalizeInput,
    AdapterInitializeInput,
    AdapterStepInput,
    FrameworkAdapter,
    is_terminal_action,
)
from mobile_world.runtime.protocol.validation import ProtocolValidationError, run_protocol_preflight
from mobile_world.runtime.utils.trajectory_logger import METRICS_FILE_NAME, TrajLogger
```

**Adapter lifecycle orchestration pattern** (`src/mobile_world/core/runner.py:83-95`, `113-128`, `263-277`):
```python
adapter_options = dict(framework_options or {})
adapter_options.setdefault("output_dir", traj_logger.log_file_dir)
init_result = framework_adapter.initialize(
    AdapterInitializeInput(
        task_name=task_name,
        task_goal=task_goal,
        run_id=run_id,
        options=adapter_options,
    )
)
if not init_result.ok:
    raise RuntimeError(f"Framework adapter initialize failed: {init_result.message}")

step_result = framework_adapter.step(
    AdapterStepInput(
        run_id=run_id,
        task_name=task_name,
        step_index=step,
        observation=observation_payload,
    )
)

finalize_result = framework_adapter.finalize(
    AdapterFinalizeInput(
        run_id=run_id,
        task_name=task_name,
        score=evaluation_result.score,
        reason=evaluation_result.reason,
        metrics=metrics_summary,
    )
)
```

**Pre-flight gate pattern** (`src/mobile_world/core/runner.py:527-538`):
```python
if skip_protocol_validation:
    logger.warning("Protocol pre-flight validation explicitly skipped by CLI flag")
else:
    try:
        validation_report = run_protocol_preflight(strict=True)
    except ProtocolValidationError:
        logger.exception("Protocol pre-flight validation failed")
        raise
    logger.info(
        "Protocol pre-flight passed. Checked adapters: {}",
        validation_report.checked_adapters,
    )
```

---

### `src/mobile_world/runtime/utils/trajectory_logger.py` (service, file-I/O)

**Analog:** `src/mobile_world/runtime/utils/trajectory_logger.py`

**Dual-write artifact initialization pattern** (`src/mobile_world/runtime/utils/trajectory_logger.py:113-122`):
```python
with open(os.path.join(self.log_file_dir, self.log_file_name), "w") as f:
    json.dump({}, f)
with open(os.path.join(self.log_file_dir, self.canonical_log_file_name), "w") as f:
    f.write("")
with open(os.path.join(self.log_file_dir, self.canonical_meta_file_name), "w") as f:
    json.dump({}, f)
```

**Legacy + canonical synchronized write pattern** (`src/mobile_world/runtime/utils/trajectory_logger.py:221-235`):
```python
with open(os.path.join(self.log_file_dir, self.log_file_name), "w") as f:
    json.dump(log_data, f, ensure_ascii=False, indent=4)
self._write_canonical_meta(task_name, task_goal, task_id, token_usage=token_usage)
canonical_step = normalize_step_event(
    task_name=task_name,
    task_goal=task_goal,
    run_id=f"{task_name}-{task_id}",
    step=step,
    prediction=prediction,
    action=action,
    observation=obs,
    token_usage=token_usage,
    info=step_info or {},
)
self._append_canonical_event(canonical_step.model_dump())
```

---

### `src/mobile_world/agents/registry.py` (store, CRUD)

**Analog:** `src/mobile_world/agents/registry.py`

**Registry config map pattern** (`src/mobile_world/agents/registry.py:33-58`):
```python
AGENT_CONFIGS = {
    "qwen3vl": {"class": Qwen3VLAgentMCP},
    "planner_executor": {"class": PlannerExecutorAgentMCP},
    "mai_ui_agent": {"class": MAIUINaivigationAgent},
    "general_e2e": {"class": GeneralE2EAgentMCP},
    "seed_agent": {"class": SeedAgent},
    "gelab_agent": {"class": GelabAgent},
    "ui_venus_agent": {"class": VenusNaviAgent},
    "gui_owl_1_5": {"class": GUIOWL15AgentMCP},
}
```

**Validation + error pattern** (`src/mobile_world/agents/registry.py:269-279`):
```python
if agent_type not in AGENT_CONFIGS:
    raise ValueError(f"Unsupported agent type: {agent_type}")

return AGENT_CONFIGS[agent_type]["class"](
    model_name=model_name,
    llm_base_url=llm_base_url,
    tools=kwargs["env"].tools,
    api_key=api_key,
    **kwargs,
)
```

---

### `src/mobile_world/runtime/utils/models.py` (model, transform)

**Analog:** `src/mobile_world/runtime/utils/models.py`

**Action schema pattern** (`src/mobile_world/runtime/utils/models.py:83-127`):
```python
class JSONAction(BaseModel):
    action_type: str | None = None
    index: str | int | None = None
    x: int | None = None
    y: int | None = None
    text: str | None = None
    direction: str | None = None
    goal_status: str | None = None
    app_name: str | None = None
    keycode: str | None = None
    clear_text: bool | None = None
    start_x: int | None = None
    start_y: int | None = None
    end_x: int | None = None
    end_y: int | None = None
    action_name: str | None = None
    action_json: dict | None = None
```

**Model-level semantic checks** (`src/mobile_world/runtime/utils/models.py:176-186`):
```python
def model_post_init(self, __context: Any) -> None:
    if self.index is not None:
        if self.x is not None or self.y is not None:
            raise ValueError("Either an index or a <x, y> should be provided.")

def __eq__(self, other: object) -> bool:
    if not isinstance(other, JSONAction):
        return False
    return _compare_actions(self, other)
```

---

### `tests/protocol/test_phase1_protocol_baseline.py` (test, request-response)

**Analog:** `tests/protocol/test_phase2_tool_router_policy.py`

**Import + test helper pattern** (`tests/protocol/test_phase2_tool_router_policy.py:3-17`, `32-43`):
```python
import json
from pathlib import Path

from mobile_world.runtime.protocol.capability_policy import (
    CapabilityDecision,
    resolve_capability_policy,
)
from mobile_world.runtime.protocol.tool_router import UnifiedToolRouter

def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows
```

**Contract assertion style** (`tests/protocol/test_phase2_tool_router_policy.py:66-80`):
```python
def test_router_denies_disabled_tool_class():
    decision = CapabilityDecision(
        enabled_tool_classes=["gui"],
        enabled_mcp_tools=[],
        mcp_timeout_seconds=120,
        source="test",
        task_tags=[],
        profile_name="unit",
    )
    router = UnifiedToolRouter(decision)
    action = JSONAction(action_type="mcp", action_name="mcp_demo", action_json={})
    result = router.dispatch(DummyEnv(), action)
    assert result.ok is False
    assert result.error.code == "CAPABILITY_DENIED"
```

---

### `tests/protocol/conftest.py` (test, batch)

**Analog:** `tests/protocol/conftest.py`

**Autouse isolation fixture pattern** (`tests/protocol/conftest.py:12-19`):
```python
@pytest.fixture(autouse=True)
def reset_protocol_adapter_registry():
    clear_adapters()
    register_builtin_protocol_adapters()
    register_reference_framework_adapters()
    yield
    clear_adapters()
```

## Shared Patterns

### Contract Models with Pydantic Validators
**Source:** `src/mobile_world/runtime/utils/models.py:83-181`  
**Apply to:** `runtime/protocol/adapter.py`, `runtime/protocol/events.py`, `runtime/protocol/validation.py`
```python
class JSONAction(BaseModel):
    ...

@field_validator("action_type")
@classmethod
def validate_action_type(cls, v: str | None) -> str | None:
    if v is not None and v not in _ACTION_TYPES:
        raise ValueError(f"Invalid action type: {v}")
    return v
```

### Runner Fail-Fast Preflight
**Source:** `src/mobile_world/core/runner.py:527-538`  
**Apply to:** protocol startup validation integration in runner entrypoints
```python
validation_report = run_protocol_preflight(strict=True)
```

### Dual-Write Legacy + Canonical Artifacts
**Source:** `src/mobile_world/runtime/utils/trajectory_logger.py:221-235`  
**Apply to:** all trajectory persistence updates in Phase 1
```python
json.dump(log_data, f, ensure_ascii=False, indent=4)
self._append_canonical_event(canonical_step.model_dump())
```

### Registry + Factory Resolution
**Source:** `src/mobile_world/agents/registry.py:61-83`, `161-185`  
**Apply to:** adapter registry/discovery flow (`ADPT-01`)
```python
register_protocol_adapter(...)
registration = get_adapter_registration(profile_name)
```

### Test Isolation for Global Registries
**Source:** `tests/protocol/conftest.py:12-19`  
**Apply to:** all adapter contract tests (`ADPT-04`)
```python
clear_adapters()
register_builtin_protocol_adapters()
...
clear_adapters()
```

## No Analog Found

None. Every Phase 1 inferred file has a concrete analog in the current codebase.

## Metadata

**Analog search scope:** `src/mobile_world/runtime`, `src/mobile_world/core`, `src/mobile_world/agents`, `tests/protocol`  
**Files scanned:** 109  
**Pattern extraction date:** 2026-04-17
