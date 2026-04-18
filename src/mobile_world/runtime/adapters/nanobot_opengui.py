"""Nanobot/OpenGUI mixed execution adapter implementation."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from loguru import logger

from mobile_world.runtime.protocol.adapter import (
    AdapterArtifactsResult,
    AdapterFinalizeInput,
    AdapterFinalizeResult,
    AdapterInitializeInput,
    AdapterInitializeResult,
    AdapterStepInput,
    AdapterStepResult,
    ArtifactRecord,
    FrameworkAdapter,
)

_DEFAULT_NANOBOT_FORK_PATH = "/home/jinli/Project/nanobot_fork"
_DEFAULT_GUI_CLAW_PATH = "/home/jinli/Project/GUI-Claw"
_ALLOWED_EVALUATION_MODES = {"standard", "mixed"}


def _resolve_nanobot_fork_path(explicit: str | None) -> Path | None:
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if candidate.exists():
            return candidate
        return None

    env_candidate = os.getenv("NANOBOT_FORK_PATH")
    if env_candidate:
        candidate = Path(env_candidate).expanduser().resolve()
        if candidate.exists():
            return candidate

    default_candidate = Path(_DEFAULT_NANOBOT_FORK_PATH).expanduser().resolve()
    if default_candidate.exists():
        return default_candidate
    return None


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _coerce_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _json_loads_maybe(text: Any) -> dict[str, Any] | None:
    if isinstance(text, dict):
        return dict(text)
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    if not stripped:
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _infer_provider_name(model_name: str | None, llm_base_url: str | None) -> str:
    model = (model_name or "").strip().lower()
    base = (llm_base_url or "").strip().lower()

    if "dashscope" in base or "aliyuncs.com" in base:
        return "dashscope"
    if "openrouter" in base:
        return "openrouter"
    if "api.openai.com" in base:
        return "openai"
    if "qwen" in model:
        return "dashscope"
    if model.startswith("gpt"):
        return "openai"
    return "custom"


def _resolve_runtime_api_key(provider_name: str, explicit_api_key: str | None) -> str | None:
    if explicit_api_key:
        return explicit_api_key

    if provider_name == "dashscope":
        return os.getenv("DASHSCOPE_API_KEY") or os.getenv("API_KEY")
    if provider_name == "openai":
        return os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")
    if provider_name == "openrouter":
        return os.getenv("OPENROUTER_API_KEY") or os.getenv("API_KEY")
    if provider_name == "custom":
        return os.getenv("API_KEY")
    return (
        os.getenv("API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
    )


def _build_mw_adb_wrapper(
    *,
    output_dir: str,
    run_id: str,
    container_name: str,
    device: str | None,
) -> tuple[Path, Path, Path, Path]:
    runtime_root = Path(output_dir).expanduser() / ".nanobot_runtime" / run_id
    bin_dir = runtime_root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper_path = bin_dir / "mw_adb"
    adb_wrapper_path = bin_dir / "adb"
    call_log_path = runtime_root / "adb_wrapper_calls.log"
    call_log_path.touch(exist_ok=True)

    forward = f"docker exec {shlex.quote(container_name)} adb"
    if device:
        forward += f" -s {shlex.quote(device)}"
    container_literal = shlex.quote(container_name)
    serial_literal = shlex.quote(device) if device else "''"
    call_log_literal = shlex.quote(str(call_log_path))

    wrapper_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"printf '%s\\t%s\\n' 'mw_adb' \"$*\" >> {call_log_literal}\n"
        f'exec {forward} "$@"\n',
        encoding="utf-8",
    )
    wrapper_path.chmod(0o755)
    adb_wrapper_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"printf '%s\\t%s\\n' 'adb' \"$*\" >> {call_log_literal}\n"
        f"CONTAINER={container_literal}\n"
        f"DEFAULT_SERIAL={serial_literal}\n"
        "SERIAL_ARGS=()\n"
        "ARGS=(\"$@\")\n"
        "if [[ ${#ARGS[@]} -ge 2 && \"${ARGS[0]}\" == \"-s\" ]]; then\n"
        "  SERIAL_ARGS=(\"${ARGS[0]}\" \"${ARGS[1]}\")\n"
        "  ARGS=(\"${ARGS[@]:2}\")\n"
        "elif [[ -n \"$DEFAULT_SERIAL\" ]]; then\n"
        "  SERIAL_ARGS=(\"-s\" \"$DEFAULT_SERIAL\")\n"
        "fi\n"
        "if [[ ${#ARGS[@]} -eq 0 ]]; then\n"
        "  exec docker exec \"$CONTAINER\" adb \"${SERIAL_ARGS[@]}\"\n"
        "fi\n"
        "CMD=\"${ARGS[0]}\"\n"
        "if [[ \"$CMD\" == \"pull\" && ${#ARGS[@]} -ge 3 ]]; then\n"
        "  SRC=\"${ARGS[1]}\"\n"
        "  DST=\"${ARGS[2]}\"\n"
        "  TMP=\"/tmp/mw_adb_pull_$(date +%s%N)_$$\"\n"
        "  docker exec \"$CONTAINER\" adb \"${SERIAL_ARGS[@]}\" pull \"$SRC\" \"$TMP\" >/dev/null\n"
        "  if [[ \"$DST\" == */ ]]; then\n"
        "    mkdir -p \"$DST\"\n"
        "  else\n"
        "    mkdir -p \"$(dirname \"$DST\")\"\n"
        "  fi\n"
        "  docker cp \"$CONTAINER:$TMP\" \"$DST\" >/dev/null\n"
        "  docker exec \"$CONTAINER\" rm -f \"$TMP\" >/dev/null 2>&1 || true\n"
        "  exit 0\n"
        "fi\n"
        "if [[ \"$CMD\" == \"push\" && ${#ARGS[@]} -ge 3 ]]; then\n"
        "  SRC=\"${ARGS[1]}\"\n"
        "  DST=\"${ARGS[2]}\"\n"
        "  TMP=\"/tmp/mw_adb_push_$(date +%s%N)_$$\"\n"
        "  docker cp \"$SRC\" \"$CONTAINER:$TMP\" >/dev/null\n"
        "  docker exec \"$CONTAINER\" adb \"${SERIAL_ARGS[@]}\" push \"$TMP\" \"$DST\"\n"
        "  docker exec \"$CONTAINER\" rm -f \"$TMP\" >/dev/null 2>&1 || true\n"
        "  exit 0\n"
        "fi\n"
        "exec docker exec \"$CONTAINER\" adb \"${SERIAL_ARGS[@]}\" \"${ARGS[@]}\"\n",
        encoding="utf-8",
    )
    adb_wrapper_path.chmod(0o755)
    return bin_dir, wrapper_path, adb_wrapper_path, call_log_path


@contextmanager
def _temporary_sys_path(path: Path):
    path_str = str(path)
    if path_str in sys.path:
        yield
        return

    sys.path.insert(0, path_str)
    try:
        yield
    finally:
        try:
            sys.path.remove(path_str)
        except ValueError:
            pass


@contextmanager
def _temporary_environ(updates: dict[str, str | None]):
    previous: dict[str, str | None] = {}
    try:
        for key, value in updates.items():
            previous[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class NanobotOpenGUIAdapter(FrameworkAdapter):
    """Adapter that runs one full nanobot mixed execution per MobileWorld task."""

    def __init__(
        self,
        *,
        model_name: str | None = None,
        llm_base_url: str | None = None,
        api_key: str | None = None,
        nanobot_fork_path: str | None = None,
        nanobot_config_path: str | None = None,
        gui_claw_path: str | None = None,
        evaluation_mode: str | None = None,
        allow_adb_bypass: bool | None = None,
    ) -> None:
        self.model_name = model_name
        self.llm_base_url = llm_base_url
        self.api_key = api_key
        self.nanobot_root = _resolve_nanobot_fork_path(nanobot_fork_path)
        self.nanobot_config_path = nanobot_config_path
        self.gui_claw_path = gui_claw_path or _DEFAULT_GUI_CLAW_PATH
        self.evaluation_mode = (evaluation_mode or "mixed").strip().lower()
        self.allow_adb_bypass = True if allow_adb_bypass is None else bool(allow_adb_bypass)

        self._initialized = False
        self._state: dict[str, Any] = {}
        self._artifacts: list[ArtifactRecord] = []
        self._mixed_summary: dict[str, Any] | None = None
        self._task_executed = False

    def initialize(self, payload: AdapterInitializeInput) -> AdapterInitializeResult:
        options = dict(payload.options)
        runtime_mode = str(
            options.get("evaluation_mode")
            or self.evaluation_mode
            or "mixed"
        ).strip().lower()
        runtime_allow_adb_bypass = _coerce_bool(
            options.get("allow_adb_bypass"),
            default=self.allow_adb_bypass,
        )
        runtime_nanobot_config_path = (
            options.get("nanobot_config_path")
            or self.nanobot_config_path
        )
        runtime_gui_claw_path = str(
            options.get("gui_claw_path")
            or self.gui_claw_path
            or _DEFAULT_GUI_CLAW_PATH
        )

        if self.nanobot_root is None:
            return AdapterInitializeResult(
                ok=False,
                message="nanobot_fork_path_not_found",
                adapter_state={"nanobot_fork_path": options.get("nanobot_fork_path")},
            )

        if runtime_mode not in _ALLOWED_EVALUATION_MODES:
            return AdapterInitializeResult(
                ok=False,
                message=f"evaluation_mode_invalid:{runtime_mode}",
            )

        if runtime_mode != "mixed":
            return AdapterInitializeResult(
                ok=False,
                message="nanobot_opengui_requires_evaluation_mode_mixed",
            )

        if not runtime_allow_adb_bypass:
            return AdapterInitializeResult(
                ok=False,
                message="nanobot_opengui_requires_allow_adb_bypass_true",
            )

        if not runtime_nanobot_config_path:
            return AdapterInitializeResult(
                ok=False,
                message="nanobot_config_path_required",
            )

        nanobot_config = Path(str(runtime_nanobot_config_path)).expanduser().resolve()
        if not nanobot_config.exists() or not nanobot_config.is_file():
            return AdapterInitializeResult(
                ok=False,
                message=f"nanobot_config_path_not_found:{nanobot_config}",
            )

        self._initialized = True
        self._task_executed = False
        self._artifacts = []
        self._mixed_summary = None
        self._state = {
            "task_name": payload.task_name,
            "task_goal": payload.task_goal,
            "run_id": payload.run_id,
            "steps": 0,
            "options": options,
            "output_dir": str(options.get("output_dir", ".")),
            "nanobot_config_path": str(nanobot_config),
            "gui_claw_path": runtime_gui_claw_path,
            "evaluation_mode": runtime_mode,
            "allow_adb_bypass": runtime_allow_adb_bypass,
            "nanobot_fork_path": str(self.nanobot_root),
            "mobileworld_container_name": options.get("mobileworld_container_name"),
            "mobileworld_device": options.get("mobileworld_device"),
            "mobileworld_env_url": options.get("mobileworld_env_url"),
            "session_nonce": int(time.time() * 1000),
        }

        return AdapterInitializeResult(
            ok=True,
            message="nanobot_opengui mixed adapter initialized",
            adapter_state={
                "framework": "nanobot_opengui",
                "nanobot_root": str(self.nanobot_root),
                "nanobot_config_path": str(nanobot_config),
                "gui_claw_path": runtime_gui_claw_path,
                "evaluation_mode": runtime_mode,
                "allow_adb_bypass": runtime_allow_adb_bypass,
            },
        )

    def _run_coro_sync(self, coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        def _worker() -> Any:
            # Run the coroutine in a fresh thread to avoid nested loop conflicts.
            return asyncio.run(coro)

        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(_worker).result()

    async def _execute_with_nanobot_loop(
        self,
        *,
        task_name: str,
        task_goal: str,
        run_id: str,
    ) -> dict[str, Any]:
        if self.nanobot_root is None:
            raise RuntimeError("nanobot_fork_path_not_found")

        with _temporary_sys_path(self.nanobot_root):
            from nanobot.agent.loop import AgentLoop
            from nanobot.bus.queue import MessageBus
            from nanobot.cli.commands import _make_provider, _resolve_gui_runtime
            from nanobot.config.loader import load_config, set_config_path
            from nanobot.cron.service import CronService

            config_path = Path(self._state["nanobot_config_path"]).expanduser().resolve()
            set_config_path(config_path)
            config = load_config(config_path)
            config.agents.defaults.workspace = self._state["gui_claw_path"]
            if self.model_name:
                config.agents.defaults.model = self.model_name

            provider_name = config.agents.defaults.provider
            if provider_name == "auto":
                provider_name = _infer_provider_name(self.model_name, self.llm_base_url)
                config.agents.defaults.provider = provider_name

            provider_cfg = getattr(config.providers, provider_name, None)
            if provider_cfg is None:
                provider_name = "custom"
                config.agents.defaults.provider = provider_name
                provider_cfg = config.providers.custom

            runtime_api_key = _resolve_runtime_api_key(provider_name, self.api_key)
            if runtime_api_key and not provider_cfg.api_key:
                provider_cfg.api_key = runtime_api_key
            if self.llm_base_url and not provider_cfg.api_base:
                provider_cfg.api_base = self.llm_base_url

            mw_adb_wrapper: Path | None = None
            adb_wrapper: Path | None = None
            bin_dir: Path | None = None
            adb_call_log_path: Path | None = None
            container_name = self._state.get("mobileworld_container_name")
            device = self._state.get("mobileworld_device")
            if isinstance(container_name, str) and container_name.strip():
                bin_dir, mw_adb_wrapper, adb_wrapper, adb_call_log_path = _build_mw_adb_wrapper(
                    output_dir=str(self._state.get("output_dir", ".")),
                    run_id=run_id,
                    container_name=container_name.strip(),
                    device=str(device).strip() if isinstance(device, str) and device.strip() else None,
                )
                existing_path_append = config.tools.exec.path_append.strip()
                config.tools.exec.path_append = (
                    str(bin_dir)
                    if not existing_path_append
                    else f"{existing_path_append}{os.pathsep}{bin_dir}"
                )

            if config.gui is None:
                raise RuntimeError("nanobot_gui_config_missing")
            if adb_wrapper is not None:
                adb_cfg = getattr(config.gui, "adb", None)
                if adb_cfg is not None:
                    if hasattr(adb_cfg, "adb_path"):
                        adb_cfg.adb_path = str(adb_wrapper)
                    if isinstance(device, str) and device.strip() and hasattr(adb_cfg, "serial"):
                        adb_cfg.serial = device.strip()

            bus = MessageBus()
            provider = _make_provider(
                config,
                model_override=self.model_name or None,
                provider_override=provider_name,
            )
            gui_provider, gui_model = _resolve_gui_runtime(config)
            cron_store_path = config.workspace_path / "cron" / "jobs.json"
            cron = CronService(cron_store_path)

            agent_loop = AgentLoop(
                bus=bus,
                provider=provider,
                workspace=config.workspace_path,
                model=self.model_name or config.agents.defaults.model,
                max_iterations=config.agents.defaults.max_tool_iterations,
                context_window_tokens=config.agents.defaults.context_window_tokens,
                web_search_config=config.tools.web.search,
                web_proxy=config.tools.web.proxy or None,
                exec_config=config.tools.exec,
                cron_service=cron,
                restrict_to_workspace=config.tools.restrict_to_workspace,
                mcp_servers=config.tools.mcp_servers,
                channels_config=config.channels,
                gui_config=config.gui,
                gui_provider=gui_provider,
                gui_model=gui_model,
            )

            session_key = f"mobile_world:{run_id}:{self._state.get('session_nonce')}"
            instruction = (
                "You are running inside MobileWorld benchmark evaluation. "
                "Complete the target task on the connected Android device. "
                "Use gui_task/ADB/deeplink tooling when needed. "
                "When using shell commands for device control, do NOT use plain `adb`. "
                "Use `mw_adb` so commands run inside the MobileWorld container. "
                "Return a concise completion summary at the end.\n\n"
                f"Task Name: {task_name}\n"
                f"Task Goal: {task_goal}"
            )
            if mw_adb_wrapper is not None:
                instruction += (
                    "\n"
                    f"Device shell wrapper: {mw_adb_wrapper} (call as `mw_adb ...`)."
                )

            response = None
            messages: list[dict[str, Any]] = []
            env_updates: dict[str, str | None] = {}
            if bin_dir is not None:
                current_path = os.environ.get("PATH", "")
                env_updates["PATH"] = (
                    f"{bin_dir}{os.pathsep}{current_path}" if current_path else str(bin_dir)
                )
            if isinstance(device, str) and device.strip():
                env_updates["ANDROID_SERIAL"] = device.strip()
            try:
                with _temporary_environ(env_updates):
                    response = await agent_loop.process_direct(
                        instruction,
                        session_key=session_key,
                        channel="cli",
                        chat_id="direct",
                    )
                    session = agent_loop.sessions.get_or_create(session_key)
                    messages = list(session.messages)
            finally:
                await agent_loop.close_mcp()
                agent_loop.stop()

        wrapper_mw_adb_calls = 0
        wrapper_adb_calls = 0
        if adb_call_log_path is not None and adb_call_log_path.exists():
            try:
                for line in adb_call_log_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("mw_adb\t"):
                        wrapper_mw_adb_calls += 1
                    elif line.startswith("adb\t"):
                        wrapper_adb_calls += 1
            except Exception:
                logger.exception("failed_to_read_adb_wrapper_call_log")

        return {
            "success": True,
            "summary": response.content if response is not None else "",
            "messages": messages,
            "default_gui_backend": getattr(config.gui, "backend", None),
            "wrapper_mw_adb_calls": wrapper_mw_adb_calls,
            "wrapper_adb_calls": wrapper_adb_calls,
        }

    @staticmethod
    def _extract_lane_stats(
        messages: list[dict[str, Any]],
        *,
        default_gui_backend: str | None,
    ) -> dict[str, Any]:
        adb_calls = 0
        gui_task_calls = 0
        deeplink_calls = 0
        gui_steps = 0
        trace_refs: list[str] = []

        for message in messages:
            if not isinstance(message, dict):
                continue

            role = message.get("role")
            if role == "assistant":
                tool_calls = message.get("tool_calls")
                if not isinstance(tool_calls, list):
                    continue

                for tool_call in tool_calls:
                    if not isinstance(tool_call, dict):
                        continue

                    fn_payload = tool_call.get("function") if isinstance(tool_call.get("function"), dict) else tool_call
                    tool_name = fn_payload.get("name")
                    if not isinstance(tool_name, str):
                        continue

                    args = _json_loads_maybe(fn_payload.get("arguments")) or {}
                    normalized_name = tool_name.lower()

                    if normalized_name == "gui_task":
                        gui_task_calls += 1
                        backend = str(args.get("backend") or default_gui_backend or "").lower()
                        if backend == "adb":
                            adb_calls += 1
                    elif normalized_name in {"exec", "exec_shell", "tool.exec_shell"}:
                        command = str(args.get("command") or "").strip().lower()
                        command_padded = f" {command} "
                        if "mw_adb" in command:
                            adb_calls += 1
                        elif " adb " in command_padded or command.startswith("adb ") or "/adb " in command_padded:
                            adb_calls += 1
                    elif "deeplink" in normalized_name:
                        deeplink_calls += 1
                    elif normalized_name.startswith("adb") or "adb" in normalized_name:
                        adb_calls += 1

            if role == "tool" and message.get("name") == "gui_task":
                payload = _json_loads_maybe(message.get("content"))
                if payload is None:
                    continue
                gui_steps += _coerce_int(payload.get("steps_taken"), default=0)
                trace_path = payload.get("trace_path")
                if isinstance(trace_path, str) and trace_path.strip():
                    trace_refs.append(trace_path.strip())

        dedup_trace_refs = sorted({path for path in trace_refs})
        return {
            "adb_calls": adb_calls,
            "gui_task_calls": gui_task_calls,
            "deeplink_calls": deeplink_calls,
            "gui_steps": gui_steps,
            "trace_refs": dedup_trace_refs,
        }

    def _run_nanobot_mixed_execution(
        self,
        *,
        task_name: str,
        task_goal: str,
        run_id: str,
    ) -> dict[str, Any]:
        raw_result = self._run_coro_sync(
            self._execute_with_nanobot_loop(
                task_name=task_name,
                task_goal=task_goal,
                run_id=run_id,
            )
        )
        lane_stats = self._extract_lane_stats(
            raw_result.get("messages", []),
            default_gui_backend=raw_result.get("default_gui_backend"),
        )
        wrapper_mw_adb_calls = _coerce_int(raw_result.get("wrapper_mw_adb_calls"))
        wrapper_adb_calls = _coerce_int(raw_result.get("wrapper_adb_calls"))
        merged_adb_calls = max(
            _coerce_int(lane_stats.get("adb_calls")),
            wrapper_mw_adb_calls + wrapper_adb_calls,
        )
        merged_gui_task_calls = _coerce_int(lane_stats.get("gui_task_calls"))
        if merged_gui_task_calls == 0 and wrapper_adb_calls > 0:
            merged_gui_task_calls = 1
        return {
            "execution_mode": "mixed",
            "success": bool(raw_result.get("success", False)),
            "summary": str(raw_result.get("summary") or ""),
            "error": raw_result.get("error"),
            "adb_calls": merged_adb_calls,
            "gui_task_calls": merged_gui_task_calls,
            "deeplink_calls": _coerce_int(lane_stats.get("deeplink_calls")),
            "gui_steps": _coerce_int(lane_stats.get("gui_steps")),
            "trace_refs": lane_stats.get("trace_refs") or [],
            "token_usage": raw_result.get("token_usage"),
        }

    def step(self, payload: AdapterStepInput) -> AdapterStepResult:
        if not self._initialized:
            return AdapterStepResult(
                prediction=None,
                action={"action_type": "unknown"},
                done=True,
                info={"error": "adapter_not_initialized"},
            )

        if self._task_executed:
            return AdapterStepResult(
                prediction="nanobot_mixed_execution_already_completed",
                action={"action_type": "finished"},
                done=True,
                info={
                    "framework": "nanobot_opengui",
                    "execution_mode": "mixed",
                    "replayed": True,
                },
            )

        self._state["steps"] = int(self._state.get("steps", 0)) + 1
        observation = payload.observation if isinstance(payload.observation, dict) else {}

        try:
            injected = observation.get("nanobot_mixed_result")
            if isinstance(injected, dict):
                mixed_result = dict(injected)
                execution_source = "observation_injected"
            else:
                mixed_result = self._run_nanobot_mixed_execution(
                    task_name=payload.task_name,
                    task_goal=self._state.get("task_goal", payload.task_name),
                    run_id=payload.run_id,
                )
                execution_source = "nanobot_loop"
        except Exception as exc:
            logger.exception("nanobot mixed execution failed")
            mixed_result = {
                "execution_mode": "mixed",
                "success": False,
                "summary": "nanobot_mixed_execution_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "adb_calls": 0,
                "gui_task_calls": 0,
                "deeplink_calls": 0,
                "gui_steps": 0,
                "trace_refs": [],
            }
            execution_source = "nanobot_loop_error"

        self._task_executed = True
        self._mixed_summary = {
            "execution_mode": "mixed",
            "evaluation_mode": self._state.get("evaluation_mode", "mixed"),
            "allow_adb_bypass": bool(self._state.get("allow_adb_bypass", True)),
            "adb_calls": _coerce_int(mixed_result.get("adb_calls")),
            "gui_task_calls": _coerce_int(mixed_result.get("gui_task_calls")),
            "deeplink_calls": _coerce_int(mixed_result.get("deeplink_calls")),
            "gui_steps": _coerce_int(mixed_result.get("gui_steps")),
            "trace_refs": list(mixed_result.get("trace_refs") or []),
            "success": bool(mixed_result.get("success", False)),
            "summary": str(mixed_result.get("summary") or ""),
            "error": mixed_result.get("error"),
        }

        return AdapterStepResult(
            prediction=str(mixed_result.get("summary") or "nanobot_mixed_execution_completed"),
            action={"action_type": "finished"},
            done=True,
            info={
                "framework": "nanobot_opengui",
                "execution_mode": "mixed",
                "allow_adb_bypass": bool(self._state.get("allow_adb_bypass", True)),
                "execution_source": execution_source,
                "token_usage": mixed_result.get("token_usage"),
                "nanobot_success": bool(mixed_result.get("success", False)),
                "nanobot_error": mixed_result.get("error"),
            },
        )

    def finalize(self, payload: AdapterFinalizeInput) -> AdapterFinalizeResult:
        output_dir = Path(str(self._state.get("output_dir", "."))).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        mixed_summary = {
            "framework": "nanobot_opengui",
            "task_name": payload.task_name,
            "run_id": payload.run_id,
            "execution_mode": "mixed",
            "evaluation_mode": self._state.get("evaluation_mode", "mixed"),
            "allow_adb_bypass": bool(self._state.get("allow_adb_bypass", True)),
            "adb_calls": _coerce_int((self._mixed_summary or {}).get("adb_calls")),
            "gui_task_calls": _coerce_int((self._mixed_summary or {}).get("gui_task_calls")),
            "deeplink_calls": _coerce_int((self._mixed_summary or {}).get("deeplink_calls")),
            "gui_steps": _coerce_int((self._mixed_summary or {}).get("gui_steps")),
            "trace_refs": list((self._mixed_summary or {}).get("trace_refs") or []),
            "nanobot_success": bool((self._mixed_summary or {}).get("success", False)),
            "nanobot_summary": (self._mixed_summary or {}).get("summary"),
            "nanobot_error": (self._mixed_summary or {}).get("error"),
            "score": payload.score,
            "reason": payload.reason,
            "metrics": payload.metrics,
        }

        summary_path = output_dir / "nanobot_mixed_summary.json"
        summary_path.write_text(
            json.dumps(mixed_summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self._artifacts = [
            ArtifactRecord(
                path=str(summary_path),
                artifact_type="nanobot_mixed_summary",
                description="Per-task mixed execution summary emitted by nanobot_opengui adapter",
                metadata={
                    "task_name": payload.task_name,
                    "run_id": payload.run_id,
                    "execution_mode": "mixed",
                },
            )
        ]

        for trace_ref in mixed_summary["trace_refs"]:
            self._artifacts.append(
                ArtifactRecord(
                    path=str(trace_ref),
                    artifact_type="nanobot_trace",
                    description="Trace path reported by nanobot mixed execution",
                    metadata={
                        "task_name": payload.task_name,
                        "run_id": payload.run_id,
                    },
                )
            )

        self._initialized = False
        self._task_executed = False

        return AdapterFinalizeResult(
            ok=True,
            summary=f"nanobot_opengui adapter finalized for task {payload.task_name}",
            final_state={
                "score": payload.score,
                "reason": payload.reason,
                "metrics": payload.metrics,
                "steps": self._state.get("steps", 0),
                "mixed_summary": mixed_summary,
            },
        )

    def emit_artifacts(self, run_id: str, output_dir: str) -> AdapterArtifactsResult:
        _ = (run_id, output_dir)
        return AdapterArtifactsResult(artifacts=list(self._artifacts))
