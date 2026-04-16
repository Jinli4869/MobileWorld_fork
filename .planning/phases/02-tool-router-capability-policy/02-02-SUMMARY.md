---
phase: 02-tool-router-capability-policy
plan: 02
subsystem: capability-policy
tags: [capability-policy, config, deterministic]
provides:
  - policy schema and per-task capability decision resolver
  - eval CLI knobs for policy file and MCP allowlist override
affects: [phase-2, runner, eval-cli]
tech-stack:
  added: []
  patterns: [deterministic-policy-resolution]
key-files:
  created:
    - src/mobile_world/runtime/protocol/capability_policy.py
  modified:
    - src/mobile_world/core/runner.py
    - src/mobile_world/core/subcommands/eval.py
key-decisions:
  - "Policy resolution happens per-task using task tags + profile + explicit flags."
requirements-completed: [TOOL-02]
duration: 25min
completed: 2026-04-17
---

# Phase 2 Plan 02 Summary

Implemented capability policy config schema and resolver, then integrated it into runner and CLI so tool classes are enabled/disabled deterministically for each task run.

## Verification
- `python3 -m compileall src/mobile_world/runtime/protocol src/mobile_world/core`
