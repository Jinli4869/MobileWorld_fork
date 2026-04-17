# Benchmark Reporting and Conformance CLI

Phase 6 adds a dedicated `benchmark` command group for trace conversion, aggregation reporting, conformance checks, and reproducibility analysis.

## Convert Legacy Trace

Convert one legacy `traj.json` into canonical JSONL events:

```bash
mobile-world benchmark convert-trace \
  --legacy-traj ./traj_logs/task_x/traj.json \
  --output ./traj_logs/task_x/traj.canonical.converted.jsonl \
  --task-name task_x
```

## Cross-Framework Aggregation

Aggregate framework runs over common task sets and output KPI-enriched leaderboard JSON:

```bash
mobile-world benchmark aggregate \
  --framework-run nanobot=./runs/nanobot_20260417 \
  --framework-run openclaw=./runs/openclaw_20260417 \
  --framework-run hermes=./runs/hermes_20260417 \
  --success-threshold 0.99 \
  --output ./reports/framework_comparison.json
```

Key output sections:

- `leaderboard`: success rate, average score, tokens per success, cost per success
- `kpi_panels.efficiency`: tokens/cost per success and average steps
- `kpi_panels.latency`: average TTFT
- `kpi_panels.reliability`: tool success and invalid action rates
- `kpi_panels.evaluation_quality`: judge agreement rate

## Artifact Conformance Suite

Validate adapter/tool/evaluator/metrics contract integrity for one run root:

```bash
mobile-world benchmark conformance \
  --log-root ./runs/nanobot_20260417 \
  --output ./reports/nanobot_conformance.json
```

Conformance checks include:

- protocol adapter contract validation
- canonical schema consistency validation
- per-task artifact bundle checks (`traj/meta/metrics/audit/score`)
- metrics/evaluator payload shape checks

## Reproducibility and Judge Agreement

Evaluate repeated fixed-config runs for stability and judge-agreement thresholds:

```bash
mobile-world benchmark reproducibility \
  --run-root ./runs/nanobot_repeat_1 \
  --run-root ./runs/nanobot_repeat_2 \
  --run-root ./runs/nanobot_repeat_3 \
  --variance-threshold 0.02 \
  --agreement-threshold 0.8 \
  --output ./reports/nanobot_reproducibility.json
```

Outputs include:

- per-task score variance and pass/fail
- overall reproducibility variance
- judge agreement rate and threshold verdict
- `evaluation_quality.agreement_available`: whether any judge checks were present
- `evaluation_quality.agreement_status`: one of `passed`, `failed`, or `unavailable`
- `evaluation_quality.agreement_passed`: boolean when available, `null` when unavailable
- `gate_summary`: explicit stability gate, agreement gate, and overall status fields

Agreement semantics:

- If judge checks are unavailable, reproducibility can still pass when variance checks pass.
- If judge checks are available, agreement threshold enforcement remains mandatory.
