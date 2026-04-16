---
phase: 06-reporting-conformance-reproducibility
type: research
updated: 2026-04-17
---

# Phase 6 Research

## Objective
Deliver final cross-framework reporting, contract conformance checks, and reproducibility workflows required for trustworthy benchmark comparison.

## Findings

1. Existing runtime already emits the core artifacts needed for aggregation per task run:
   - `traj.canonical.jsonl`
   - `traj.meta.json`
   - `metrics.json`
   - `evaluator_audit.json`
   - `result.txt`
2. There is currently no offline CLI/API utility to:
   - convert historical `traj.json` into canonical schema events
   - aggregate multiple framework runs into one comparable leaderboard/KPI report
   - execute artifact-level conformance checks across adapter/tool/evaluator/metrics contracts
   - evaluate reproducibility variance and judge agreement thresholds across repeated runs
3. Existing protocol validation covers adapter registration and canonical model construction, but not full run artifact bundles.

## Implementation Strategy

1. Add a trace conversion utility that converts legacy `traj.json` to canonical JSONL events with schema/version metadata.
2. Add framework-run aggregation utilities that compute common-task comparison tables and KPI panels (efficiency, latency, reliability, evaluation quality).
3. Add a conformance suite that validates per-task artifact integrity and protocol contract coverage.
4. Add reproducibility analysis utilities for repeated fixed-config runs and expose judge-agreement metrics with threshold gating.
5. Expose all phase capabilities through a dedicated CLI surface so operators can run checks/reports without custom scripts.
