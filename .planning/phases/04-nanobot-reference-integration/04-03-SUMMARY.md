---
phase: 04-nanobot-reference-integration
plan: 03
subsystem: integration-parity-tests
tags: [tests, integration, parity]
provides:
  - phase 4 protocol tests for adapter profile creation and runner adapter mode
  - regression fixture update ensuring reference profiles are restored in isolated tests
  - artifact parity assertions for legacy/canonical/metrics outputs under adapter execution
affects: [phase-4, protocol-tests]
tech-stack:
  added: []
  patterns: [adapter-parity-regression]
key-files:
  created:
    - tests/protocol/test_phase4_nanobot_reference_integration.py
  modified:
    - tests/protocol/conftest.py
    - tests/protocol/test_phase1_protocol_baseline.py
key-decisions:
  - "Validate phase 4 through deterministic protocol tests to avoid emulator/runtime flakiness in CI."
requirements-completed: [INTG-01, COMP-01]
duration: 25min
completed: 2026-04-17
---

# Phase 4 Plan 03 Summary

Added phase 4 test coverage for nanobot profile registration and adapter-mode execution artifact parity, and confirmed compatibility with all prior protocol phases.

## Verification
- `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev python -m pytest -q -s tests/protocol/test_phase1_protocol_baseline.py tests/protocol/test_canonical_trajectory_contract.py tests/protocol/test_phase2_tool_router_policy.py tests/protocol/test_phase3_evaluator_unification.py tests/protocol/test_phase3_1_metrics_kpi.py tests/protocol/test_phase4_nanobot_reference_integration.py`
- Result: `19 passed`
