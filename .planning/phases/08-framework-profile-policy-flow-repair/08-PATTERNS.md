# Phase 08: Framework Profile Policy Flow Repair - Pattern Map

**Mapped:** 2026-04-17  
**Files analyzed:** 5  
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/mobile_world/core/runner.py` | service | batch/runtime | `src/mobile_world/core/runner.py` | exact |
| `src/mobile_world/runtime/protocol/capability_policy.py` *(read-first contract owner)* | protocol | decision | `src/mobile_world/runtime/protocol/capability_policy.py` | exact |
| `src/mobile_world/core/subcommands/eval.py` *(flow contract owner)* | cli | request->runner | `src/mobile_world/core/subcommands/eval.py` | exact |
| `tests/protocol/test_phase8_framework_profile_policy_flow.py` | test | behavior/assertion | `tests/protocol/test_phase4_nanobot_reference_integration.py` | role-match |
| `tests/protocol/test_phase5_framework_profiles.py` *(optional extension target)* | test | cli parse/flow | `tests/protocol/test_phase5_framework_profiles.py` | exact |

## Pattern Assignments

### `src/mobile_world/core/runner.py` (service)

**Analog:** `src/mobile_world/core/runner.py`  
**Pattern to preserve:** Resolve capability policy before task execution, serialize one manifest payload to logger, then initialize tool router and evaluator.

**Current critical call shape:**
```python
capability_decision = resolve_capability_policy(
    task_tags=task_tags,
    profile_name=agent_type,
    enable_mcp=enable_mcp,
    enable_user_interaction=enable_user_interaction,
    policy_path=policy_path,
    mcp_allowlist_override=allowlist_override,
)
capability_manifest = capability_decision.as_manifest()
traj_logger.log_tool_manifest(capability_manifest)
traj_logger.log_policy_manifest(capability_manifest)
```

**Required phase-8 change pattern:** introduce a deterministic `effective_policy_profile` variable and pass it to `profile_name`.

### `src/mobile_world/runtime/protocol/capability_policy.py` (protocol)

**Analog:** same file  
**Pattern to preserve:** `resolve_capability_policy(..., profile_name=...)` is the single policy matching entrypoint; `CapabilityDecision.as_manifest()` is the canonical serialized shape.

### `tests/protocol/test_phase8_framework_profile_policy_flow.py` (new test module)

**Primary analog:** `tests/protocol/test_phase4_nanobot_reference_integration.py` (lightweight runtime-path helpers)  
**Secondary analog:** `tests/protocol/test_phase5_framework_profiles.py` (framework-profile flow assertions)

**Test style pattern:**
- Use small fakes/monkeypatching around runner seams.
- Assert exact behavioral values (`profile_name`, manifest fields, forwarded kwargs), not subjective outcomes.
- Keep tests deterministic and free of live emulator requirements.

### `src/mobile_world/core/subcommands/eval.py` (flow contract)

**Analog:** same file  
**Pattern to preserve:** parse/config merge for `framework_profile` and forward to `run_agent_with_evaluation(...)` unchanged.

## Anti-Patterns to Avoid

- Re-keying policy on adapter class or model name instead of `framework_profile` intent.
- Changing capability policy schema for this phase (widen scope unnecessarily).
- Adding heavy end-to-end dependencies in protocol tests when deterministic seam tests are sufficient.
