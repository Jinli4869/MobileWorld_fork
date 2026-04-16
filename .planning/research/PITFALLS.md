# Pitfalls Research

**Domain:** Cross-framework benchmark standardization for mobile agents
**Researched:** 2026-04-16
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: "Same task, different semantics"

**What goes wrong:** Different frameworks interpret action/tool results differently, causing unfair score differences.

**Why it happens:** No strict canonical action/tool event contract.

**How to avoid:** Define protocol models and conformance tests before adding adapters.

**Warning signs:** Same trajectory intent but mismatched event fields across frameworks.

**Phase to address:** Phase 1 (protocol baseline)

---

### Pitfall 2: MCP tool drift and uncontrolled exposure

**What goes wrong:** Tool sets differ by run, or unexpected MCP tools leak into evaluation.

**Why it happens:** Hard-coded MCP setup or permissive dynamic registration without policy.

**How to avoid:** Capability policy + allowlist + deterministic tool manifest per run.

**Warning signs:** Repeated score instability across re-runs with same seeds.

**Phase to address:** Phase 2 (tool router + capability policy)

---

### Pitfall 3: Evaluator inconsistency across frameworks

**What goes wrong:** Final score mixes framework-local logic with benchmark logic.

**Why it happens:** Evaluator location and responsibilities are not centralized.

**How to avoid:** Central evaluator contracts and one final scoring authority.

**Warning signs:** Framework-specific "success" without equivalent benchmark evidence.

**Phase to address:** Phase 3 (evaluator contract)

---

### Pitfall 4: Backward compatibility break

**What goes wrong:** Existing `mw eval`/`mw test` users lose functionality during refactor.

**Why it happens:** Big-bang rewrites that replace runner APIs.

**How to avoid:** Introduce adapter mode incrementally while preserving legacy path.

**Warning signs:** Existing built-in agent smoke tests failing after adapter work.

**Phase to address:** Phase 4 (compatibility + migration)

---

### Pitfall 5: Trace schema migration debt

**What goes wrong:** Old and new trace formats cannot be jointly analyzed.

**Why it happens:** No versioning and no converter strategy.

**How to avoid:** Versioned canonical schema with backward converters and validation CLI.

**Warning signs:** Evaluator fails to parse mixed historical logs.

**Phase to address:** Phase 5 (schema/versioning/reporting)

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Adapter writes custom trace directly | Faster initial integration | Broken downstream evaluator/reporting | Never for merged benchmark runs |
| Hard-code one framework into runner | Fast demo | Blocks later framework onboarding | Only in local spike branches |
| Skip policy checks for MCP in dev | Less friction | Unsafe and non-reproducible behavior | Never in shared eval configs |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Framework adapter | Returning framework-native action objects | Convert to canonical action/event model at boundary |
| MCP tools | Register all discovered tools by default | Use task/profile-scoped allowlist |
| LLM judge | Treat judge output as sole truth | Combine with deterministic task signals and diagnostics |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Heavy image payload in every event | Slow eval and large logs | Snapshot references + selective payload retention | Large batch runs |
| Unbounded retry loops in adapters | Hanging jobs and stale environments | Bounded retry and timeout policy | Unhealthy environments or flaky tools |
| Single-thread bottlenecks in evaluator | Long tail for batch completion | Parallel-safe evaluator workers | High task concurrency |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Unrestricted MCP server/tool usage | Data exfiltration and unsafe execution | Tool allowlist and endpoint trust policy |
| Unsanitized adapter metadata in logs | Log injection / analysis breakage | Schema validation and escaping at ingestion |
| Framework bypassing workspace restrictions | Out-of-scope system access | Enforce runtime path/tool constraints centrally |

## "Looks Done But Isn't" Checklist

- [ ] **Adapter onboarding:** implements lifecycle but lacks conformance tests
- [ ] **Tool routing:** runs MCP calls but no policy manifest captured in output
- [ ] **Evaluator:** returns score but cannot explain evidence path
- [ ] **Trace schema:** records events but missing version and converter metadata

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Semantic drift | Phase 1 | Contract tests pass across built-in + adapter |
| MCP drift | Phase 2 | Run manifest matches policy and is reproducible |
| Evaluator inconsistency | Phase 3 | Same run evidence gives consistent score across frameworks |
| Compatibility break | Phase 4 | Legacy smoke suite remains green |
| Trace migration debt | Phase 5 | Old/new logs parse and aggregate in one report |

## Sources

- MobileWorld runtime/runner/eval code paths
- nanobot MCP and tool registry patterns
- OpenGUI trajectory evaluation patterns

---
*Pitfalls research for: MobileWorld multi-framework evaluation upgrade*
*Researched: 2026-04-16*
