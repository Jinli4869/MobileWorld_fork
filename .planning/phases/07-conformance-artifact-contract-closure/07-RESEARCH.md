# Phase 7: Conformance Artifact Contract Closure - Research

**Researched:** 2026-04-17  
**Domain:** Canonical trajectory artifact contract alignment between eval runtime output and benchmark conformance validation  
**Confidence:** HIGH

## User Constraints

### Locked Decisions
- Phase 7 goal is to close blocker-level artifact gaps so eval outputs satisfy conformance checks end-to-end. [VERIFIED: `.planning/ROADMAP.md` Phase 7 section]
- Phase 7 must address `COMP-02` and `TRCE-01`. [VERIFIED: `.planning/ROADMAP.md` + `.planning/REQUIREMENTS.md`]
- Success criteria include: canonical header event in trajectory JSONL, policy manifest fields in canonical metadata, eval->conformance CLI pass, and regression test coverage. [VERIFIED: user-provided phase brief + `.planning/ROADMAP.md`]

### Claude's Discretion
- Exact implementation shape for header emission timing and policy manifest serialization is not locked by a `*-CONTEXT.md` file for this phase. [VERIFIED: no `*-CONTEXT.md` in `.planning/phases/07-conformance-artifact-contract-closure/`]

### Deferred Ideas (OUT OF SCOPE)
- Phase 8 policy-resolution correctness (`agent_type` vs `framework_profile`) is out of scope for Phase 7 except where it affects artifact presence. [VERIFIED: `.planning/ROADMAP.md` Phase 8 scope]
- Phase 9 reproducibility gate hardening is out of scope for Phase 7. [VERIFIED: `.planning/ROADMAP.md` Phase 9 scope]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COMP-02 | Conformance suite validates adapter contract, tool routing, and evaluator output shape. [VERIFIED: `.planning/REQUIREMENTS.md`] | Research identifies exact failing conformance checks (`canonical.header_present`, `meta.policy_manifest_present`) and the runtime write path that must be fixed (`TrajLogger` + runner manifest logging). [VERIFIED: `src/mobile_world/runtime/protocol/conformance.py`, `src/mobile_world/runtime/utils/trajectory_logger.py`, `src/mobile_world/core/runner.py`] |
| TRCE-01 | All runs persist a canonical versioned trajectory schema regardless of framework source. [VERIFIED: `.planning/REQUIREMENTS.md`] | Research confirms versioned schema exists but runtime JSONL stream omits header event; converter path includes header, proving contract target is already modeled. [VERIFIED: `src/mobile_world/runtime/protocol/events.py`, `src/mobile_world/runtime/utils/trajectory_logger.py`, `src/mobile_world/runtime/protocol/trace_converter.py`] |

</phase_requirements>

## Summary

Phase 7 is a contract-closure phase, not a redesign phase: the conformance validator already defines required checks, and the runtime already has most required artifacts, but two required fields are missing in the eval-produced path (`header` event in canonical JSONL and `policy_manifest` in canonical metadata). [VERIFIED: `src/mobile_world/runtime/protocol/conformance.py`, `.planning/v1.0-v1.0-MILESTONE-AUDIT.md`]

The gap is localized and testable. `run_conformance_suite` requires `canonical.header_present` and `meta.policy_manifest_present`; current runner flow logs `tool_manifest` but never logs `policy_manifest`, and `TrajLogger.log_traj` appends only `step` events to JSONL while storing header-shaped data only in `traj.meta.json`. [VERIFIED: `src/mobile_world/runtime/protocol/conformance.py`, `src/mobile_world/core/runner.py`, `src/mobile_world/runtime/utils/trajectory_logger.py`]

The fastest safe closure is: emit one canonical header event in the runtime JSONL stream, persist policy manifest metadata from resolved capability policy into `traj.meta.json`, and add regression coverage that validates real runtime artifact output against the conformance suite path (not only synthetic fixture bundles). [VERIFIED: existing synthetic-only conformance test setup in `tests/protocol/test_phase6_reporting_conformance_reproducibility.py`]

