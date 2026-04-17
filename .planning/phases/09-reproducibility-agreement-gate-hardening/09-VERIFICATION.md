---
phase: 09-reproducibility-agreement-gate-hardening
verified: 2026-04-17T08:58:13Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
---

# Phase 9: Reproducibility Agreement Gate Hardening Verification Report

**Phase Goal:** Resolve reproducibility gate edge cases when judge agreement data is unavailable.  
**Verified:** 2026-04-17T08:58:13Z  
**Status:** passed

## Goal Achievement

### Must-Haves Verification

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Stability variance pass/fail is evaluated independently from judge-agreement availability | ✓ VERIFIED | `agreement_available = judge_total > 0` plus availability-aware `overall_ok` composition in `src/mobile_world/runtime/protocol/reproducibility.py` |
| 2 | Runs with no judge checks do not false-fail top-level reproducibility gate when stability passes | ✓ VERIFIED | `overall_ok = variance_ok and (agreement_passed if agreement_available else True)` in `reproducibility.py` and `test_reproducibility_stability_gate_passes_without_judge_data` |
| 3 | Judge-agreement threshold remains enforced when judge checks exist | ✓ VERIFIED | `agreement_passed` computed from `judge_agreement_rate >= judge_agreement_threshold` on available branch; enforced by `test_reproducibility_fails_when_judge_available_and_below_threshold` |
| 4 | Reproducibility report distinguishes agreement availability from threshold outcomes | ✓ VERIFIED | `evaluation_quality` now includes `agreement_available`, `agreement_status`, and `agreement_passed` |
| 5 | Report includes explicit gate-level status summary | ✓ VERIFIED | `gate_summary` contains `stability_gate`, `agreement_gate`, and `overall_status` fields |
| 6 | CLI output surfaces agreement state alongside PASS/FAIL | ✓ VERIFIED | Reproducibility CLI summary in `src/mobile_world/core/subcommands/benchmark.py` includes `agreement: {status}; judge checks: {count}` |
| 7 | Operator docs explain unavailable-agreement branch semantics | ✓ VERIFIED | `docs/benchmark_reporting.md` includes agreement availability/status fields and unavailable/threshold semantics |
| 8 | Regression tests cover judge-available and judge-unavailable scenarios | ✓ VERIFIED | `tests/protocol/test_phase9_reproducibility_agreement_gate.py` adds deterministic coverage for both branches |
| 9 | One canonical combined phase-9 regression command is aligned across test and validation artifacts | ✓ VERIFIED | `PHASE9_COMBINED_REGRESSION_CMD` in phase-9 test module and matching quick/full commands in `09-VALIDATION.md` |

## Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| METR-06 | System reports stability metrics including reproducibility variance across repeated fixed-config runs | ✓ SATISFIED | Stability gate retained and independently verified in phase-6/phase-9 reproducibility tests |
| METR-07 | System reports evaluator quality metrics including deterministic evaluator vs LLM-judge agreement rate | ✓ SATISFIED | Agreement availability/status fields plus threshold-enforced available branch semantics |
| COMP-03 | Regression tests ensure benchmark reproducibility between repeated runs under same config | ✓ SATISFIED | Phase-9 deterministic regression suite and combined command verification |

## Behavioral Verification Commands

- `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase9_reproducibility_agreement_gate.py` → pass
- `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase6_reporting_conformance_reproducibility.py::test_reproducibility_reports_variance_and_judge_agreement` → pass
- `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase9_reproducibility_agreement_gate.py tests/protocol/test_phase6_reporting_conformance_reproducibility.py` → pass
- `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol` → pass (42 passed)

## Gaps

None.

---

_Verified: 2026-04-17T08:58:13Z_  
_Verifier: Codex (inline execute-phase verification)_
