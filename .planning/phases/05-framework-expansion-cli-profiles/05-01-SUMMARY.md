---
phase: 05-framework-expansion-cli-profiles
plan: 01
subsystem: framework-scaffold-adapters
tags: [openclaw, hermes, templates]
provides:
  - OpenClaw/Hermes scaffold adapters conforming to FrameworkAdapter
  - profile registration for template adapters in registry
  - onboarding documentation for framework adapter profiles
affects: [phase-5, adapter-onboarding]
tech-stack:
  added: []
  patterns: [scaffold-first-integration]
key-files:
  created:
    - src/mobile_world/runtime/adapters/openclaw_template.py
    - src/mobile_world/runtime/adapters/hermes_template.py
    - docs/framework_adapters.md
  modified:
    - src/mobile_world/runtime/adapters/__init__.py
    - src/mobile_world/agents/registry.py
key-decisions:
  - "Ship template adapters as safe no-op fallbacks (`wait`) to unblock onboarding before full framework runtime wiring."
requirements-completed: [INTG-02]
duration: 25min
completed: 2026-04-17
---

# Phase 5 Plan 01 Summary

Added OpenClaw/Hermes scaffold adapters and registered them as framework profiles (`openclaw_template`, `hermes_template`), with documentation for operator usage and implementation TODOs.

## Verification
- `rg -n "OpenClawTemplateAdapter|HermesTemplateAdapter|openclaw_template|hermes_template|framework_adapters" src/mobile_world/runtime/adapters src/mobile_world/agents/registry.py docs/framework_adapters.md`
