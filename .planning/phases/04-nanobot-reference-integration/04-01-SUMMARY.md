---
phase: 04-nanobot-reference-integration
plan: 01
subsystem: nanobot-reference-adapter
tags: [nanobot, opengui, adapter]
provides:
  - `NanobotOpenGUIAdapter` implementing FrameworkAdapter lifecycle
  - optional OpenGUI evaluator hook via dynamic import from `nanobot_fork`
  - safe fallback behavior when OpenGUI dependencies are unavailable
affects: [phase-4, adapter-layer]
tech-stack:
  added: []
  patterns: [optional-dependency-gate, adapter-reference-implementation]
key-files:
  created:
    - src/mobile_world/runtime/adapters/nanobot_opengui.py
    - src/mobile_world/runtime/adapters/__init__.py
  modified:
    - src/mobile_world/runtime/protocol/adapter.py
    - src/mobile_world/runtime/protocol/__init__.py
key-decisions:
  - "Treat OpenGUI evaluator as optional sidecar capability so benchmark core remains runnable without external dependency installation."
requirements-completed: [INTG-01]
duration: 30min
completed: 2026-04-17
---

# Phase 4 Plan 01 Summary

Added nanobot/OpenGUI reference adapter with dynamic optional evaluator loading and explicit fallback mode. Also added protocol-level `is_terminal_action` helper used across adapters.

## Verification
- `rg -n "class NanobotOpenGUIAdapter|_load_opengui_eval_function|is_terminal_action|TERMINAL_ACTION_TYPES" src/mobile_world/runtime/adapters/nanobot_opengui.py src/mobile_world/runtime/protocol/adapter.py`
