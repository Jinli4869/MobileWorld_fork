---
phase: 07-conformance-artifact-contract-closure
plan: 01
subsystem: runtime
tags: [trajectory, conformance, canonical-schema, pytest]
requires:
  - phase: 06-reporting-conformance-reproducibility
    provides: canonical trajectory/events contracts and conformance checks
provides:
  - runtime canonical JSONL header emission guard with idempotent behavior
  - regression test enforcing single canonical header event presence
affects: [phase-07-plan-02, phase-07-plan-03, conformance-suite]
tech-stack:
  added: []
  patterns: [emit-once-header-guard, model-backed-header-serialization]
key-files:
  created: []
  modified:
    - src/mobile_world/runtime/utils/trajectory_logger.py
    - tests/protocol/test_canonical_trajectory_contract.py
key-decisions:
  - "Emit canonical header using CanonicalTrajectoryHeader before canonical step/score/metrics writes."
  - "Use an idempotent guard that checks existing JSONL header rows to prevent duplicates."
patterns-established:
  - "Canonical header is guaranteed by runtime writer, not only by canonical meta file."
  - "Contract tests must assert event-type counts (header/step/score), not only event order."
requirements-completed: [TRCE-01]
duration: 1 min
completed: 2026-04-17
---

# Phase 07 Plan 01: Canonical Header Contract Closure Summary

**Runtime now emits exactly one canonical `header` event in JSONL artifacts while preserving step/score event integrity, with regression coverage for header uniqueness and schema identity.**

## Performance

- **Duration:** 1 min
- **Started:** 2026-04-17T07:12:14Z
- **Completed:** 2026-04-17T07:13:18Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added a private emit-once guard in `TrajLogger` that writes canonical header events via `CanonicalTrajectoryHeader`.
- Wired header guarding into `log_traj`, `log_score`, and `log_metrics_summary` so non-step-first flows are covered.
- Strengthened canonical contract tests to fail on missing or duplicate headers while still asserting step/score events.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add emit-once canonical header insertion in runtime logger** - `1a5079a` (fix)
2. **Task 2: Strengthen canonical contract test for header presence and uniqueness** - `688b74e` (test)

## Files Created/Modified
- `src/mobile_world/runtime/utils/trajectory_logger.py` - Added idempotent canonical header emission guard and call sites.
- `tests/protocol/test_canonical_trajectory_contract.py` - Added assertions for exactly one header event plus task/schema identity checks.

## Decisions Made
- Header emission is enforced in runtime JSONL writer paths (`log_traj`, `log_score`, `log_metrics_summary`) instead of relying on metadata-only header objects.
- Header payload construction uses `CanonicalTrajectoryHeader` model serialization to keep schema version and field shape canonical.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Task-level and plan-level verification command passed: `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_canonical_trajectory_contract.py`
- Ready for `07-02-PLAN.md` (policy manifest contract closure).

## Self-Check: PASSED
- Verified summary file exists on disk.
- Verified Task 1 and Task 2 commit hashes exist in git history.
