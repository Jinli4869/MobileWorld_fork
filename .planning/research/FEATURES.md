# Feature Research

**Domain:** Multi-framework mobile agent benchmark orchestration
**Researched:** 2026-04-16
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Framework adapter registration | Benchmark users run many agent stacks | MEDIUM | Must support built-in + external adapters uniformly |
| Unified action/tool contract | Fair comparison needs identical semantics | HIGH | GUI/MCP/ask-user must share one contract |
| Deterministic task lifecycle | Benchmark credibility requires reproducibility | HIGH | Keep `/task/init/eval/tear_down` as canonical flow |
| Unified trajectory artifacts | Evaluator and analytics depend on consistent traces | HIGH | Need strict schema + converter hooks |
| Evaluator pluggability | Different tasks need different judging modes | MEDIUM | Rule-based and LLM-judge should coexist |
| Batch benchmark reporting | Users need leaderboards not only raw logs | MEDIUM | Cross-framework aggregate outputs required |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Multi-framework parity harness | Apples-to-apples comparison across frameworks | HIGH | Must control prompt/tool/evaluator confounders |
| MCP capability profiles per task | Realistic hybrid-tool evaluation beyond GUI-only | MEDIUM | Dynamic allowlisting per task/app/tag |
| Adapter conformance test suite | Faster onboarding of new frameworks | MEDIUM | Self-serve validation for adapter authors |
| Cross-framework evaluator consistency checks | Detect judge drift and unfairness early | HIGH | Required for trustworthy public leaderboard |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Let each framework define its own success metric | Easier integration | Destroys comparability | Keep framework-specific metrics as auxiliary only |
| Unlimited tool exposure to agents | More flexibility | Security/reproducibility risk and benchmark noise | Task-scoped tool capability policy |
| One-off custom runner per framework | Fast short-term demos | Maintenance explosion | Standard adapter interface + profile config |

## Feature Dependencies

```text
Framework Adapter Contract
    -> Unified Action/Tool Contract
        -> Unified Trajectory Schema
            -> Evaluator Contract + Leaderboard Aggregation

Task Capability Policy
    -> Tool Routing Layer (GUI/MCP/ask-user)

Conformance Test Suite
    -> Reliable Third-Party Adapter Onboarding
```

### Dependency Notes

- **Adapter contract requires unified action/tool contract:** otherwise each framework introduces incompatible semantics.
- **Unified trajectory schema requires action/tool normalization first:** evaluator cannot reason consistently otherwise.
- **Evaluator contract depends on trajectory schema:** both rule-based and LLM judges read the same evidence shape.

## MVP Definition

### Launch With (v1)

- [ ] Adapter contract for external frameworks (`initialize`, `step`, `finalize`, `report`)
- [ ] Unified action/tool event schema (GUI, MCP, ask-user)
- [ ] Canonical trajectory writer + adapter converters
- [ ] Evaluator contract with rule-based + optional LLM-judge backends
- [ ] Nanobot/OpenGUI reference adapter
- [ ] Framework-profiled CLI entry for eval runs and summary export

### Add After Validation (v1.x)

- [ ] OpenClaw and hermes reference adapters
- [ ] Conformance test automation CLI for third-party adapters
- [ ] Score consistency dashboard (judge drift checks)

### Future Consideration (v2+)

- [ ] Multi-language adapter gateway
- [ ] Online benchmark submission API
- [ ] Automatic prompt/task perturbation robustness suite

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Adapter contract | HIGH | MEDIUM | P1 |
| Unified tool contract | HIGH | HIGH | P1 |
| Unified trajectory schema | HIGH | HIGH | P1 |
| Evaluator contract | HIGH | MEDIUM | P1 |
| Nanobot/OpenGUI reference | HIGH | MEDIUM | P1 |
| Conformance CLI/tests | MEDIUM | MEDIUM | P2 |
| Cross-framework drift analytics | MEDIUM | HIGH | P2 |
| Non-Python adapter gateway | LOW | HIGH | P3 |

## Competitor Feature Analysis

| Feature | MobileWorld Current | nanobot/OpenGUI Pattern | Our Approach |
|---------|---------------------|--------------------------|--------------|
| Tool registration | Fixed MCP set in code | Dynamic registry + wrappers | Config-driven registry with task policies |
| Host integration | Built-in agents + `.py` loader | Protocol adapters (`LLMProvider`, backend contracts) | Adapter protocols in benchmark core |
| Evaluator | Task-owned scoring and logs | Reusable trajectory evaluator modules | Dual-mode evaluator contract (task + trajectory judge) |

## Sources

- MobileWorld `runtime/client.py`, `runtime/mcp_server.py`, `core/server.py`, `core/subcommands/eval.py`
- nanobot `nanobot/agent/tools/mcp.py`, `nanobot/agent/tools/registry.py`
- OpenGUI `opengui/interfaces.py`, `opengui/evaluation.py`

---
*Feature research for: MobileWorld multi-framework evaluation upgrade*
*Researched: 2026-04-16*
