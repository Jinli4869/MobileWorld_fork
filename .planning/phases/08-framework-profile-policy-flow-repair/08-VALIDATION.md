---
phase: 08
slug: framework-profile-policy-flow-repair
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-17
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase8_framework_profile_policy_flow.py` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** Run `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase8_framework_profile_policy_flow.py`
- **After every plan wave:** Run `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | TOOL-02 | T-08-01-01 | Resolver profile identity is deterministic and branch-correct | unit | `... pytest -q tests/protocol/test_phase8_framework_profile_policy_flow.py::test_runner_uses_framework_profile_for_policy_resolution` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 2 | TOOL-02 | T-08-02-01 | Persisted policy manifest profile matches effective policy profile | integration | `... pytest -q tests/protocol/test_phase8_framework_profile_policy_flow.py::test_policy_manifest_profile_name_matches_effective_profile` | ❌ W0 | ⬜ pending |
| 08-03-01 | 03 | 3 | INTG-03 | T-08-03-01 | Eval framework-profile flow preserves profile semantics end-to-end | integration | `... pytest -q tests/protocol/test_phase8_framework_profile_policy_flow.py::test_eval_framework_profile_flow_preserves_profile_semantics` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/protocol/test_phase8_framework_profile_policy_flow.py` — new phase regression module
- [ ] Lightweight runner test doubles for env/agent/adapter paths

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Android/emulator eval run with `--framework-profile` and profile-scoped policy file | INTG-03 | Local CI may not have live backend/emulator and task runtime | Run `mobile-world eval --framework-profile ... --capability-policy-path ...` on representative tasks, then inspect run artifacts for `policy_manifest.profile_name` and policy-constrained behavior |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
