# Stack Research

**Domain:** Mobile agent benchmark platform with multi-framework adapter architecture
**Researched:** 2026-04-16
**Confidence:** HIGH

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

**If integrating OpenClaw/nanobot/hermes in Python:**
- Use in-process adapter modules with protocol interfaces
- Because lower latency, easier debugging, and less infra complexity

**If integrating non-Python frameworks later:**
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

---
*Stack research for: MobileWorld multi-framework evaluation architecture*
*Researched: 2026-04-16*