**Primary recommendation:** Implement header emission + policy manifest persistence directly in the existing logger/runner path and gate with a dedicated Phase 7 eval-artifact-to-conformance regression test. [VERIFIED: runtime flow and conformance checks in current codebase]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Emit canonical `header` event into runtime JSONL trajectory | API / Backend | Database / Storage | Event generation occurs in runtime logger code; persistence target is artifact files under run root. [VERIFIED: `src/mobile_world/runtime/utils/trajectory_logger.py`] |
| Persist `policy_manifest` into canonical metadata | API / Backend | Database / Storage | Policy decision is resolved in runner and must be serialized by artifact logger. [VERIFIED: `src/mobile_world/core/runner.py`, `src/mobile_world/runtime/protocol/capability_policy.py`] |
| Validate artifact contract via `mobile-world benchmark conformance` | Browser / Client | API / Backend | CLI invocation is client entry; conformance logic executes in protocol backend module. [VERIFIED: `src/mobile_world/core/subcommands/benchmark.py`, `src/mobile_world/runtime/protocol/conformance.py`] |
| Ensure eval->conformance compatibility in tests | API / Backend | Database / Storage | Tests should exercise artifact writer output and then run conformance checks over written files. [VERIFIED: existing tests in `tests/protocol/`] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mobile-world` runtime logger + protocol modules | `0.1.0` (project version) [VERIFIED: `pyproject.toml`] | Contract owner for canonical artifacts and conformance checks | Phase 7 changes are pure contract closure inside existing ownership boundary; no new framework required. [VERIFIED: `src/mobile_world/runtime/utils/trajectory_logger.py`, `src/mobile_world/runtime/protocol/conformance.py`] |
| `pydantic` | project constraint `>=2.0.0`; latest `2.13.1` (published 2026-04-15) [VERIFIED: `pyproject.toml`; CITED: https://pypi.org/pypi/pydantic/json] | Canonical event schema models (`CanonicalTrajectoryHeader`, step/score/metrics models) | Existing schema models already use Pydantic; extending contract should stay model-driven. [VERIFIED: `src/mobile_world/runtime/protocol/events.py`] |
| `pytest` | project constraint `>=7.4.0`; `uv run --extra dev` currently resolves `8.4.2`; latest `9.0.3` (published 2026-04-07) [VERIFIED: `pyproject.toml`; VERIFIED: local `uv run --extra dev python -m pytest --version`; CITED: https://pypi.org/pypi/pytest/json] | Regression gating for artifact contract behavior | Existing protocol phases already enforce behavior through pytest under `tests/protocol`. [VERIFIED: test tree in `tests/protocol/`] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `jsonlines` | project constraint `>=4.0.0`; latest `4.0.0` [VERIFIED: `pyproject.toml`; CITED: https://pypi.org/pypi/jsonlines/json] | Canonical JSONL event file handling | Keep JSONL append-only semantics for runtime event stream. [VERIFIED: `src/mobile_world/runtime/utils/trajectory_logger.py`] |
| `rich` | project constraint `>=13.0.0`; latest `15.0.0` (2026-04-12) [VERIFIED: `pyproject.toml`; CITED: https://pypi.org/pypi/rich/json] | CLI display for conformance output | Continue using existing benchmark CLI output behavior. [VERIFIED: `src/mobile_world/core/subcommands/benchmark.py`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Fix runtime writer to satisfy validator | Loosen validator checks for missing header/policy | Reject; this would hide real contract drift and re-open COMP-02/TRCE-01 risk. [VERIFIED: conformance check names in `src/mobile_world/runtime/protocol/conformance.py`] |
| Serialize policy manifest from resolved `CapabilityDecision` | Build ad-hoc policy dict in runner | Reject; duplicates schema and risks field drift against policy engine output. [VERIFIED: `CapabilityDecision.as_manifest()` in `src/mobile_world/runtime/protocol/capability_policy.py`] |
| Add eval-path regression test | Keep only synthetic fixture conformance test | Reject; current synthetic test passes even when runtime path misses required fields. [VERIFIED: `tests/protocol/test_phase6_reporting_conformance_reproducibility.py`; local conformance CLI probe] |

**Installation:**
```bash
UV_CACHE_DIR=/tmp/.uv-cache uv sync --extra dev
```

**Version verification (used in this research):**
```bash
python3 - <<'PY'
import json, urllib.request
for p in ['pydantic','pytest','jsonlines','rich']:
    data=json.load(urllib.request.urlopen(f'https://pypi.org/pypi/{p}/json'))
    print(p, data['info']['version'])
