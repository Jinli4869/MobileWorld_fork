---
phase: 06-reporting-conformance-reproducibility
plan: 02
subsystem: cross-framework-aggregation
tags: [leaderboard, kpi, reporting]
provides:
  - run artifact loader for per-task score/metrics/audit payloads
  - cross-framework aggregation report over common task subsets
  - KPI panels for efficiency, latency, reliability, and evaluator quality
affects: [phase-6, reporting]
tech-stack:
  added: []
  patterns: [artifact-driven-reporting]
key-files:
  created:
    - src/mobile_world/runtime/protocol/reporting.py
  modified:
    - src/mobile_world/runtime/protocol/__init__.py
key-decisions:
  - "Aggregate only on common task intersections to preserve fair cross-framework comparability."
requirements-completed: [METR-04, TRCE-03]
duration: 25min
completed: 2026-04-17
---

# Phase 6 Plan 02 Summary

Added artifact aggregation utilities that build leaderboard-ready framework comparison reports with tokens/cost per success and KPI panels from run roots.

## Verification
- `rg -n "aggregate_framework_runs|tokens_per_success|cost_per_success|kpi_panels|judge_agreement_rate" src/mobile_world/runtime/protocol/reporting.py`
