---
phase: 03-evaluator-unification
plan: 03
subsystem: trajectory-judge-integration
tags: [judge, evaluator, cli]
provides:
  - optional trajectory judge backend integrated in evaluator pipeline
  - explicit judge model/api config recorded in evaluator audit
  - eval CLI flags and runner plumbing for judge configuration
affects: [phase-3, eval-cli, runner-loop]
tech-stack:
  added: []
  patterns: [optional-auxiliary-judge, explicit-config-recording]
key-files:
  created: []
  modified:
    - src/mobile_world/runtime/protocol/evaluator.py
    - src/mobile_world/core/subcommands/eval.py
    - src/mobile_world/core/runner.py
key-decisions:
  - "Judge verdict never overrides deterministic score; it only contributes audit evidence and consistency checks."
requirements-completed: [EVAL-03]
duration: 20min
completed: 2026-04-17
---

# Phase 3 Plan 03 Summary

Integrated `enable_trajectory_judge` flow end-to-end from CLI to runner to evaluator, and persisted judge config details (`judge_model`, `judge_api_base`, key-presence flag) in audit payloads.

## Verification
- `rg -n "enable_trajectory_judge|judge_model|judge_api_key|judge_api_base|TrajectoryJudge" src/mobile_world/core/subcommands/eval.py src/mobile_world/core/runner.py src/mobile_world/runtime/protocol/evaluator.py`