PY
```

## Architecture Patterns

### System Architecture Diagram

```text
mobile-world eval (CLI)
  -> run_agent_with_evaluation (runner)
     -> resolve_capability_policy(...)
     -> TrajLogger.log_tool_manifest(...)
     -> TrajLogger.log_policy_manifest(...)   [Phase 7 target]
     -> _execute_single_task(...)
        -> TrajLogger.log_traj(...)
           -> append canonical header (once)  [Phase 7 target]
           -> append canonical step event(s)
        -> TrajLogger.log_metrics_summary(...)
        -> TrajLogger.log_evaluator_audit(...)
        -> TrajLogger.log_score(...)
  -> run artifact directory (traj.json, traj.canonical.jsonl, traj.meta.json, metrics, audit, score)

mobile-world benchmark conformance --log-root <run_root> (CLI)
  -> run_conformance_suite(...)
     -> validate adapter contracts
     -> validate canonical schema
     -> validate per-task artifact checks:
        - canonical.header_present
        - meta.policy_manifest_present
        - metrics/evaluator contracts
  -> PASS / FAIL report
```

Data-flow contract is already explicit; Phase 7 only closes missing writes on the eval side. [VERIFIED: `src/mobile_world/core/subcommands/eval.py`, `src/mobile_world/core/subcommands/benchmark.py`, `src/mobile_world/runtime/protocol/conformance.py`]

### Recommended Project Structure
```text
src/mobile_world/
├── core/runner.py                         # capability decision + logger calls in eval runtime
├── runtime/utils/trajectory_logger.py     # canonical event/meta persistence
├── runtime/protocol/conformance.py        # artifact validator contract
└── runtime/protocol/events.py             # canonical schema models
tests/protocol/
├── test_canonical_trajectory_contract.py
├── test_phase6_reporting_conformance_reproducibility.py
└── test_phase7_conformance_artifact_contract.py  # recommended new file
```

### Pattern 1: Emit-Once Header + Append-Only Events
**What:** Header event is emitted exactly once per task run in canonical JSONL; subsequent events append step/metrics/score/audit records. [VERIFIED: conformance requires header in JSONL; current logger appends events line-by-line]
**When to use:** Every runtime task execution path that writes canonical artifacts. [VERIFIED: `_execute_single_task` always calls logger methods]
**Example:**
```python
# Source: src/mobile_world/runtime/utils/trajectory_logger.py + src/mobile_world/runtime/protocol/events.py
if not self._header_event_already_written():
    self._append_canonical_event(CanonicalTrajectoryHeader(...).model_dump())
