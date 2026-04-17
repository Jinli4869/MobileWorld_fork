# Phase 09: Reproducibility Agreement Gate Hardening - Pattern Map

**Mapped:** 2026-04-17  
**Files analyzed:** 5  
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/mobile_world/runtime/protocol/reproducibility.py` | protocol | metrics/gate | `src/mobile_world/runtime/protocol/reproducibility.py` | exact |
| `src/mobile_world/core/subcommands/benchmark.py` | cli | protocol->user | `src/mobile_world/core/subcommands/benchmark.py` | exact |
| `tests/protocol/test_phase9_reproducibility_agreement_gate.py` | test | behavior/assertion | `tests/protocol/test_phase6_reporting_conformance_reproducibility.py` | role-match |
| `tests/protocol/test_phase6_reporting_conformance_reproducibility.py` | test | regression | `tests/protocol/test_phase6_reporting_conformance_reproducibility.py` | exact |
| `docs/benchmark_reporting.md` | docs | operator guidance | `docs/benchmark_reporting.md` | exact |

## Pattern Assignments

### `src/mobile_world/runtime/protocol/reproducibility.py` (protocol)

**Analog:** same file  
**Pattern to preserve:**
- Load repeated run roots
- Intersect common tasks
- Compute per-task variance and aggregate metrics
- Build a stable dict report shape for CLI and automation consumers

**Current gate pattern to replace:**
```python
judge_ok = (
    judge_agreement_rate is not None and judge_agreement_rate >= judge_agreement_threshold
)
return {
    "ok": variance_ok and judge_ok,
    ...
}
```

**Phase-9 pattern target:** keep variance gate deterministic, and explicitly model judge-agreement availability so missing judge data is not conflated with failure.

### `src/mobile_world/core/subcommands/benchmark.py` (CLI)

**Analog:** same file  
**Pattern to preserve:** subcommand-specific execution branches with deterministic JSON-friendly summaries.

**Phase-9 extension pattern:** in `benchmark reproducibility` branch, keep report emission flow but enrich console summary with explicit agreement-state labels derived from report fields.

### `tests/protocol/test_phase9_reproducibility_agreement_gate.py` (new)

**Primary analog:** `tests/protocol/test_phase6_reporting_conformance_reproducibility.py`  
**Pattern to preserve:** lightweight synthetic task artifact bundles with deterministic evaluator audit fixtures.

**Test style pattern:**
- Build synthetic run roots in `tmp_path`
- Control score variance and judge-check presence explicitly
- Assert exact report keys/values (`ok`, `agreement_available`, `agreement_passed`, thresholds)

### `docs/benchmark_reporting.md` (docs)

**Analog:** same file  
**Pattern to preserve:** command examples plus explicit output-field bullets.

**Phase-9 extension:** document unavailable-agreement semantics and which fields indicate enforced vs unavailable agreement gating.

## Anti-Patterns to Avoid

- Treating `judge_agreement_rate == None` as automatic failure without an explicit availability model.
- Returning ambiguous agreement fields where unavailable and failed are indistinguishable.
- Updating CLI output text without updating docs/tests to the same semantics.
- Introducing non-deterministic test fixtures that depend on live evaluator backends.
