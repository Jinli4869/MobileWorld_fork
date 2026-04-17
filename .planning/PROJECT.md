# MobileWorld Multi-Framework Evaluation Upgrade

## What This Is

This project upgrades the existing MobileWorld benchmark from a built-in-agent evaluation stack into a framework-agnostic evaluation platform. The goal is to evaluate OpenClaw/nanobot/hermes-style agents under one task/runtime/evaluator standard while preserving MobileWorld's deterministic Android benchmark strengths. The target users are researchers and engineers who need fair, reproducible cross-framework agent evaluation with GUI actions, MCP tools, and evaluator calls.

## Core Value

One benchmark, one task standard, one evaluator contract, multiple agent frameworks with reproducible and comparable results.

## Requirements

### Validated

- ✓ MobileWorld can execute deterministic Android benchmark tasks with task init/teardown and scoring via server APIs (`/task/init`, `/task/eval`, `/task/tear_down`) — existing
- ✓ MobileWorld supports GUI-only, MCP-augmented, and agent-user-interaction task slices via task tags and eval flags — existing
- ✓ MobileWorld already supports multiple built-in agent implementations and allows loading custom agent classes from external `.py` files — existing
- ✓ MobileWorld already captures trajectory logs and per-task scores for benchmark reporting — existing
- ✓ Framework-profile eval flow now uses profile-bound capability policy semantics with deterministic artifact alignment (`policy_manifest.profile_name`) — validated in Phase 8
- ✓ Reproducibility reporting now distinguishes stability pass from agreement availability and enforces agreement thresholds only when judge checks exist — validated in Phase 9

### Active

- [ ] Introduce a framework adapter contract so OpenClaw/nanobot/hermes can run against MobileWorld tasks without rewriting task/evaluator internals.
- [ ] Introduce a unified tool invocation layer that standardizes GUI actions, MCP calls, and ask-user interactions across frameworks.
- [ ] Introduce evaluator contracts that support both rule-based task evaluators and LLM-judge style evaluators (trajectory + screenshot judging).
- [ ] Unify trajectory schema so outputs from built-in agents and external frameworks can be judged and compared consistently.
- [ ] Add first-party adapter reference implementation using nanobot/OpenGUI integration patterns.
- [ ] Add a standardized benchmark KPI system (tokens, TTFT/TTFA/TTS, latency percentiles, tool reliability, cost efficiency, reproducibility, judge agreement) with consistent cross-framework definitions.

### Out of Scope

- Rewriting existing 201 task definitions into a new task language — keep current task assets usable.
- Building a new mobile automation engine from scratch — reuse current Android controller/runtime and proven pathways.
- Solving arbitrary non-mobile benchmarks in this milestone — keep scope to MobileWorld-compatible Android tasks.
- Replacing all existing built-in agents immediately — keep backward compatibility while adapters are introduced.

## Context

MobileWorld currently has strong benchmark fundamentals: reproducible snapshots, task registry, deterministic task scoring, and practical CLI flows (`mw eval`, `mw test`). However, current architecture tightly couples evaluation execution with built-in agent implementations and a fixed MCP setup (DashScope/ModelScope servers configured in code). In parallel, nanobot/OpenGUI practices show a cleaner host-adapter pattern: protocol boundaries, tool registry, MCP dynamic registration, and reusable evaluator modules. This upgrade should absorb those proven patterns into MobileWorld while preserving existing task corpus and environment orchestration.

The current benchmark outputs are still score-centric. For production-quality framework comparison, we also need standardized efficiency/reliability KPIs, including per-step token usage, TTFT/TTFA, end-to-end latency, tool reliability, and cost-per-success metrics.

## Evaluation KPI Pack (v1)

- **Efficiency**: average tokens per step, tokens per success, average steps to success, cost per success
- **Latency**: TTFT, TTFA, TTS, step latency p50/p95, tool latency p50/p95
- **Reliability**: tool success rate, tool retry rate, invalid action rate
- **Stability**: reproducibility variance across repeated runs under fixed config
- **Evaluation quality**: deterministic evaluator vs LLM-judge agreement rate

## Constraints

- **Compatibility**: Existing CLI paths and built-in agents must continue to run — avoid breaking current users.
- **Determinism**: Task init/eval semantics must stay reproducible across frameworks — benchmark comparability depends on this.
- **Runtime boundary**: Keep task/server/runtime ownership inside MobileWorld; external frameworks integrate through adapters, not by bypassing server contracts.
- **MCP safety**: Tool registration and invocation must support allowlisting/timeouts and fail-safe behavior.
- **Evaluator integrity**: Cross-framework comparisons require normalized trajectory artifacts and stable scoring policy.
- **Metric integrity**: KPI definitions must be provider-agnostic and auditable; missing fields need explicit fallback/unknown semantics.
- **Tech stack**: Python 3.12 project with existing FastAPI + uv runtime and Android emulator workflow.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use adapter-first architecture for external frameworks | Decouples benchmark core from specific agent runtime internals | — Pending |
| Keep existing task definitions and server task APIs as canonical benchmark contract | Protects existing benchmark assets and reproducibility guarantees | — Pending |
| Introduce unified tool/evaluator protocol in MobileWorld core | Ensures fair comparison across frameworks and enables extensibility | — Pending |
| Use nanobot/OpenGUI integration as primary reference implementation for v1 adapters | Existing local reference is available and validates architecture choices quickly | — Pending |
| Adopt a standard KPI pack as first-class benchmark output | Score-only comparison is insufficient for real-world framework tradeoff analysis | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

## Current State

- Phase 9 complete: reproducibility agreement gate hardening shipped with explicit availability-aware gate semantics and regression coverage.
- Next focus: milestone closeout and transition planning.

**After each phase transition** (via `$gsd-transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `$gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-17 after Phase 9 completion*
