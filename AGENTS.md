# AGENTS.md

## Project Purpose

This repository extends MobileWorld with a practical integration path for evaluating `nanobot_fork` under MobileWorld task/runtime/evaluator constraints.

Primary goal for current work:
- Keep MobileWorld native evaluation semantics intact.
- Run nanobot integration evaluations reliably.
- Avoid unnecessary adapter/template abstraction that does not contribute to runnable evaluation.

## Current Integration Scope

Active and supported integration profile:
- `nanobot_opengui`

Not in active scope:
- scaffold/template adapters for other frameworks (do not reintroduce placeholder profiles unless they can run real evaluation).

Key integration files:
- Adapter implementation: `src/mobile_world/runtime/adapters/nanobot_opengui.py`
- Adapter registration: `src/mobile_world/agents/registry.py`
- Eval CLI and framework config handling: `src/mobile_world/core/subcommands/eval.py`
- Runtime execution path: `src/mobile_world/core/runner.py`
- Cross-run reporting utilities: `src/mobile_world/runtime/protocol/reporting.py`
- Benchmark utilities: `src/mobile_world/core/subcommands/benchmark.py`

## Evaluation Config (Where to Set It)

Main integration config file in this repo:
- `/home/jinli/Project/MobileWorld_fork/configs/framework.nanobot_opengui.mixed.json`

This JSON is the source of truth for framework-side integration switches, including:
- `framework_profile`
- `nanobot_fork_path`
- `nanobot_config_path`
- `gui_claw_path`
- `evaluation_mode`
- `allow_adb_bypass`
- nanobot runtime limits and timeout controls

If starting a new evaluation task, update this config first.

## How To Run Integration Evaluation

### 1. Environment

From repo root:

```bash
cd /home/jinli/Project/MobileWorld_fork
```

Use project venv (or uv-managed environment) and ensure:
- MobileWorld backend env is available.
- `nanobot_fork_path` and `nanobot_config_path` in config are valid.
- API keys are set as needed (`API_KEY`, optionally judge-related keys).

### 2. Run Eval With Integration Config

Typical command:

```bash
uv run mobile-world eval \
  --agent-type qwen3vl \
  --model-name qwen3-vl-plus \
  --llm-base-url https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --framework-config /home/jinli/Project/MobileWorld_fork/configs/framework.nanobot_opengui.mixed.json \
  --task "TASK_NAME" \
  --output ./traj_logs/integration_run
```

Run all tasks by replacing `--task "TASK_NAME"` with:

```bash
--task ALL
```

### 3. Optional Benchmark Post-Processing

Aggregate:

```bash
uv run mobile-world benchmark aggregate \
  --framework-run nanobot=./traj_logs/integration_run \
  --output ./reports/integration_aggregate.json
```

Conformance check:

```bash
uv run mobile-world benchmark conformance \
  --log-root ./traj_logs/integration_run \
  --output ./reports/integration_conformance.json
```

Reproducibility:

```bash
uv run mobile-world benchmark reproducibility \
  --run-root ./traj_logs/integration_run_1 \
  --run-root ./traj_logs/integration_run_2 \
  --run-root ./traj_logs/integration_run_3 \
  --output ./reports/integration_reproducibility.json
```

## Metrics Policy

For evaluation-facing summaries, keep MobileWorld native scoring focus:
- task `score`
- success count/rate derived from score threshold

Do not add new non-native ranking metrics to eval summary outputs unless explicitly required.

## Artifacts To Check After Run

Per-run:
- `run_manifest.json`
- `eval_report_*.json`

Per-task:
- `score.txt`
- `traj.json`
- canonical trajectory/meta files
- `nanobot_mixed_summary.json` (integration diagnostics)

## Guidance For Future Codex Tasks

When asked to continue integration work:
1. Validate `configs/framework.nanobot_opengui.mixed.json` first.
2. Reproduce with a concrete eval command.
3. Prioritize fixes that preserve MobileWorld native task scoring semantics.
4. Prefer simplifying over adding new abstraction layers.
5. Add/adjust protocol tests only for behavior that is actually exercised in nanobot evaluation flow.
