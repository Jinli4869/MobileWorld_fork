# Requirements: MobileWorld Multi-Framework Evaluation Upgrade

**Defined:** 2026-04-16
**Core Value:** One benchmark, one task standard, one evaluator contract, multiple agent frameworks with reproducible and comparable results.

## v1 Requirements

### Adapter Contracts

- [x] **ADPT-01**: Framework adapter can be registered by name/profile and discovered by the eval runner.
- [x] **ADPT-02**: Adapter lifecycle includes standardized `initialize`, `step`, `finalize`, and `emit_artifacts` behavior.
- [x] **ADPT-03**: Adapter outputs canonical action/tool events instead of framework-native opaque payloads.
- [x] **ADPT-04**: Adapter contract validation reports actionable schema errors before benchmark execution starts.

### Tool Routing & Capability Policy

- [x] **TOOL-01**: Runner dispatches GUI actions, MCP calls, and ask-user events via one unified tool router.
- [ ] **TOOL-02**: Task/tag/profile capability policy can enable/disable tool classes deterministically per run.
- [x] **TOOL-03**: MCP tool registration supports allowlist and timeout controls captured in run metadata.
- [x] **TOOL-04**: Tool execution errors are normalized into comparable failure events across frameworks.

### Evaluator Contracts

- [x] **EVAL-01**: Benchmark scoring uses a centralized evaluator interface independent of framework adapter internals.
- [x] **EVAL-02**: Existing task-native deterministic scoring remains supported as primary evaluator signal.
- [x] **EVAL-03**: Optional trajectory judge (LLM-based) can be enabled with explicit model/config recording.
- [x] **EVAL-04**: Evaluator outputs include score, reason, and evidence references for auditability.

### Metrics & Telemetry

- [x] **METR-01**: System records per-step token usage (`prompt`, `completion`, `cached`, `total`) and reports average tokens per step per task/run.
- [x] **METR-02**: System records TTFT at model turn level and aggregates task/run TTFT with explicit handling for providers that do not expose native TTFT.
- [x] **METR-03**: System records TTFA, TTS, step latency p50/p95, and tool latency p50/p95 for all frameworks.
- [x] **METR-04**: System reports efficiency/cost metrics including tokens per success and cost per success.
- [x] **METR-05**: System reports reliability metrics including tool success rate, tool retry rate, and invalid action rate.
- [ ] **METR-06**: System reports stability metrics including reproducibility variance across repeated fixed-config runs.
- [ ] **METR-07**: System reports evaluator quality metrics including deterministic evaluator vs LLM-judge agreement rate.

### Trajectory & Artifacts

- [ ] **TRCE-01**: All runs persist a canonical versioned trajectory schema regardless of framework source.
- [x] **TRCE-02**: Historical trajectory formats can be converted or wrapped into the canonical schema.
- [x] **TRCE-03**: Aggregated reports can compare multiple frameworks on identical task subsets and settings.

### Integration & CLI Workflows

- [x] **INTG-01**: Nanobot/OpenGUI reference adapter can execute MobileWorld tasks end-to-end.
- [x] **INTG-02**: OpenClaw and hermes adapter scaffolds are provided with implementation guide and examples.
- [ ] **INTG-03**: CLI can run eval by framework profile and emit comparable result artifacts.
- [x] **INTG-04**: CLI can list registered frameworks, supported capabilities, and conformance status.

### Compatibility & QA

- [x] **COMP-01**: Existing built-in agent eval/test workflows remain functional without adapter migration.
- [ ] **COMP-02**: Conformance test suite validates adapter contract, tool routing, and evaluator output shape.
- [ ] **COMP-03**: Regression tests ensure benchmark reproducibility between repeated runs under same config.

## v2 Requirements

### Ecosystem Expansion

- **ECOS-01**: Public adapter SDK template for third-party framework contributors.
- **ECOS-02**: Remote non-Python adapter gateway support.
- **ECOS-03**: Public submission API for leaderboard ingestion and verification.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Rebuilding all existing tasks into a new task DSL | High migration cost and unnecessary for this milestone |
| Replacing current Android runtime/controller stack | Not required to unlock multi-framework evaluation |
| Benchmarking non-mobile domains in same milestone | Would dilute delivery focus and comparability quality |
| Framework-specific private scoring rules in leaderboard | Violates cross-framework fairness |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ADPT-01 | Phase 1 | Completed |
| ADPT-02 | Phase 1 | Completed |
| ADPT-03 | Phase 1 | Completed |
| ADPT-04 | Phase 1 | Completed |
| TRCE-01 | Phase 7 | Pending |
| TOOL-01 | Phase 2 | Completed |
| TOOL-02 | Phase 8 | Pending |
| TOOL-03 | Phase 2 | Completed |
| TOOL-04 | Phase 2 | Completed |
| EVAL-01 | Phase 3 | Completed |
| EVAL-02 | Phase 3 | Completed |
| EVAL-03 | Phase 3 | Completed |
| EVAL-04 | Phase 3 | Completed |
| METR-01 | Phase 3.1 | Completed |
| METR-02 | Phase 3.1 | Completed |
| METR-03 | Phase 3.1 | Completed |
| METR-05 | Phase 3.1 | Completed |
| INTG-01 | Phase 4 | Complete |
| COMP-01 | Phase 4 | Complete |
| INTG-02 | Phase 5 | Complete |
| INTG-03 | Phase 8 | Pending |
| INTG-04 | Phase 5 | Complete |
| METR-04 | Phase 6 | Complete |
| METR-06 | Phase 9 | Pending |
| METR-07 | Phase 9 | Pending |
| TRCE-02 | Phase 6 | Complete |
| TRCE-03 | Phase 6 | Complete |
| COMP-02 | Phase 7 | Pending |
| COMP-03 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 29 total
- Checked-off: 22
- Pending rework from milestone gaps: 7
- Mapped to phases: 29
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-16*
*Last updated: 2026-04-17 after milestone gap-closure phases 7-9 were added*
