<!-- GSD:project-start source:PROJECT.md -->
## Project

**MobileWorld Multi-Framework Evaluation Upgrade**

This project upgrades the existing MobileWorld benchmark from a built-in-agent evaluation stack into a framework-agnostic evaluation platform. The goal is to evaluate OpenClaw/nanobot/hermes-style agents under one task/runtime/evaluator standard while preserving MobileWorld's deterministic Android benchmark strengths. The target users are researchers and engineers who need fair, reproducible cross-framework agent evaluation with GUI actions, MCP tools, and evaluator calls.

**Core Value:** One benchmark, one task standard, one evaluator contract, multiple agent frameworks with reproducible and comparable results.

### Constraints

- **Compatibility**: Existing CLI paths and built-in agents must continue to run — avoid breaking current users.
- **Determinism**: Task init/eval semantics must stay reproducible across frameworks — benchmark comparability depends on this.
- **Runtime boundary**: Keep task/server/runtime ownership inside MobileWorld; external frameworks integrate through adapters, not by bypassing server contracts.
- **MCP safety**: Tool registration and invocation must support allowlisting/timeouts and fail-safe behavior.
- **Evaluator integrity**: Cross-framework comparisons require normalized trajectory artifacts and stable scoring policy.
- **Tech stack**: Python 3.12 project with existing FastAPI + uv runtime and Android emulator workflow.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 | Primary runtime for benchmark core | Already the current MobileWorld runtime and task ecosystem |
| FastAPI + Uvicorn | FastAPI 0.104+, Uvicorn 0.24+ | Stable benchmark server APIs | Existing production path in MobileWorld; minimal migration risk |
| Pydantic v2 | 2.x | Contract-first schema for actions/tools/evaluation events | Ideal for strict protocol boundaries and adapter validation |
| OpenAI-compatible client abstraction | OpenAI SDK 1.x + provider wrappers | Unified model/evaluator invocation | Current agent/evaluator paths already rely on this shape |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `mcp` + `fastmcp` | `mcp>=1.9.4`, `fastmcp>=2.9.2` | MCP server/client and tool schema bridge | Dynamic MCP tool registration and call routing |
| `httpx`/`requests` | existing | Adapter transport and benchmark API calls | Framework adapters and evaluator connectors |
| `joblib` | existing | Parallel task execution | Controlled multi-env benchmark runs |
| `jsonlines` | existing | Unified trajectory artifact storage | Cross-framework trace normalization |
| `rich` | existing | CLI reporting and summary visualization | Consistent eval/leaderboard output |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| `pytest` | Contract/integration regression tests | Must add adapter contract tests and evaluator equivalence tests |
| `ruff` + `mypy` | Static quality gates | Keep protocol boundaries explicit and typed |
| Docker + AVD snapshots | Deterministic benchmark env | Preserve existing MobileWorld reproducibility foundation |
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Protocol adapter layer inside MobileWorld | Separate adapter gateway service | Use separate service only if cross-language framework support becomes dominant |
| Unified Pydantic contracts | Ad-hoc dict passing | Never for benchmark-critical interfaces due to silent mismatch risk |
| Server-owned evaluator contracts | Framework-owned evaluator logic | Use framework-owned logic only for exploratory metrics, not leaderboard metrics |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Hard-coded MCP server list only | Blocks framework portability and custom tool ecosystems | Config-driven MCP registry with allowlist and timeout control |
| Framework-specific trajectory formats | Breaks cross-framework comparability | Canonical MobileWorld trajectory schema + adapter converters |
| Direct framework bypass of MobileWorld task APIs | Undermines determinism and fairness | Adapter calling standard task lifecycle APIs |
## Stack Patterns by Variant
- Use in-process adapter modules with protocol interfaces
- Because lower latency, easier debugging, and less infra complexity
- Use thin RPC adapter boundary with same contracts
- Because contract remains stable while runtime language can differ
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `openai>=1.106.1` | OpenAI-compatible providers | Use wrapper to handle provider-specific tool-call differences |
| `mcp>=1.9.4` | HTTP/SSE/stdio MCP servers | Normalize schema and timeout behavior in adapter layer |
| `pydantic>=2` | FastAPI server models | Reuse for adapter/evaluator contracts to reduce model drift |
## Sources
- MobileWorld codebase (`src/mobile_world/runtime`, `src/mobile_world/core`, `src/mobile_world/agents`) — current benchmark runtime and contracts
- MobileWorld docs (`README.md`, `docs/mcp_setup.md`) — current CLI and MCP operational model
- nanobot/OpenGUI codebase (`nanobot/agent/tools/mcp.py`, `opengui/interfaces.py`, `opengui/evaluation.py`) — adapter and evaluator reference patterns
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
