# Framework Adapter Profiles

MobileWorld can execute via registered framework adapter profiles while preserving the same task/runtime/evaluator contract.

## Built-in Reference Profiles

- `nanobot_opengui`: Reference adapter with optional OpenGUI judge integration.

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
  "nanobot_config_path": "~/Project/nanobot_fork/config/opengui.json",
  "gui_claw_path": "/home/jinli/Project/GUI-Claw",
  "evaluation_mode": "mixed",
  "allow_adb_bypass": true,
  "judge_model": "qwen3-vl-plus"
}
```

`nanobot_opengui` requires `nanobot_config_path`, and mixed-mode execution should set `evaluation_mode: "mixed"` and `allow_adb_bypass: true` for stable cross-framework comparability.

## Adding New Adapters

When implementing a new framework adapter:

1. Replace scaffold prediction/action logic in `step`.
2. Map framework-native actions to canonical `JSONAction` payloads.
3. Emit framework trace artifacts in `emit_artifacts`.
4. Keep MobileWorld evaluator and metrics contracts unchanged.
