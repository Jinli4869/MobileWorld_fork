---
phase: 09
slug: reproducibility-agreement-gate-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-17
---

# Phase 09 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase9_reproducibility_agreement_gate.py tests/protocol/test_phase6_reporting_conformance_reproducibility.py` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase9_reproducibility_agreement_gate.py tests/protocol/test_phase6_reporting_conformance_reproducibility.py` |
| **Estimated runtime** | ~150 seconds |

---

## Sampling Rate

- **After every task commit:** Run `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase9_reproducibility_agreement_gate.py`
- **After every plan wave:** Run `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase9_reproducibility_agreement_gate.py tests/protocol/test_phase6_reporting_conformance_reproducibility.py`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 150 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | METR-06 | T-09-01-01 | Stability gate pass/fail is deterministic even when judge data is missing | unit/integration | `... pytest -q tests/protocol/test_phase9_reproducibility_agreement_gate.py::test_reproducibility_stability_gate_passes_without_judge_data` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 2 | METR-07 | T-09-02-01 | Report and CLI expose agreement availability and enforced threshold outcome | unit/integration | `... pytest -q tests/protocol/test_phase9_reproducibility_agreement_gate.py::test_reproducibility_report_exposes_agreement_availability_state` | ❌ W0 | ⬜ pending |
| 09-03-01 | 03 | 3 | COMP-03 | T-09-03-01 | Regression suite covers judge-available and judge-unavailable reproducibility branches | integration | `... pytest -q tests/protocol/test_phase9_reproducibility_agreement_gate.py tests/protocol/test_phase6_reporting_conformance_reproducibility.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/protocol/test_phase9_reproducibility_agreement_gate.py` - new phase-9 regression module
- [ ] Shared synthetic artifact helper(s) for reproducibility branch tests

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real repeated-run benchmark with trajectory judge disabled or unavailable | METR-06, METR-07 | CI uses synthetic fixtures and does not guarantee live judge backend behavior | Run `mobile-world benchmark reproducibility --run-root ...` over repeated fixed-config runs without judge checks and confirm report marks agreement unavailable while preserving stability verdict |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 150s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
