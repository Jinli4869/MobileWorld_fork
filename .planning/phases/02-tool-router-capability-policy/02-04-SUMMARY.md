---
phase: 02-tool-router-capability-policy
plan: 04
subsystem: normalized-tool-errors
tags: [error-normalization, tests, trajectory]
provides:
  - normalized tool failure codes and payloads
  - persisted tool error events in canonical trajectory output
  - phase2 regression tests for policy/router/manifest/error behavior
affects: [phase-2, test-suite]
tech-stack:
  added: []
  patterns: [comparable-error-envelopes]
key-files:
  created:
    - tests/protocol/test_phase2_tool_router_policy.py
  modified:
    - src/mobile_world/runtime/protocol/tool_router.py
    - src/mobile_world/runtime/utils/trajectory_logger.py
key-decisions:
  - "Use stable error codes: CAPABILITY_DENIED, MCP_TOOL_NOT_ALLOWLISTED, TOOL_EXECUTION_ERROR."
requirements-completed: [TOOL-04]
duration: 20min
completed: 2026-04-17
---

# Phase 2 Plan 04 Summary

Completed normalized tool-error integration and added protocol tests validating capability decisions, router denials, error normalization, and manifest logging.

## Verification
- `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q -s tests/protocol/test_phase1_protocol_baseline.py tests/protocol/test_canonical_trajectory_contract.py tests/protocol/test_phase2_tool_router_policy.py`
- Result: `11 passed`
