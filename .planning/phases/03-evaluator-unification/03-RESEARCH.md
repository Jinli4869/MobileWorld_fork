# Phase 3: Evaluator Unification - Research

**Researched:** 2026-04-17
**Domain:** centralized evaluator interface, deterministic task scoring bridge, optional trajectory judge, evaluator audit output
**Confidence:** HIGH

## Summary

Current scoring is directly tied to `env.get_task_score` in runner, which couples execution and evaluation and makes cross-framework comparison less auditable. Phase 3 should introduce protocol evaluator interfaces and registry, then route scoring through a single evaluator pipeline.

A practical rollout:
- Add `runtime/protocol/evaluator.py` with evaluator input/result contracts and task-native bridge evaluator.
- Add evaluator registry and creation helpers.
- Add optional trajectory judge evaluator (enabled by config) that does not alter primary deterministic score.
- Persist evaluator audit artifacts so every score includes reason and evidence references.

This preserves current deterministic benchmark semantics while unlocking adapter-agnostic evaluator composability.

## Sources

- `src/mobile_world/core/runner.py`
- `src/mobile_world/runtime/client.py`
- `src/mobile_world/runtime/utils/trajectory_logger.py`
- `~/Project/nanobot_fork/opengui/evaluation.py`
