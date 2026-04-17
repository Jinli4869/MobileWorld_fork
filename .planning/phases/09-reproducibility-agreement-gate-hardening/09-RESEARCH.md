# Phase 9: Reproducibility Agreement Gate Hardening - Research

**Researched:** 2026-04-17  
**Domain:** Reproducibility pass/fail semantics when judge-agreement data is missing  
**Confidence:** HIGH

## User Constraints

### Locked Decisions
- Phase 9 goal is to resolve reproducibility gate edge cases when judge agreement data is unavailable.
- Phase 9 must satisfy `METR-06`, `METR-07`, and `COMP-03`.
- Stability variance should remain a deterministic gate independent from judge availability.
- Judge-agreement thresholds must still be enforced when judge checks exist.

### Agent's Discretion
- Exact report field names for agreement-availability and gate-status metadata.
- Whether regression coverage extends phase-6 tests or uses a dedicated phase-9 test module (or both).
- Exact CLI reporting text for reproducibility status summaries.

### Deferred Ideas (Out of Scope)
- Redesigning evaluator audit schemas across unrelated commands.
- Changing trajectory judge provider behavior or API integration.
- Reworking cross-framework aggregation ranking logic.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| METR-06 | System reports stability metrics including reproducibility variance across repeated fixed-config runs. | Keep variance gate explicit and independently evaluated in reproducibility report. |
| METR-07 | System reports evaluator quality metrics including deterministic evaluator vs LLM-judge agreement rate. | Add explicit agreement availability/pass fields so missing judge data is not conflated with failing agreement. |
| COMP-03 | Regression tests ensure benchmark reproducibility between repeated runs under same config. | Add regression cases for judge-available and judge-unavailable scenarios with deterministic expected outcomes. |

</phase_requirements>

## Summary

Current `evaluate_reproducibility(...)` logic computes:
- `variance_ok` from per-task variance checks
- `judge_ok` from `judge_agreement_rate is not None and >= threshold`
- top-level `ok = variance_ok and judge_ok`

That means runs with no judge checks (`judge_total == 0`) always set `judge_agreement_rate = None`, then `judge_ok = False`, and force overall failure even when deterministic variance passes. This conflicts with the Phase 9 goal and blocks stable runs where judge signals are intentionally unavailable.

Recommended closure strategy:
1. Keep stability variance as an independent gate and continue enforcing it.
2. Treat missing judge checks as `agreement unavailable` (not automatic agreement failure).
3. Enforce agreement threshold strictly when judge checks exist.
4. Expose explicit report fields and CLI output so operators can distinguish:
   - stability failed
   - agreement failed
   - agreement unavailable
5. Add deterministic tests for both with-judge and without-judge branches.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Reproducibility gate semantics | Runtime Protocol (`reproducibility.py`) | Benchmark CLI (`benchmark.py`) | Protocol computes truth; CLI renders operator-facing status. |
| Agreement availability reporting | Runtime Protocol | Docs/Operator guidance | Missing-judge branch must be explicit for trustworthy interpretation. |
| Regression confidence for gate behavior | Protocol tests | Reproducibility utility | Tests must pin both available and unavailable agreement paths. |

## Existing Code Findings

### Primary Gap
- `src/mobile_world/runtime/protocol/reproducibility.py` currently hard-fails top-level `ok` when `judge_agreement_rate` is `None`, even if all variance checks pass.
- No explicit report field currently distinguishes `agreement unavailable` from `agreement failed`.

### Flow Surface to Update
- `src/mobile_world/core/subcommands/benchmark.py` prints reproducibility PASS/FAIL based on report `ok` only and does not surface agreement availability state.
- `docs/benchmark_reporting.md` currently documents rate/threshold output but not unavailable-state semantics.

### Existing Strengths to Reuse
- Per-task reproducibility variance and threshold logic is already deterministic.
- Judge-agreement extraction from evaluator audit consistency checks already exists.
- Phase 6 synthetic artifact test helpers can be reused for deterministic branch testing.

