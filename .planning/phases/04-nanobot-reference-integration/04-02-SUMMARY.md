---
phase: 04-nanobot-reference-integration
plan: 02
subsystem: runner-compatibility-shim
tags: [runner, compatibility, framework-profile]
provides:
  - registry-backed `nanobot_opengui` framework profile factory
  - runner support for adapter execution mode (`framework_profile`) with legacy path preserved
  - eval CLI wiring for framework profile and nanobot fork path flags
affects: [phase-4, eval-cli, execution-loop]
tech-stack:
  added: []
  patterns: [side-by-side-execution-mode, non-breaking-cli-extension]
key-files:
  created: []
  modified:
    - src/mobile_world/agents/registry.py
    - src/mobile_world/core/runner.py
    - src/mobile_world/core/subcommands/eval.py
    - src/mobile_world/runtime/utils/trajectory_logger.py
key-decisions:
  - "Keep built-in agent flow as default and gate adapter mode behind explicit profile selection."
requirements-completed: [COMP-01]
duration: 35min
completed: 2026-04-17
---

# Phase 4 Plan 02 Summary

Implemented non-breaking compatibility shim so runner can execute either legacy built-in agents or protocol adapters, with adapter artifact persistence integrated into trajectory outputs.

## Verification
- `rg -n "framework_profile|create_framework_adapter|framework_adapter|log_adapter_artifacts|--framework-profile|--nanobot-fork-path" src/mobile_world/core/runner.py src/mobile_world/agents/registry.py src/mobile_world/core/subcommands/eval.py src/mobile_world/runtime/utils/trajectory_logger.py`
