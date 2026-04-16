---
phase: 06-reporting-conformance-reproducibility
plan: 01
subsystem: trace-schema-converter
tags: [trace, schema, conversion]
provides:
  - legacy `traj.json` to canonical JSONL conversion utility
  - conversion metadata fields for source/target schema version traceability
affects: [phase-6, trajectory-compatibility]
tech-stack:
  added: []
  patterns: [schema-versioned-conversion]
key-files:
  created:
    - src/mobile_world/runtime/protocol/trace_converter.py
  modified:
    - src/mobile_world/runtime/protocol/__init__.py
key-decisions:
  - "Treat legacy conversion as best-effort artifact migration with explicit converter/source schema metadata in canonical header."
requirements-completed: [TRCE-02]
duration: 20min
completed: 2026-04-17
---

# Phase 6 Plan 01 Summary

Implemented legacy trajectory conversion utilities with `convert_legacy_trajectory` and `convert_legacy_directory`, emitting canonical header/step/score/metrics events and versioned conversion metadata.

## Verification
- `rg -n "convert_legacy_trajectory|convert_legacy_directory|LEGACY_TRAJECTORY_SCHEMA_VERSION|TRACE_CONVERTER_VERSION" src/mobile_world/runtime/protocol/trace_converter.py src/mobile_world/runtime/protocol/__init__.py`
