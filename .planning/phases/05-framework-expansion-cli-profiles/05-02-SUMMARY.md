---
phase: 05-framework-expansion-cli-profiles
plan: 02
subsystem: framework-profile-eval-config
tags: [eval-cli, config, framework-profile]
provides:
  - `--framework-config` JSON loader for eval CLI
  - normalized framework profile option mapping to runner adapter mode
  - regression coverage for parser/config behavior
affects: [phase-5, eval-cli]
tech-stack:
  added: []
  patterns: [config-driven-execution]
key-files:
  created: []
  modified:
    - src/mobile_world/core/subcommands/eval.py
    - tests/protocol/test_phase5_framework_profiles.py
key-decisions:
  - "Framework config JSON may override framework/judge fields so execution remains reproducible and file-driven."
requirements-completed: [INTG-03]
duration: 20min
completed: 2026-04-17
---

# Phase 5 Plan 02 Summary

Extended eval CLI with `--framework-config` and framework option resolution logic, enabling reproducible profile-based runs without changing existing direct-flag behavior.

## Verification
- `rg -n "load_framework_config|framework_config|framework_profile|nanobot_fork_path" src/mobile_world/core/subcommands/eval.py tests/protocol/test_phase5_framework_profiles.py`
