# Phase 8: Framework Profile Policy Flow Repair - Research

**Researched:** 2026-04-17  
**Domain:** Framework-profile capability policy correctness in adapter-mode eval runs  
**Confidence:** HIGH

## User Constraints

### Locked Decisions
- Phase 8 goal is to ensure framework-profile runs use deterministic profile-bound capability policy behavior.
- Phase 8 must satisfy `TOOL-02` and `INTG-03`.
- Adapter-mode policy resolution currently uses `agent_type` instead of `framework_profile`; this is the known high-severity flow gap to close.
- Runtime/task ownership remains in MobileWorld; fix must stay inside current runner/protocol contracts.

### Agent's Discretion
- Exact test boundaries and fixture strategy for verifying framework-profile policy flow.
- Whether new regression coverage lands in an existing protocol test module or a new phase-specific protocol test file.

### Deferred Ideas (Out of Scope)
- Reproducibility judge-agreement gate hardening (Phase 9 scope).
- New adapter ecosystems or registry redesign beyond profile-binding correctness.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TOOL-02 | Task/tag/profile capability policy can enable/disable tool classes deterministically per run. | Bind policy resolution input to `framework_profile` in adapter-mode; preserve `agent_type` fallback for built-in mode. |
| INTG-03 | CLI can run eval by framework profile and emit comparable result artifacts. | Verify `eval --framework-profile` path propagates profile identity into policy manifest and capability decisions used during task execution. |

</phase_requirements>

## Summary

The functional gap is localized in the runner path: `_process_task_on_env(...)` resolves capability policy before task execution using `profile_name=agent_type` even when `framework_profile` is selected for adapter mode. That causes profile-scoped rules to resolve against the wrong identity and can produce policy manifests that do not match the selected framework profile.

The safest closure strategy is:
1. Resolve capability policy with `framework_profile` when present, else `agent_type`.
2. Keep manifest persistence as-is (already implemented in Phase 7) so the corrected profile identity is reflected in artifacts.
3. Add deterministic regression tests that exercise both built-in and framework-profile branches and assert profile identity/manifest alignment.
4. Add flow regression coverage for eval framework-profile invocation semantics to close `INTG-03` confidence gap.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Profile identity selection for capability policy | API / Backend | Runtime Protocol | Runner owns capability resolution inputs before task execution. |
| Policy manifest profile alignment in artifacts | Runtime Protocol | Storage Artifacts | `CapabilityDecision.as_manifest()` feeds `TrajLogger` artifact writes. |
| Framework-profile eval flow correctness | CLI / Subcommand | Runner | CLI parses profile input; runner must consume it semantically. |
| Regression enforcement | Protocol Tests | Runner/CLI | Tests should pin both resolver input and artifact output behavior. |

## Existing Code Findings

### Primary Gap
- `src/mobile_world/core/runner.py` currently calls:
  - `resolve_capability_policy(..., profile_name=agent_type, ...)`
- This occurs before framework adapter creation branch and ignores the selected `framework_profile` identity for adapter-mode policy matching.

### Existing Strengths to Reuse
- `CapabilityDecision.as_manifest()` already carries `profile_name` and is persisted to tool/policy manifests (Phase 7).
- Eval subcommand already parses and forwards `framework_profile` into `run_agent_with_evaluation(...)`.
- Runner already forwards `framework_profile` into `_process_task_on_env(...)`; mismatch is inside policy resolution input choice.

## Recommended Plan Decomposition

| Plan | Scope | Why |
|------|-------|-----|
| 08-01 | Bind resolver profile identity to framework profile in runner path | Fix root cause with minimal code-surface risk |
| 08-02 | Add artifact/profile alignment regression coverage on runner task path | Prevent silent regressions in manifest semantics |
| 08-03 | Add framework-profile eval flow regression test | Close CLI-to-runner-to-policy confidence for `INTG-03` |

## Files Likely To Be Modified

| File | Purpose |
|------|---------|
| `src/mobile_world/core/runner.py` | Select effective policy profile identity (`framework_profile` or `agent_type`) and pass to resolver deterministically |
| `tests/protocol/test_phase8_framework_profile_policy_flow.py` (new) | Add focused runner/flow regressions for profile-bound capability policy behavior |
| `tests/protocol/test_phase5_framework_profiles.py` (optional extension) | Add targeted eval flow regression if CLI parse/forward coverage needs explicit semantic assertion |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Built-in agent policy behavior regression | Could break existing CLI paths | Add fallback-branch test asserting `agent_type` remains profile identity when `framework_profile` is absent |
| False-green tests that only validate parser flags | Might miss runtime policy mismatch | Include runner-path assertions that inspect resolver input and persisted manifests |
| Overly broad refactor in runner | Unnecessary regression surface | Keep fix narrowly scoped to profile identity selection and non-functional logging only |

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` via `uv run --extra dev` |
| Config file | `pyproject.toml` |
| Quick run command | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase8_framework_profile_policy_flow.py` |
| Full protocol run | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol` |

### Requirements -> Verification Map

| Req ID | Behavior | Test Type | Command |
|--------|----------|-----------|---------|
| TOOL-02 | Adapter-mode resolver uses framework profile identity; built-in mode uses agent type fallback | unit/integration | `... pytest -q tests/protocol/test_phase8_framework_profile_policy_flow.py::test_runner_uses_framework_profile_for_policy_resolution` |
| TOOL-02 | Policy manifest profile_name matches effective profile identity in artifacts | unit/integration | `... pytest -q tests/protocol/test_phase8_framework_profile_policy_flow.py::test_policy_manifest_profile_name_matches_effective_profile` |
| INTG-03 | Eval framework-profile flow preserves profile semantics into runner invocation and capability policy decision path | integration | `... pytest -q tests/protocol/test_phase8_framework_profile_policy_flow.py::test_eval_framework_profile_flow_preserves_profile_semantics` |

### Wave 0 Gaps
- [ ] `tests/protocol/test_phase8_framework_profile_policy_flow.py` must be created.
- [ ] Runner-path fixture helpers for lightweight env/agent/adapter stubs must be added.

## Security Domain

| Category | Applies | Notes |
|----------|---------|-------|
| Input Validation | yes | Profile identifiers and policy matching are deterministic string inputs; tests should assert exact behavior. |
| Access Control | no | No auth or permission model changes in this phase. |
| Cryptography | no | No cryptographic changes required. |

## Open Questions (Resolved for Planning)

1. Should resolver prefer framework profile whenever present, even if adapter initialization fails later?
- Planned resolution: **Yes**. Policy decision should be bound to selected framework-profile intent at run setup time; adapter runtime failure does not change intended policy identity.

2. Should we mutate capability policy schema for this phase?
- Planned resolution: **No**. Existing schema already supports profile-scoped rules via `match_profiles_any`; Phase 8 is behavior wiring closure.
