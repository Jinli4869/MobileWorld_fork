# Phase 4: Nanobot Reference Integration - Research

**Researched:** 2026-04-17
**Domain:** nanobot/OpenGUI adapter bridge, runner compatibility shim, artifact parity validation
**Confidence:** MEDIUM-HIGH

## Summary

The current runtime already has framework adapter contracts and registry, but runner execution still uses built-in agent prediction directly. To make nanobot/OpenGUI a reference integration while preserving compatibility:

1. Add a `NanobotOpenGUIAdapter` implementation that conforms to `FrameworkAdapter` and supports optional OpenGUI evaluator integration from `~/Project/nanobot_fork`.
2. Add runner support for adapter-driven step execution (without changing existing built-in path).
3. Register a `nanobot_opengui` profile in registry with a factory.
4. Add protocol tests that validate adapter registration, compatibility shim behavior, and artifact parity (legacy + canonical + metrics) under adapter mode.

This keeps MobileWorld task/runtime ownership intact while proving external framework adapter flow is feasible.

## Sources

- `src/mobile_world/runtime/protocol/adapter.py`
- `src/mobile_world/agents/registry.py`
- `src/mobile_world/core/runner.py`
- `~/Project/nanobot_fork/opengui/interfaces.py`
- `~/Project/nanobot_fork/opengui/evaluation.py`
