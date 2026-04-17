---
phase: 07-conformance-artifact-contract-closure
reviewed: 2026-04-17T07:45:20Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - src/mobile_world/runtime/utils/trajectory_logger.py
  - src/mobile_world/core/runner.py
  - tests/protocol/test_canonical_trajectory_contract.py
  - tests/protocol/test_phase2_tool_router_policy.py
  - tests/protocol/test_phase7_conformance_artifact_contract.py
  - .planning/phases/07-conformance-artifact-contract-closure/07-01-SUMMARY.md
  - .planning/phases/07-conformance-artifact-contract-closure/07-02-SUMMARY.md
  - .planning/phases/07-conformance-artifact-contract-closure/07-03-SUMMARY.md
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-04-17T07:45:20Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Phase 07 successfully adds canonical header emission and policy manifest persistence, and all newly scoped protocol tests pass (`10 passed`).  
However, two runtime regressions remain in header lifecycle handling, including one already visible in protocol cross-suite verification (`test_phase3_evaluator_unification::test_logger_persists_evaluator_audit_and_score_evidence`).

## Warnings

### WR-01: Retry reset drops canonical header in subsequent runs

**File:** `src/mobile_world/runtime/utils/trajectory_logger.py:180` and `src/mobile_world/runtime/utils/trajectory_logger.py:614`  
**Issue:** `reset_traj()` rotates files but does not reset `self._canonical_header_emitted`. After a retry/reset path, `_canonical_header_written()` returns `True` from stale in-memory state, so header emission is skipped and canonical JSONL can start with `step` only. This breaks conformance intent for retry flows.  
**Fix:**
```python
def reset_traj(self):
    ...
    self.tools = None
    self._canonical_header_emitted = False
    logger.info(f"Trajectory reset with backup timestamp: {timestamp}")
```
Also add a regression test: log once -> `reset_traj()` -> log again -> assert exactly one `header` exists in the new canonical file.

### WR-02: Header can be inserted after canonical events (ordering regression)

**File:** `src/mobile_world/runtime/utils/trajectory_logger.py:413` and `src/mobile_world/runtime/utils/trajectory_logger.py:461`  
**Issue:** `log_evaluator_audit()` appends a canonical `evaluator_audit` event without ensuring header first. If `log_score()` is called afterward, `_ensure_canonical_header_event()` inserts header between prior events and score. This caused a real regression in protocol tests (`events[-2]` became `header`, not `evaluator_audit`).  
**Fix:**
```python
def log_evaluator_audit(self, audit: dict) -> None:
    task_name = os.path.basename(self.log_file_dir)
    run_id = f"{task_name}-0"
    self._ensure_canonical_header_event(
        task_name=task_name,
        task_goal=self._infer_task_goal_for_header(),
        run_id=run_id,
    )
    ...
```
Apply the same precondition to other canonical-event writers that can run before `log_traj()` (`log_tool_error`, `log_step_metrics`, `log_adapter_artifacts`) to keep ordering deterministic.

## Info

### IN-01: Phase 07 tests miss retry and cross-suite compatibility coverage

**File:** `tests/protocol/test_phase7_conformance_artifact_contract.py:113`  
**Issue:** Added tests validate positive/negative conformance checks but do not cover retry reset behavior or evaluator-audit-before-score ordering, so regressions in WR-01/WR-02 were not caught during Phase 07 verification.  
**Fix:** Add targeted tests for:
1. `TrajLogger.reset_traj()` header behavior after a prior run.
2. `log_evaluator_audit()` + `log_score()` event ordering (header emitted before both).
3. Optional protocol suite guard: assert no existing phase tests regress when header emission logic changes.

---

_Reviewed: 2026-04-17T07:45:20Z_  
_Reviewer: Claude (gsd-code-reviewer)_  
_Depth: standard_