self._append_canonical_event(canonical_step.model_dump())
```

### Pattern 2: Manifest Parity Between Policy Engine and Artifact Metadata
**What:** Persist policy manifest from `CapabilityDecision.as_manifest()` into canonical metadata as a dedicated `policy_manifest` object. [VERIFIED: `as_manifest()` exists; conformance checks `meta.policy_manifest_present`]
**When to use:** Immediately after capability resolution and before/at first trajectory write for a task run. [VERIFIED: capability is resolved in `_process_task_on_env` before task execution]
**Example:**
```python
# Source: src/mobile_world/core/runner.py + src/mobile_world/runtime/protocol/capability_policy.py
capability_decision = resolve_capability_policy(...)
traj_logger.log_tool_manifest(capability_decision.as_manifest())
traj_logger.log_policy_manifest(capability_decision.as_manifest())  # Phase 7 target
```

### Anti-Patterns to Avoid
- **Header-only-in-meta:** Writing header structure only to `traj.meta.json` but never to canonical JSONL will fail conformance. [VERIFIED: current failure condition + `canonical.header_present` check]
- **Synthetic-only coverage:** Tests that build hand-crafted valid bundles can pass while real eval output remains non-conformant. [VERIFIED: `test_phase6_reporting_conformance_reproducibility.py` fixture pattern + local probe]
- **Independent manifest schemas:** Generating policy manifest fields outside capability policy object risks divergence and hidden policy artifacts drift. [VERIFIED: `CapabilityDecision.as_manifest()` provides canonical shape]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Canonical header payload shaping | Manual dicts scattered across runner/logger | `CanonicalTrajectoryHeader` model | Maintains schema-version consistency and prevents missing required fields. [VERIFIED: `src/mobile_world/runtime/protocol/events.py`] |
| Policy manifest serialization | Custom one-off JSON layout | `CapabilityDecision.as_manifest()` output | One source of truth for deterministic policy fields. [VERIFIED: `src/mobile_world/runtime/protocol/capability_policy.py`] |
| Artifact conformance checker | New standalone script | Existing `run_conformance_suite` + CLI wrapper | Contract checks already centralized and used by benchmark CLI. [VERIFIED: `src/mobile_world/runtime/protocol/conformance.py`, `src/mobile_world/core/subcommands/benchmark.py`] |
| End-to-end verification | Manual spot-checking files | Pytest regression + CLI smoke command | Repeatable and CI-friendly gate for COMP-02/TRCE-01. [VERIFIED: existing protocol test harness + CLI commands] |

**Key insight:** Phase 7 is a producer-side contract repair; validator-side behavior is already explicit and should remain the acceptance oracle. [VERIFIED: conformance check definitions]

## Common Pitfalls

### Pitfall 1: Writing Header on Every Step
**What goes wrong:** Multiple header events bloat trajectories and can obscure event ordering semantics. [ASSUMED]
**Why it happens:** Header write is triggered inside per-step path without an idempotent guard. [ASSUMED]
**How to avoid:** Add a one-time emission guard keyed by canonical log content or in-memory flag reset per task logger instance. [ASSUMED]
**Warning signs:** More than one `"type":"header"` line appears in `traj.canonical.jsonl`. [ASSUMED]

### Pitfall 2: Persisting Policy Manifest Too Late
**What goes wrong:** Early failures before first step may produce artifacts without `policy_manifest`. [ASSUMED]
**Why it happens:** Manifest write is deferred until after action loop begins. [ASSUMED]
**How to avoid:** Persist policy manifest immediately after capability resolution in `_process_task_on_env`. [VERIFIED: capability resolution location in `src/mobile_world/core/runner.py`]
**Warning signs:** Conformance failures show only `meta.policy_manifest_present` missing while other files exist. [VERIFIED: local conformance probe]

### Pitfall 3: Relying on Synthetic Fixtures as End-to-End Proof
**What goes wrong:** Conformance tests pass but runtime eval outputs still fail contract checks. [VERIFIED: current test composition + local probe]
**Why it happens:** Fixture helper manually writes header/policy fields that runtime path does not currently write. [VERIFIED: `tests/protocol/test_phase6_reporting_conformance_reproducibility.py`]
**How to avoid:** Add regression that generates artifacts through logger/runner path before calling conformance suite. [VERIFIED: existing runtime/conformance APIs]
**Warning signs:** `test_conformance_suite_passes_for_valid_artifacts` remains green while `mobile-world benchmark conformance --log-root <real eval root>` fails. [VERIFIED: local CLI probe]

## Code Examples

Verified patterns from current code + required closure:

### Runtime Gap Reproduction (Current Behavior)
```bash
# Source: local run on 2026-04-17
.venv/bin/mobile-world benchmark conformance --log-root /tmp/<runtime-generated-run-root>
# Fails with:
# - canonical.header_present
# - meta.policy_manifest_present
```

### Canonical Conformance Checks (Acceptance Oracle)
```python
# Source: src/mobile_world/runtime/protocol/conformance.py
add_check("canonical.header_present", "header" in event_types)
add_check("meta.policy_manifest_present", "policy_manifest" in meta)
```

### Existing Runtime Write Path to Extend
```python
# Source: src/mobile_world/core/runner.py
capability_decision = resolve_capability_policy(...)
traj_logger.log_tool_manifest(capability_decision.as_manifest())
# Phase 7 addition should persist policy_manifest here (or equivalent earliest safe point)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Legacy `traj.json` only | Dual-write legacy + canonical artifacts (`traj.canonical.jsonl`, `traj.meta.json`) | Phase 1 implementation period [VERIFIED: Phase 1 summaries + logger code] | Enabled framework-agnostic artifact processing but left header-in-JSONL gap in runtime path. [VERIFIED: logger code + audit findings] |
| No benchmark conformance CLI | `mobile-world benchmark conformance` validates adapter/schema/task artifacts | Phase 6 [VERIFIED: Phase 6 plan/summary + benchmark subcommand] | Contract oracle exists and now exposes producer-side drift for Phase 7 closure. [VERIFIED: conformance code + audit] |
| Synthetic conformance fixture only | Need runtime-generated artifact regression for eval->conformance flow | Phase 7 target [VERIFIED: current tests + roadmap Phase 7 success criteria] | Prevents false green state where fixture passes but real eval path fails. [VERIFIED: local probe + audit] |

