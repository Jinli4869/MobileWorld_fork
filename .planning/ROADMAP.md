# Roadmap: MobileWorld Multi-Framework Evaluation Upgrade

## Overview

This roadmap upgrades MobileWorld from built-in-agent evaluation to a protocol-driven benchmark platform for OpenClaw/nanobot/hermes-style frameworks. The execution order prioritizes contract correctness, deterministic tool/evaluator behavior, standardized benchmark metrics (tokens/TTFT/latency/cost/reliability), real adapter validation, and final comparability hardening.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Protocol Baseline** - Define adapter, action/tool, and trajectory contracts
- [ ] **Phase 2: Tool Router & Capability Policy** - Unify GUI/MCP/ask-user routing with deterministic controls
- [ ] **Phase 3: Evaluator Unification** - Centralize scoring and optional trajectory judge integration
- [ ] **Phase 3.1: Metrics Instrumentation & KPI Contracts (INSERTED)** - Add token/latency/cost/reliability KPI capture and definitions
- [ ] **Phase 4: Nanobot Reference Integration** - Validate architecture with nanobot/OpenGUI adapter
- [ ] **Phase 5: Framework Expansion & CLI Profiles** - Add OpenClaw/hermes scaffolds and framework-oriented commands
- [ ] **Phase 6: Reporting, Conformance & Reproducibility** - Finalize cross-framework comparison and QA guarantees

## Phase Details

### Phase 1: Protocol Baseline
**Goal**: Establish stable cross-framework protocol contracts before integration.
**Depends on**: Nothing (first phase)
**Requirements**: ADPT-01, ADPT-02, ADPT-03, ADPT-04, TRCE-01
**Success Criteria** (what must be TRUE):
1. Adapter lifecycle contract is implemented and validated by schema checks.
2. Canonical action/tool event schema can represent existing built-in agent runs.
3. Canonical trajectory writer produces versioned artifacts for all runs.
4. Existing built-in eval flow remains runnable after contract introduction.
**Plans**: 4 plans

Plans:
- [x] 01-01: Define adapter protocol models and base interfaces
- [x] 01-02: Define canonical action/tool/trace event schemas
- [x] 01-03: Integrate protocol validation gates into runner startup
- [x] 01-04: Add baseline regression tests for built-in agent compatibility

### Phase 2: Tool Router & Capability Policy
**Goal**: Enforce consistent and deterministic tool behavior across frameworks.
**Depends on**: Phase 1
**Requirements**: TOOL-01, TOOL-02, TOOL-03, TOOL-04
**Success Criteria** (what must be TRUE):
1. All framework calls route through one tool dispatch path.
2. Task/tag/profile capability policy can reproduce identical tool availability per run.
3. MCP tool manifest (enabled tools, timeout, source) is persisted in artifacts.
4. Tool errors are normalized and comparable in trajectory data.
**Plans**: 4 plans

Plans:
- [ ] 02-01: Implement unified tool router and dispatch hooks
- [ ] 02-02: Implement capability policy engine and config schema
- [ ] 02-03: Refactor MCP registration to config-driven allowlist model
- [ ] 02-04: Add error normalization and deterministic tool manifest logging

### Phase 3: Evaluator Unification
**Goal**: Make scoring framework-agnostic and auditable.
**Depends on**: Phase 2
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04
**Success Criteria** (what must be TRUE):
1. One evaluator interface is used regardless of framework adapter.
2. Existing deterministic task scoring is preserved as primary signal.
3. Optional trajectory judge can be enabled without changing final artifact schema.
4. Every score has machine-readable reason and evidence references.
**Plans**: 4 plans

Plans:
- [ ] 03-01: Define evaluator protocol and evaluator registry
- [ ] 03-02: Bridge existing task-native scoring into evaluator interface
- [ ] 03-03: Integrate trajectory judge backend with explicit config recording
- [ ] 03-04: Add evaluator audit output and score consistency checks