## Recommended Plan Decomposition

| Plan | Scope | Why |
|------|-------|-----|
| 09-01 | Refine gate semantics so missing judge data does not force false hard-failure | Fixes root logic bug with minimum blast radius |
| 09-02 | Add explicit agreement-availability and threshold-outcome reporting fields + CLI summary | Makes result interpretation unambiguous for operators |
| 09-03 | Add regression tests for judge-available and judge-unavailable paths | Prevents future semantic drift and closes COMP-03 confidence gap |

## Files Likely To Be Modified

| File | Purpose |
|------|---------|
| `src/mobile_world/runtime/protocol/reproducibility.py` | Gate logic hardening and report-field expansion |
| `src/mobile_world/core/subcommands/benchmark.py` | CLI status summary for agreement availability/outcome |
| `tests/protocol/test_phase6_reporting_conformance_reproducibility.py` | Align existing reproducibility assertions to hardened semantics |
| `tests/protocol/test_phase9_reproducibility_agreement_gate.py` (new) | Focused regression coverage for agreement available/unavailable branches |
| `docs/benchmark_reporting.md` | Operator-facing explanation of new report fields and gate outcomes |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Consumers assume `agreement_passed` is always boolean | Downstream parser breakage | Introduce explicit availability field and keep top-level gate semantics stable/clear |
| Over-correcting logic to always pass without judge checks | Masks real agreement failures | Enforce threshold whenever judge checks exist (`agreement_available == true`) |
| Test blind spots around unavailable-judge branch | Regression can reappear silently | Add dedicated phase-9 tests with synthetic artifacts lacking judge checks |

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` via `uv run --extra dev` |
| Config file | `pyproject.toml` |
| Quick run command | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase9_reproducibility_agreement_gate.py tests/protocol/test_phase6_reporting_conformance_reproducibility.py` |
| Full protocol run | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol` |

### Requirements -> Verification Map

| Req ID | Behavior | Test Type | Command |
|--------|----------|-----------|---------|
| METR-06 | Variance gate remains deterministic and independently evaluated | unit/integration | `... pytest -q tests/protocol/test_phase9_reproducibility_agreement_gate.py::test_reproducibility_stability_gate_passes_without_judge_data` |
| METR-07 | Agreement gate is enforced when judge checks are available | unit/integration | `... pytest -q tests/protocol/test_phase9_reproducibility_agreement_gate.py::test_reproducibility_fails_when_judge_available_and_below_threshold` |
| COMP-03 | Regression suite covers both judge-available and judge-unavailable scenarios | integration | `... pytest -q tests/protocol/test_phase9_reproducibility_agreement_gate.py tests/protocol/test_phase6_reporting_conformance_reproducibility.py` |

### Wave 0 Gaps
- [ ] `tests/protocol/test_phase9_reproducibility_agreement_gate.py` must be created.
- [ ] Existing phase-6 reproducibility assertions must be updated to include agreement-availability semantics.

## Security Domain

| Category | Applies | Notes |
|----------|---------|-------|
| Input Validation | yes | Threshold and availability calculations must remain deterministic for malformed/missing judge data. |
| Access Control | no | No auth/session boundary changes in this phase. |
| Cryptography | no | No cryptographic logic is introduced or modified. |

## Open Questions (Resolved for Planning)

1. Should missing judge data hard-fail reproducibility?
- Planned resolution: **No**. Missing judge data should be reported as unavailable while still allowing deterministic stability pass/fail.

2. Should agreement thresholds still gate results when judge data exists?
- Planned resolution: **Yes**. Agreement threshold remains enforced whenever judge checks are present.

3. Should CLI output expose agreement availability explicitly?
- Planned resolution: **Yes**. CLI must surface availability/outcome to avoid ambiguous PASS/FAIL interpretation.
