---
phase: 08-framework-profile-policy-flow-repair
plan: 02
subsystem: protocol-tests
tags: [framework-profile, policy-manifest, runner, regression]
requires:
  - phase: 08-framework-profile-policy-flow-repair
    provides: effective policy profile selection in runner
provides:
  - deterministic runner-path regression harness for framework-profile policy semantics
  - artifact assertions for policy_manifest profile alignment across framework and built-in modes
affects: [protocol-test-suite, capability-policy-guardrails]
tech-stack:
  added: []
  patterns: [runner-seam-monkeypatching, artifact-manifest-assertions]
key-files:
  created:
    - tests/protocol/test_phase8_framework_profile_policy_flow.py
  modified: []
key-decisions:
  - "Use `_process_task_on_env` with monkeypatched seams instead of synthetic helper-only assertions."
  - "Assert `policy_manifest.profile_name` from persisted artifacts in both legacy and canonical metadata."
requirements-completed: [TOOL-02]
duration: 7 min
completed: 2026-04-17
---

# Phase 08 Plan 02: Framework Profile Policy Flow Repair Summary

**Phase-8 protocol regressions now lock framework-profile policy resolution input and persisted policy-manifest profile alignment.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-17T08:23:00Z
- **Completed:** 2026-04-17T08:29:56Z
- **Tasks:** 3
- **Files modified:** 1

## Accomplishments
- Created an emulator-free test harness around `_process_task_on_env` using deterministic monkeypatched seams.
- Added regression for resolver input identity to ensure adapter-mode uses `framework_profile`.
- Added artifact-level regression that validates `policy_manifest.profile_name` in both `traj.json` and `traj.meta.json` for framework and fallback branches.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create phase-8 protocol test module with runner test doubles** - `82885c1` (test)
2. **Task 2: Assert runner uses framework profile for policy resolution** - `3a23b48` (test)
3. **Task 3: Assert policy manifest profile_name matches effective profile in artifacts** - `9737556` (test)

## Files Created/Modified
- `tests/protocol/test_phase8_framework_profile_policy_flow.py` - Added deterministic runner-path regressions and artifact profile alignment assertions.

## Decisions Made
- Kept test scope at protocol seams to avoid Android backend dependencies while still exercising production runner code path.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Verification passed:
  - `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase8_framework_profile_policy_flow.py`
- Ready for `08-03-PLAN.md`.

## Self-Check: PASSED
- Verified summary file exists on disk.
- Verified task commit hashes exist in git history (`82885c1`, `3a23b48`, `9737556`).
