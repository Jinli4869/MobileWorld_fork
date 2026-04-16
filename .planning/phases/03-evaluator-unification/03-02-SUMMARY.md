---
phase: 03-evaluator-unification
plan: 02
subsystem: runner-evaluator-bridge
tags: [runner, evaluator, deterministic-score]
provides:
  - runner scoring path routed through evaluator abstraction
  - deterministic task-native scoring preserved as primary signal
  - evaluator audit persisted into legacy and canonical trajectory artifacts
affects: [phase-3, runner-loop, trajectory-logging]
tech-stack:
  added: []
  patterns: [primary-signal-preservation, auditable-scoring]
key-files:
  created: []
  modified:
    - src/mobile_world/core/runner.py
    - src/mobile_world/runtime/utils/trajectory_logger.py
key-decisions:
  - "Keep score output deterministic and use judge only as supplemental audit signal."
requirements-completed: [EVAL-02]
duration: 25min
completed: 2026-04-17
---

# Phase 3 Plan 02 Summary

Replaced direct `env.get_task_score` usage in runner with evaluator-driven scoring, and added evaluator audit persistence (`log_evaluator_audit`) to trajectory artifacts.

## Verification
- `rg -n "create_evaluator|EvaluatorInput|log_evaluator_audit" src/mobile_world/core/runner.py src/mobile_world/runtime/utils/trajectory_logger.py`
