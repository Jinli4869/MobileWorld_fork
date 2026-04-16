# Project Research Summary

**Project:** MobileWorld Multi-Framework Evaluation Upgrade
**Domain:** Mobile benchmark orchestration for heterogeneous agent frameworks
**Researched:** 2026-04-16
**Confidence:** HIGH

## Executive Summary

MobileWorld already has a solid deterministic benchmark core (task lifecycle APIs, environment reproducibility, scoring flow), but it is still oriented around built-in agent implementations and a fixed MCP setup. Your goal requires turning this into a framework-agnostic benchmark platform that can fairly evaluate OpenClaw, nanobot, hermes, and future agent runtimes under one contract.

The recommended direction is adapter-first architecture: keep MobileWorld server/task/evaluator ownership as benchmark core, and place each framework behind a strict adapter protocol. Then add unified tool routing (GUI/MCP/ask-user), canonical trajectory schema, and centralized evaluator contracts. This preserves benchmark credibility while enabling rapid framework onboarding.

The largest risks are semantic drift (same task interpreted differently), uncontrolled MCP exposure, and evaluator inconsistency. All three are mitigated by contract-first protocol design, capability policy manifests, and centralized scoring logic.

## Key Findings

### Recommended Stack

Build on current Python/FastAPI/Pydantic foundation and extend with protocol modules plus adapter/evaluator packages. Reuse existing `mcp` ecosystem but shift from hard-coded server list to config-driven registration and policy-scoped enablement.

**Core technologies:**
- Python 3.12 + FastAPI/Uvicorn: keep runtime stable
- Pydantic contracts: enforce adapter/tool/evaluator schema consistency
- MCP wrappers: dynamic tool registration with allowlist and timeout controls

### Expected Features

**Must have (table stakes):**
- Framework adapter registration and execution contract
- Unified tool invocation model
- Canonical trajectory schema
- Central evaluator contract

**Should have (competitive):**
- Conformance test suite for third-party adapters
- Cross-framework score consistency diagnostics

**Defer (v2+):**
- Non-Python adapter gateway and public submission APIs

### Architecture Approach

Use layered architecture: framework adapters -> orchestration core -> runtime/task server + evaluator layer. Keep existing task APIs canonical and forbid adapter bypasses. Persist all execution evidence as versioned canonical events.

**Major components:**
1. Adapter protocol and registry
2. Tool router + capability policy
3. Canonical trajectory/event schema
4. Evaluator interfaces (rule-based + LLM judge)
5. Aggregated reporting/leaderboard exporter

### Critical Pitfalls

1. **Semantic drift across frameworks** — solve with strict protocol and conformance tests.
2. **MCP drift/uncontrolled tool surface** — solve with task-scoped capability policy.
3. **Evaluator inconsistency** — solve with centralized scoring ownership.
4. **Backward compatibility regressions** — solve with incremental migration preserving legacy path.

## Implications for Roadmap

### Phase 1: Protocol Baseline
**Rationale:** No safe multi-framework expansion without explicit contracts.
**Delivers:** Adapter interfaces + canonical action/tool/trajectory event models.
**Addresses:** semantic parity foundation.

### Phase 2: Tool Routing & MCP Policy
**Rationale:** Tool equivalence must be enforced before adapter expansion.
**Delivers:** Unified tool router and capability manifests.
**Implements:** policy-gated GUI/MCP/ask-user dispatch.

### Phase 3: Evaluator Unification
**Rationale:** Comparable results need one scoring authority.
**Delivers:** Evaluator interface, rule-judge bridge, optional trajectory judge integration.

### Phase 4: Reference Adapter & Migration
**Rationale:** Need one real external framework to validate design.
**Delivers:** nanobot/OpenGUI reference adapter + compatibility shims for legacy runner path.

### Phase 5: Cross-Framework Reporting & QA
**Rationale:** Benchmark value is in trusted comparison outputs.
**Delivers:** trace schema versioning, aggregation reports, conformance CLI/tests.

### Phase Ordering Rationale

- Contract first, then execution policies, then scoring, then integration, then reporting hardening.
- This ordering minimizes rework and prevents premature framework-specific branching.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** MCP transport edge cases and timeout behavior across providers.
- **Phase 3:** Judge consistency and calibration policy.
- **Phase 4:** Nanobot/OpenGUI adapter ergonomics and model/tool-call profile handling.

Phases with standard patterns (skip heavy research-phase):
- **Phase 1:** protocol modeling and adapter interface extraction from existing code.
- **Phase 5:** reporting and schema versioning patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Strong alignment with existing repo runtime |
| Features | HIGH | Directly grounded in user goal + codebase constraints |
| Architecture | HIGH | Existing reference pattern available in nanobot/OpenGUI |
| Pitfalls | HIGH | Risks visible in current coupling and benchmark requirements |

**Overall confidence:** HIGH

### Gaps to Address

- Exact adapter surface for hermes/OpenClaw variants may need minor profile extensions.
- Need explicit policy for handling evaluator disagreements between deterministic checks and LLM judge.

## Sources

### Primary (HIGH confidence)
- MobileWorld source and docs in current workspace
- nanobot/OpenGUI local reference repository (`~/Documents/Personal/nanobot_fork`)

---
*Research completed: 2026-04-16*
*Ready for roadmap: yes*
