# Phase 2: Tool Router & Capability Policy - Research

**Researched:** 2026-04-17
**Domain:** Unified tool dispatch, capability gating, MCP allowlist policy, normalized tool error events
**Confidence:** HIGH

## Summary

Current execution path routes actions through `env.execute_action` directly inside `core/runner.py`. GUI/MCP/ask-user behavior is split across `AndroidEnvClient` and `AndroidMCPEnvClient`, but there is no central policy gate or normalized tool failure shape. This phase should add a protocol-level router and capability-policy resolution layer, then wire it into runner pre-step dispatch.

MCP integration currently depends on hard-coded `MCP_CONFIG` and task metadata-driven filtering (`reset_tools(task_type=...)`). To satisfy deterministic comparability, the runtime needs explicit policy-driven allowlist/timeout decisions recorded into run artifacts (`traj.meta.json` and legacy log body).

Primary approach:
- Add `runtime/protocol/capability_policy.py` for deterministic policy resolution.
- Add `runtime/protocol/tool_router.py` for one dispatch path and normalized errors.
- Integrate policy + router into `_process_task_on_env` and `_execute_single_task`.
- Extend trajectory logger with tool manifest + tool error persistence.

## Sources

- `src/mobile_world/core/runner.py`
- `src/mobile_world/runtime/client.py`
- `src/mobile_world/runtime/mcp_server.py`
- `src/mobile_world/runtime/utils/trajectory_logger.py`
- `src/mobile_world/runtime/utils/models.py`
- `src/mobile_world/core/subcommands/eval.py`
