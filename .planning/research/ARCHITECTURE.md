# Architecture Research

**Domain:** Multi-framework mobile benchmark architecture
**Researched:** 2026-04-16
**Confidence:** HIGH

## Standard Architecture

### System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                     Framework Layer                          │
├─────────────────────────────────────────────────────────────┤
│ OpenClaw Adapter │ nanobot Adapter │ hermes Adapter │ Built-in │
└───────────────┬───────────────────────────────┬──────────────┘
                │ Unified Adapter Contract      │
┌───────────────┴───────────────────────────────┴──────────────┐
│                 MobileWorld Orchestration Core                │
├─────────────────────────────────────────────────────────────┤
│ Eval Runner │ Tool Router │ Capability Policy │ Trajectory IO │
└───────────────┬───────────────────────────────┬──────────────┘
                │                                │
┌───────────────┴──────────────┐  ┌──────────────┴──────────────┐
│ Runtime / Task Server         │  │ Evaluator Layer             │
├───────────────────────────────┤  ├─────────────────────────────┤
│ /task/init /step /task/eval   │  │ Rule Evaluator + LLM Judge  │
│ Android Controller + AVD       │  │ Score normalizer + reports  │
└───────────────────────────────┘  └─────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Adapter Contract | Normalize framework loop into benchmark loop | Typed protocol + adapter base class |
| Tool Router | Route action/tool calls to GUI/MCP/ask-user handlers | Action enum + capability checks + audit logs |
| Capability Policy | Restrict per-task/per-tag tool access | Task metadata tags + config policies |
| Trajectory IO | Persist canonical event stream | JSONL writer with versioned schema |
| Evaluator Contract | Judge outcome from task and trace evidence | Rule-based evaluator + optional vision LLM judge |

## Recommended Project Structure

```text
src/mobile_world/
├── adapters/                    # Framework adapters
│   ├── base.py                  # Adapter protocol / abstract base
│   ├── registry.py              # Adapter discovery + registration
│   └── implementations/         # nanobot/openclaw/hermes adapters
├── orchestration/
│   ├── tool_router.py           # Unified tool dispatch
│   ├── capability_policy.py     # Task-aware tool permissions
│   └── execution_loop.py        # Framework-agnostic eval loop
├── protocols/
│   ├── events.py                # Canonical action/tool/trace events
│   ├── evaluator.py             # Evaluator interface contracts
│   └── schemas.py               # Versioned pydantic models
├── evaluators/
│   ├── builtin.py               # Existing task scoring bridge
│   ├── trajectory_judge.py      # LLM judge bridge
│   └── aggregator.py            # Cross-framework reporting
└── runtime/                     # Existing controller/server/client
```

### Structure Rationale

- **`adapters/`** isolates framework-specific code and prevents core orchestration coupling.
- **`protocols/`** centralizes benchmark contracts so runner/evaluator/adapter evolve consistently.
- **`orchestration/`** separates execution policy from runtime mechanics.
- **`evaluators/`** allows dual-mode scoring while maintaining a single score output path.

## Architectural Patterns

### Pattern 1: Adapter Boundary

**What:** Each framework implements the same lifecycle contract and emits standardized events.
**When to use:** Always for external framework integration.
**Trade-offs:** Slight upfront boilerplate, major long-term maintenance win.

### Pattern 2: Capability-Gated Tool Routing

**What:** Tool calls pass through policy before dispatch to runtime/MCP/user-sim channels.
**When to use:** Any task using MCP or user interaction.
**Trade-offs:** More plumbing, but avoids unfair or unsafe tool usage.

### Pattern 3: Evaluator Composition

**What:** Final score merges task-native result and optional trajectory judge diagnostics.
**When to use:** Cross-framework runs where native score is insufficient.
**Trade-offs:** More evaluator complexity, significantly better observability.

## Data Flow

### Request Flow

```text
CLI eval request
 -> Orchestrator builds run profile
 -> Adapter step loop (framework)
 -> Tool Router (GUI/MCP/ask-user)
 -> Runtime server executes /step
 -> Canonical trajectory event written
 -> Evaluator consumes task state + trajectory
 -> Aggregated report output
```

### Key Data Flows

1. **Adapter -> Tool Router:** framework actions normalized to canonical event/action schema.
2. **Tool Router -> Runtime/MCP/UserSim:** policy-gated execution with result normalization.
3. **Trajectory -> Evaluator:** shared evidence for both deterministic scoring and optional LLM judge.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Single framework dev runs | Local adapters + direct JSONL logging |
| Multi-framework benchmark batches | Per-run profile isolation + stronger cache/retry controls |
| Public leaderboard-scale | Artifact versioning, evaluator drift checks, reproducibility manifests |

## Anti-Patterns

### Anti-Pattern 1: Adapter bypasses core tool routing

**What people do:** Call runtime/MCP directly from framework wrapper.
**Why it's wrong:** Breaks policy enforcement and trace consistency.
**Do this instead:** Force all tool paths through unified router.

### Anti-Pattern 2: Evaluator embedded inside framework adapter

**What people do:** Each adapter computes its own success.
**Why it's wrong:** Scores stop being comparable.
**Do this instead:** Adapter reports evidence; MobileWorld evaluator owns final scoring.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| MCP servers | Config-driven registry and wrapped tools | Must support allowlist + timeout + error normalization |
| LLM judge provider | OpenAI-compatible judge client | Keep deterministic fallback when judge unavailable |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Adapter <-> Orchestrator | Typed protocol calls | No direct runtime bypass |
| Orchestrator <-> Runtime server | Existing REST APIs | Preserve current `/task/*` contract |
| Orchestrator <-> Evaluator | Canonical events + task handles | Enables consistent scoring and debugging |

## Sources

- MobileWorld runtime and core server structure
- nanobot/OpenGUI adapter and protocol designs

---
*Architecture research for: MobileWorld multi-framework evaluation upgrade*
*Researched: 2026-04-16*
