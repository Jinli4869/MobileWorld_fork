---
phase: 09-reproducibility-agreement-gate-hardening
plan: 01
subsystem: runtime-protocol
tags: [reproducibility, judge-agreement, gate-semantics]
requires:
  - phase: 06-reporting-conformance-reproducibility
    provides: baseline reproducibility metric computation and benchmark command wiring
provides:
  - stability gate result is evaluated independently from judge-agreement availability
  - missing judge checks no longer force top-level reproducibility failure
  - agreement threshold enforcement remains active when judge checks exist
affects: [benchmark-reproducibility, phase-09-wave-2]
tech-stack:
  added: []
  patterns: [availability-aware-gating]
key-files:
  created: []
  modified:
    - src/mobile_world/runtime/protocol/reproducibility.py
key-decisions:
  - "Treat agreement availability as a first-class branch in gate composition instead of implicit failure."
  - "Keep existing reproducibility payload keys while correcting top-level `ok` semantics."
requirements-completed: [METR-06, METR-07]
duration: 3 min
completed: 2026-04-17
---

# Phase 09 Plan 01: Reproducibility Agreement Gate Hardening Summary

**Reproducibility now passes deterministic stability checks even when judge-agreement data is unavailable, while preserving threshold enforcement when judge checks are present.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-17T08:49:00Z
- **Completed:** 2026-04-17T08:51:50Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Added explicit `agreement_available` branching in reproducibility evaluation.
- Reworked top-level `ok` to depend on stability plus agreement threshold only when judge checks exist.
- Preserved existing report shape and threshold inputs for compatibility with downstream commands.

## Task Commits

Each task was committed atomically:

1. **Task 1: Decouple stability gate from judge-agreement availability in reproducibility core logic** - `4fff6e4` (fix)

## Files Created/Modified
- `src/mobile_world/runtime/protocol/reproducibility.py` - Availability-aware agreement gate composition for reproducibility status.

## Decisions Made
- Represented non-applicable agreement pass state as `None` when no judge checks exist.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Verification passed:
  - `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase6_reporting_conformance_reproducibility.py::test_reproducibility_reports_variance_and_judge_agreement`
- Ready for `09-02-PLAN.md`.

## Self-Check: PASSED
- Verified summary file exists on disk.
- Verified task commit hash exists in git history (`4fff6e4`).