**Deprecated/outdated:**
- Treating `traj.meta.json` header object as sufficient proof of canonical header event is outdated for conformance because validator requires `header` in JSONL events. [VERIFIED: conformance check logic + current logger behavior]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Emitting multiple header events is undesirable even if current conformance only checks presence. | Common Pitfalls | Low: conformance may still pass, but trace quality and downstream tooling behavior may degrade. |
| A2 | Header duplication usually comes from missing idempotent guards in per-step write paths. | Common Pitfalls | Medium: can produce noisy/ambiguous traces and brittle downstream parsing assumptions. |
| A3 | A one-time header emission guard should be added in logger runtime path. | Common Pitfalls | Low: implementation may still be acceptable without strict guard if validated differently. |
| A4 | More than one `header` JSONL row should be treated as warning-sign behavior. | Common Pitfalls | Low: may be acceptable for some consumers if they only check presence. |
| A5 | Early failure before first step can leave policy manifest absent if write timing is late. | Common Pitfalls | Medium: edge-case conformance regressions can persist. |
| A6 | Deferring policy manifest write until inside action loop is an unsafe timing point. | Common Pitfalls | Medium: can fail artifact completeness under early termination/error paths. |
| A7 | Phase 7 should keep strict-order (`header first`) enforcement out of immediate scope. | Open Questions | Low: ordering hardening might be needed sooner by downstream consumers. |
| A8 | ASVS V2 Authentication does not apply to this local artifact contract closure scope. | Security Domain | Low: if auth boundaries exist in a deployment variant, security checks may be incomplete. |
| A9 | ASVS V3 Session Management does not apply to this phase scope. | Security Domain | Low: same as above for deployment-specific surfaces. |
| A10 | ASVS V4 Access Control does not apply to this phase scope. | Security Domain | Medium: if CLI is exposed in multi-tenant environment, access controls may matter. |
| A11 | ASVS V6 Cryptography changes are not required for this contract closure. | Security Domain | Low: if artifact integrity signatures are mandatory in some contexts, this would be incomplete. |

## Open Questions (RESOLVED)

1. **Should conformance require header ordering (`header` must be first event) instead of only presence?**
   - What we know: current validator only checks presence, not order. [VERIFIED: `src/mobile_world/runtime/protocol/conformance.py`]
   - RESOLVED: Phase 7 will enforce canonical header presence and emit-once behavior, but will not change validator policy to require strict first-event ordering in this phase. Ordering hardening is deferred to a follow-up conformance hardening phase. [VERIFIED: `src/mobile_world/runtime/protocol/conformance.py`, `.planning/ROADMAP.md`]

