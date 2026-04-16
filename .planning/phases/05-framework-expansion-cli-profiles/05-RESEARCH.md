# Phase 5: Framework Expansion & CLI Profiles - Research

**Researched:** 2026-04-17
**Domain:** adapter template scaffolds, framework-profile CLI config, framework inventory reporting
**Confidence:** HIGH

## Summary

Phase 4 introduced adapter-mode execution and nanobot reference profile. Phase 5 should generalize this for broader onboarding:

1. Add OpenClaw/hermes scaffold adapters with clear contract-preserving placeholders.
2. Extend eval CLI with framework profile config loading so framework runs can be selected reproducibly.
3. Add framework inventory reporting (registered profiles, capabilities, conformance status) via `info framework`.

This delivers operator-ready framework profile workflows without breaking built-in default behavior.

## Sources

- `src/mobile_world/runtime/adapters/nanobot_opengui.py`
- `src/mobile_world/agents/registry.py`
- `src/mobile_world/core/subcommands/eval.py`
- `src/mobile_world/core/subcommands/info.py`
- `src/mobile_world/core/api/info.py`
