---
phase: 07
slug: conformance-artifact-contract-closure
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-17
updated: 2026-04-17
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest` via `uv run --extra dev` |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_canonical_trajectory_contract.py tests/protocol/test_phase2_tool_router_policy.py` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol` |
| **Estimated runtime** | ~30-90 seconds depending on protocol suite size |

---

## Sampling Rate

- **After every task commit:** Run the task-specific `<automated>` command from the map below.
- **After every plan wave:** Run `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol`.
- **Before `$gsd-verify-work`:** Full suite must be green
- **Before phase closeout:** Run `.venv/bin/mobile-world benchmark conformance --log-root <run_root> --output /tmp/phase07-conformance-report.json` on a runtime-generated run root and require `ok: true`.
- **Max feedback latency:** <= 2 minutes for task-level checks

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | TRCE-01 | T-07-01-01 | Logger inserts canonical header through model-backed emit-once guard call sites | static-check | `bash -lc 'rg -n "def _ensure_canonical_header_event|CanonicalTrajectoryHeader\\(" src/mobile_world/runtime/utils/trajectory_logger.py && rg -n "_ensure_canonical_header_event\\(" src/mobile_world/runtime/utils/trajectory_logger.py'` | ✅ existing | ⬜ pending |
| 07-01-02 | 01 | 1 | TRCE-01 | T-07-01-02 | Canonical artifact contract enforces one header event plus schema-valid step/score events | integration | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_canonical_trajectory_contract.py` | ✅ existing | ⬜ pending |
| 07-02-01 | 02 | 2 | COMP-02 | T-07-02-01 | Logger exposes policy manifest persistence into legacy + canonical metadata stores | unit | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase2_tool_router_policy.py::test_tool_manifest_and_error_logged_to_artifacts` | ✅ existing | ⬜ pending |
| 07-02-02 | 02 | 2 | COMP-02 | T-07-02-02 | Runner logs `policy_manifest` before task execution from `CapabilityDecision.as_manifest()` | integration | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase2_tool_router_policy.py::test_tool_manifest_and_error_logged_to_artifacts` | ✅ existing | ⬜ pending |
| 07-02-03 | 02 | 2 | COMP-02 | T-07-02-03 | Regression test fails when policy manifest is missing from runtime artifact output | integration | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase2_tool_router_policy.py` | ✅ existing | ⬜ pending |
| 07-03-01 | 03 | 3 | COMP-02, TRCE-01 | T-07-03-01 | Runtime-generated artifacts pass conformance suite checks for header + policy manifest | integration | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase7_conformance_artifact_contract.py::test_runtime_artifacts_pass_conformance` | ➕ created in task | ⬜ pending |
| 07-03-02 | 03 | 3 | COMP-02, TRCE-01 | T-07-03-01 | Negative-path mutations fail exact contract checks (`canonical.header_present`, `meta.policy_manifest_present`) | integration | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase7_conformance_artifact_contract.py` | ✅ after 07-03-01 | ⬜ pending |
| 07-03-03 | 03 | 3 | COMP-02 | T-07-03-02 | Benchmark conformance CLI path validates runtime-generated artifacts and writes PASS report | integration | `UV_CACHE_DIR=/tmp/.uv-cache uv run --extra dev python -m pytest -q tests/protocol/test_phase7_conformance_artifact_contract.py` | ✅ after 07-03-01 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No `MISSING` automated references are present in plans 07-01/07-02/07-03.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | N/A | All phase behaviors in scope have automated checks | N/A |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency target defined and bounded
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved for planning state on 2026-04-17
