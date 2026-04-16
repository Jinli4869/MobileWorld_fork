# Framework Adapter Profiles

MobileWorld can execute via registered framework adapter profiles while preserving the same task/runtime/evaluator contract.

## Built-in Reference Profiles

- `nanobot_opengui`: Reference adapter with optional OpenGUI judge integration.
- `openclaw_template`: Scaffold adapter for OpenClaw onboarding.
- `hermes_template`: Scaffold adapter for Hermes onboarding.

## Eval CLI Usage

Run with a direct profile:

```bash
mobile-world eval \
  --agent-type qwen3vl \
  --model-name your-model \
  --llm-base-url http://localhost:8000/v1 \
  --framework-profile nanobot_opengui
```

Run with profile config file:

```bash
mobile-world eval \
  --agent-type qwen3vl \
  --model-name your-model \
  --llm-base-url http://localhost:8000/v1 \
  --framework-config ./framework-profile.json
```

Example `framework-profile.json`:

```json
{
  "framework_profile": "nanobot_opengui",
  "nanobot_fork_path": "~/Project/nanobot_fork",
  "judge_model": "qwen3-vl-plus"
}
```

## Adapter Scaffold TODOs

`openclaw_template` and `hermes_template` intentionally return a safe `wait` action until real framework wiring is implemented.

When implementing real adapters:

1. Replace scaffold prediction/action logic in `step`.
2. Map framework-native actions to canonical `JSONAction` payloads.
3. Emit framework trace artifacts in `emit_artifacts`.
4. Keep MobileWorld evaluator and metrics contracts unchanged.