2. **Should `policy_manifest.profile_name` remain `agent_type` in adapter mode until Phase 8?**
   - What we know: current resolution uses `profile_name=agent_type` in runner, and Phase 8 is scoped to fix profile-bound policy semantics. [VERIFIED: `src/mobile_world/core/runner.py`, `.planning/ROADMAP.md`]
   - RESOLVED: Keep `policy_manifest.profile_name` mapped to `agent_type` for Phase 7 adapter-mode artifacts, and defer profile-name semantic changes to Phase 8 exactly as scoped. Phase 7 only closes manifest presence/persistence requirements. [VERIFIED: `src/mobile_world/core/runner.py`, `.planning/ROADMAP.md`]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python runtime (project target) | Eval runtime + tests | ✓ (via `.venv`) | 3.12.12 [VERIFIED: `.venv/bin/python --version`] | Use `.venv/bin/python` explicitly |
| `uv` | Reproducible command execution and dev deps | ✓ | 0.9.16 [VERIFIED: `uv --version`] | — |
| `pytest` (global binary) | Test execution | ✗ [VERIFIED: `command -v pytest`] | — | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest` (verified working, resolves pytest 8.4.2) [VERIFIED: local run] |
| `mobile-world` (global binary) | CLI eval/conformance commands | ✗ [VERIFIED: `command -v mobile-world`] | — | `.venv/bin/mobile-world` or `uv run mobile-world` [VERIFIED: local run] |
| Docker daemon | Auto-discovery eval path when `--aw-host` not provided | ✗ (CLI exists, daemon unavailable) [VERIFIED: `docker ps` error] | Docker CLI 29.1.2 [VERIFIED: `docker --version`] | Provide explicit reachable `--aw-host` backend(s) |
| `adb` + connected device | Android interaction path | ✓ | ADB 1.0.41; device listed (`f11f539`) [VERIFIED: `adb version`, `adb devices`] | Use configured backend URL if direct adb path is not required |

**Missing dependencies with no fallback:**
- None identified for Phase 7 code/test implementation path. [VERIFIED: local environment audit]

**Missing dependencies with fallback:**
- Global `pytest`, global `mobile-world`, and Docker daemon availability. [VERIFIED: local environment audit]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` (resolved as 8.4.2 via `uv run --extra dev`) [VERIFIED: local command output] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` [VERIFIED: `pyproject.toml`] |
| Quick run command | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_canonical_trajectory_contract.py tests/protocol/test_phase6_reporting_conformance_reproducibility.py::test_conformance_suite_passes_for_valid_artifacts` [VERIFIED: local run passed on 2026-04-17] |
| Full suite command | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol` [VERIFIED: command shape matches existing suite layout] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COMP-02 | Runtime-generated task artifacts pass `run_conformance_suite` with `ok=True` when produced through eval/logger path. [VERIFIED: requirement text + conformance API] | integration | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase7_conformance_artifact_contract.py::test_runtime_artifacts_pass_conformance` | ❌ Wave 0 |
| TRCE-01 | Canonical JSONL written by runtime includes one `header` event with canonical schema version in addition to step/score/metrics events. [VERIFIED: requirement + conformance checks] | unit/integration | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_canonical_trajectory_contract.py::test_trajectory_logger_writes_legacy_and_canonical_artifacts` | ✅ (needs assertion updates) |

### Sampling Rate
- **Per task commit:** `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_canonical_trajectory_contract.py tests/protocol/test_phase7_conformance_artifact_contract.py`
- **Per wave merge:** `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol`
- **Phase gate:** Run representative eval artifact generation then `mobile-world benchmark conformance --log-root <run_root>` with PASS required. [VERIFIED: phase success criteria + benchmark CLI]

### Wave 0 Gaps
- [ ] `tests/protocol/test_phase7_conformance_artifact_contract.py` — add eval/logger-path-to-conformance regression covering COMP-02/TRCE-01.
- [ ] Update `tests/protocol/test_canonical_trajectory_contract.py` — assert canonical JSONL includes required header event.
- [ ] Add/extend helper fixture to build runner-like artifact bundle through runtime writer path (not manual JSON fixture writing).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Not in scope for local artifact validation flow. [ASSUMED] |
| V3 Session Management | no | Not in scope for this CLI artifact-processing phase. [ASSUMED] |
| V4 Access Control | no | No role/permission boundary changes in Phase 7 target paths. [ASSUMED] |
| V5 Input Validation | yes | Explicit JSON/JSONL structural checks and Pydantic canonical event models. [VERIFIED: `conformance.py`, `events.py`] |
| V6 Cryptography | no | No cryptographic primitive changes are required for artifact contract closure. [ASSUMED] |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Artifact tampering or incomplete artifacts | Tampering | Required-file checks + required-field checks (`header`, `policy_manifest`) + schema-version consistency checks in conformance suite. [VERIFIED: `src/mobile_world/runtime/protocol/conformance.py`] |
| Malformed JSON/JSONL payloads | Denial of Service | Fail-fast JSON parsing and contract validation with per-check failure reporting. [VERIFIED: `_read_json`, `_read_jsonl`, check aggregation in `conformance.py`] |
| Path misuse via `--log-root` | Tampering / Information Disclosure | Use explicit task-directory traversal and fixed expected file names under run root. [VERIFIED: `run_conformance_suite` + `validate_task_artifacts`] |

## Sources

### Primary (HIGH confidence)
- `.planning/ROADMAP.md` — Phase 7 goal, dependencies, success criteria, and adjacent phase scope.
- `.planning/REQUIREMENTS.md` — requirement definitions for `COMP-02` and `TRCE-01`.
- `.planning/v1.0-v1.0-MILESTONE-AUDIT.md` — blocker gap evidence for eval->conformance flow.
- `src/mobile_world/runtime/protocol/conformance.py` — authoritative conformance check names and required artifact fields.
- `src/mobile_world/runtime/utils/trajectory_logger.py` — current canonical writer behavior and metadata persistence.
- `src/mobile_world/core/runner.py` — capability resolution and manifest logging call sites.
- `src/mobile_world/runtime/protocol/capability_policy.py` — `CapabilityDecision` manifest shape.
- `tests/protocol/test_canonical_trajectory_contract.py` — current canonical artifact contract assertions.
- `tests/protocol/test_phase6_reporting_conformance_reproducibility.py` — current conformance test strategy (synthetic bundle).
- Local command probes run on 2026-04-17:
  - `uv run --extra dev python -m pytest ...` (target tests pass)
  - `.venv/bin/mobile-world benchmark conformance --log-root <runtime probe>` (fails on header/policy)
  - environment availability checks (`python`, `uv`, `pytest`, `mobile-world`, `docker`, `adb`)

### Secondary (MEDIUM confidence)
- PyPI JSON API for latest package versions and publish timestamps:
  - https://pypi.org/pypi/pydantic/json
  - https://pypi.org/pypi/pytest/json
  - https://pypi.org/pypi/jsonlines/json
  - https://pypi.org/pypi/rich/json
  - https://pypi.org/pypi/fastapi/json
  - https://pypi.org/pypi/uvicorn/json
  - https://pypi.org/pypi/mcp/json
  - https://pypi.org/pypi/fastmcp/json

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Derived from project constraints (`pyproject.toml`) plus live PyPI version verification.
- Architecture: HIGH - Direct code-path tracing from eval runner through logger to conformance validator.
- Pitfalls: MEDIUM - Rooted in verified code/tests, but some failure-mode severity/order assumptions are inferential.

**Research date:** 2026-04-17  
**Valid until:** 2026-05-17 (30 days; internal architecture is stable but package versions are fast-moving)