### Phase 3.1: Metrics Instrumentation & KPI Contracts (INSERTED)
**Goal**: Make benchmark efficiency, latency, cost, and reliability metrics first-class and comparable.
**Depends on**: Phase 3
**Requirements**: METR-01, METR-02, METR-03, METR-05
**Success Criteria** (what must be TRUE):
1. Per-step token accounting is captured and queryable for built-in and adapter runs.
2. TTFT, TTFA, TTS, step latency p50/p95, and tool latency p50/p95 are emitted in standardized run artifacts.
3. Tool success rate, tool retry rate, and invalid action rate are computed per task/profile/run.
4. Metrics quality flags explicitly mark native vs estimated vs unavailable fields.
**Plans**: 4 plans

Plans:
- [ ] 03.1-01: Add canonical metrics event schema and telemetry hooks
- [ ] 03.1-02: Add token/TTFT collection adapters with provider fallback policy
- [ ] 03.1-03: Add latency/reliability aggregators and per-run KPI summaries
- [ ] 03.1-04: Add KPI validation tests and metrics quality flagging

### Phase 4: Nanobot Reference Integration
**Goal**: Prove adapter architecture end-to-end with nanobot/OpenGUI.
**Depends on**: Phase 3.1
**Requirements**: INTG-01, COMP-01
**Success Criteria** (what must be TRUE):
1. Nanobot/OpenGUI adapter can run selected MobileWorld tasks end-to-end.
2. Legacy built-in agents still run unchanged via existing CLI pathways.
3. Adapter run artifacts and built-in run artifacts are structurally comparable, including KPI fields.
**Plans**: 3 plans

Plans:
- [ ] 04-01: Implement nanobot/OpenGUI adapter using protocol boundaries
- [ ] 04-02: Add compatibility shim for existing built-in agent runner path
- [ ] 04-03: Run side-by-side pilot benchmark and validate artifact parity

### Phase 5: Framework Expansion & CLI Profiles
**Goal**: Enable broader framework onboarding and practical operator workflows.
**Depends on**: Phase 4
**Requirements**: INTG-02, INTG-03, INTG-04
**Success Criteria** (what must be TRUE):
1. OpenClaw/hermes adapter scaffolds with clear contracts are available.
2. CLI can run benchmark by framework profile with consistent option semantics.
3. CLI can display framework registration, capability, and conformance status.
**Plans**: 3 plans

Plans:
- [ ] 05-01: Add OpenClaw/hermes adapter templates and docs
- [ ] 05-02: Add framework-profile eval CLI commands and config loading
- [ ] 05-03: Add framework inventory and conformance status reporting commands

### Phase 6: Reporting, Conformance & Reproducibility
**Goal**: Finalize trustworthy cross-framework comparison outputs.
**Depends on**: Phase 5
**Requirements**: METR-04, METR-06, METR-07, TRCE-02, TRCE-03, COMP-02, COMP-03
**Success Criteria** (what must be TRUE):
1. Historical and new traces can be converted/aggregated under canonical schema.
2. Cross-framework result reports are generated for identical task sets, including token/cost/latency/reliability KPI panels.
3. Conformance suite validates adapter/tool/evaluator/metrics contract integrity.
4. Repeated runs under identical config satisfy reproducibility thresholds, and judge agreement metrics are reported.
**Plans**: 4 plans

Plans:
- [ ] 06-01: Implement trace schema versioning and converter utilities
- [ ] 06-02: Implement cross-framework aggregation and KPI-enriched leaderboard report output
- [ ] 06-03: Build adapter conformance CLI and test suite (including metrics conformance)
- [ ] 06-04: Add reproducibility/judge-agreement workflow and thresholds

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 3.1 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Protocol Baseline | 4/4 | Completed | 2026-04-17 |
| 2. Tool Router & Capability Policy | 0/4 | Not started | - |
| 3. Evaluator Unification | 0/4 | Not started | - |
| 3.1. Metrics Instrumentation & KPI Contracts | 0/4 | Not started | - |
| 4. Nanobot Reference Integration | 0/3 | Not started | - |
| 5. Framework Expansion & CLI Profiles | 0/3 | Not started | - |
| 6. Reporting, Conformance & Reproducibility | 0/4 | Not started | - |
