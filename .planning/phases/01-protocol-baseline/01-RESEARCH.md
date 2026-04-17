# Phase 1: Protocol Baseline - Research

**Researched:** 2026-04-17
**Domain:** MobileWorld cross-framework adapter contract and canonical trajectory protocol
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

No phase CONTEXT.md exists for Phase 1.

### Locked Decisions
- No user-locked decisions captured in CONTEXT.md.

### the agent's Discretion
- Contract naming, module boundaries, and migration sequence are at the agent's discretion.
- Validation gate strictness and rollout compatibility strategy are at the agent's discretion.

### Deferred Ideas (OUT OF SCOPE)
- Framework-specific execution logic for OpenClaw/hermes (planned in later phases).
- KPI enrichment, judge integration, and leaderboard-level reproducibility (later phases).
</user_constraints>

<architectural_responsibility_map>
## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Adapter lifecycle protocol (`initialize/step/finalize/emit_artifacts`) | API/Backend | Browser/Client | Runner orchestration and lifecycle enforcement occur in server/runtime side Python modules. |
| Canonical action/tool/event schema | API/Backend | Database/Storage | Canonical schemas are produced by runtime and persisted as benchmark artifacts. |
| Trajectory writer with schema versioning | API/Backend | Database/Storage | Artifact generation is runtime-owned and must be deterministic/replayable. |
| Runner startup contract validation | API/Backend | Frontend Server | Pre-flight validation belongs in CLI/runner entrypoints before task execution starts. |
| Built-in compatibility regression tests | API/Backend | Frontend Server | Existing CLI/agent path compatibility is verified via Python test suite and runner semantics. |
</architectural_responsibility_map>

<research_summary>
## Summary

Phase 1 should introduce a protocol layer without rewriting existing built-in agent paths. The safest approach is additive: add new adapter/event schemas under a dedicated runtime protocol package, then integrate conversion/validation at runner boundaries while retaining existing `JSONAction`, `BaseAgent`, and task lifecycle semantics.

Current MobileWorld already has useful primitives: `JSONAction` validation in `runtime/utils/models.py`, centralized task loop in `core/runner.py`, and trajectory persistence in `runtime/utils/trajectory_logger.py`. These can be upgraded into canonical protocol outputs by introducing explicit adapter lifecycle interfaces, event normalizers, and versioned trajectory metadata while preserving current `traj.json` behavior for backward compatibility.

External reference patterns in `~/Project/nanobot_fork` reinforce this direction: OpenGUI uses explicit protocol dataclasses (`opengui/interfaces.py`) and Nanobot MCP wrapping includes schema normalization and safe timeout/error behavior (`nanobot/agent/tools/mcp.py`). Phase 1 should mirror this contract-first style with deterministic validation errors and canonical artifact structure.

**Primary recommendation:** Add a new `src/mobile_world/runtime/protocol/` contract layer first, then bridge runner/logger through adapters and canonical event normalization, and only then enforce startup validation gates plus compatibility tests.
</research_summary>

<standard_stack>
## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12 | Runtime and orchestration implementation | Existing project runtime |
| Pydantic | 2.x | Strict protocol model validation | Already used in runtime models, ideal for contract boundaries |
| FastAPI | Existing | Server lifecycle endpoints | Existing server contract surface |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `json`/`jsonlines` style writing | existing | Versioned trajectory artifact persistence | Canonical trace/event output |
| `pytest` | existing | Contract + regression tests | Built-in compatibility and schema gate coverage |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-repo protocol package | External adapter gateway service | Adds infra latency and weakens deterministic local contract checks |
| Pydantic models | Untyped dict payloads | Dicts are faster to prototype but risk silent schema drift |
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Pattern 1: Contract-First Adapter Boundary
**What:** Introduce typed adapter lifecycle interfaces and payload/result models.
**When to use:** Any framework integration that must preserve deterministic benchmark contracts.
**Why for Phase 1:** Enables ADPT-01/02/04 before touching framework-specific implementations.

### Pattern 2: Canonical Event Normalization
**What:** Convert framework/native action/tool outputs into one canonical event schema.
**When to use:** Cross-framework comparability and evaluator portability requirements.
**Why for Phase 1:** Directly addresses ADPT-03 + TRCE-01.

### Pattern 3: Additive Compatibility Rollout
**What:** Keep legacy paths operational while introducing new protocol outputs and checks.
**When to use:** Existing users depend on current CLI/agent behavior.
**Why for Phase 1:** Prevents regressions while introducing strict validation gates.

### Anti-Patterns to Avoid
- Replacing existing runtime flow in one shot; this risks non-deterministic breakage.
- Mixing framework-specific payload shape directly in evaluator/runtime core.
- Failing fast only at runtime step N instead of pre-flight startup validation.
</architecture_patterns>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Plan waves with overlapping file ownership
**What goes wrong:** Parallel plans conflict and produce merge ambiguity.
**How to avoid:** Explicit `files_modified` partitioning and dependency wave separation in PLAN.md.

### Pitfall 2: Canonical schema missing legacy compatibility adapter
**What goes wrong:** Built-in agents fail after protocol changes.
**How to avoid:** Introduce conversion layer from current `JSONAction`/observation objects.

### Pitfall 3: Validation gates that only check presence, not semantics
**What goes wrong:** Invalid adapters pass startup and fail mid-run.
**How to avoid:** Validate required lifecycle methods and schema-level payload/output compatibility before execution.
</common_pitfalls>

<open_questions>
## Open Questions (RESOLVED)

1. Should canonical trajectory become JSONL immediately or dual-write JSON + JSONL for one phase?
   - RESOLVED: Phase 1 uses dual-write (`traj.json` + `traj.canonical.jsonl`/canonical meta) to preserve compatibility; canonical-only output is deferred to a later phase after compatibility validation.

2. Where should adapter registration metadata live (agent registry vs separate adapter registry)?
   - RESOLVED: Adapter registration metadata is owned by `src/mobile_world/runtime/protocol/registry.py`; `src/mobile_world/agents/registry.py` provides a compatibility bridge for existing CLI/agent flows.
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- `src/mobile_world/core/runner.py`
- `src/mobile_world/runtime/client.py`
- `src/mobile_world/runtime/utils/models.py`
- `src/mobile_world/runtime/utils/trajectory_logger.py`
- `src/mobile_world/core/server.py`
- `src/mobile_world/agents/base.py`
- `src/mobile_world/agents/registry.py`

### Secondary (HIGH confidence local reference)
- `~/Project/nanobot_fork/opengui/interfaces.py`
- `~/Project/nanobot_fork/opengui/evaluation.py`
- `~/Project/nanobot_fork/nanobot/agent/tools/mcp.py`
</sources>
