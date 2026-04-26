"""Eval subcommand for MobileWorld CLI - Run benchmark evaluation suite."""

import argparse
import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..runner import run_agent_with_evaluation


def load_framework_config(path: str) -> dict:
    """Load framework profile config JSON for eval runs."""
    config_path = Path(path).expanduser()
    with open(config_path, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Framework config must be a JSON object: {config_path}")
    return payload


_DEFAULT_NANOBOT_FORK_PATH = "/home/jinli/Project/nanobot_fork"
_DEFAULT_GUI_CLAW_PATH = "/home/jinli/Project/GUI-Claw"
_ALLOWED_EVALUATION_MODES = {"standard", "mixed"}


def _normalize_bool(value: object, *, default: bool) -> bool:
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


def _normalize_positive_int(
    value: object,
    *,
    default: int | None,
    field_name: str,
) -> int | None:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an integer, got: {value!r}") from None
    if parsed <= 0:
        raise ValueError(f"{field_name} must be > 0, got: {parsed}")
    return parsed


def _path_fingerprint(path_value: str | None) -> dict:
    if not path_value:
        return {"path": None, "exists": False, "fingerprint": None, "path_type": None}

    path = Path(path_value).expanduser().resolve()
    exists = path.exists()
    path_type = "file" if path.is_file() else "dir" if path.is_dir() else None

    digest = hashlib.sha256()
    digest.update(str(path).encode("utf-8"))
    digest.update(str(exists).encode("utf-8"))
    digest.update(str(path_type).encode("utf-8"))

    if exists:
        stat = path.stat()
        digest.update(str(stat.st_size).encode("utf-8"))
        digest.update(str(stat.st_mtime_ns).encode("utf-8"))
        if path.is_file():
            digest.update(path.read_bytes())

    return {
        "path": str(path),
        "exists": exists,
        "path_type": path_type,
        "fingerprint": digest.hexdigest(),
    }


def _task_set_fingerprint(task_names: list[str]) -> str:
    digest = hashlib.sha256()
    payload = "\n".join(sorted(task_names))
    digest.update(payload.encode("utf-8"))
    return digest.hexdigest()


def _write_run_manifest(
    *,
    run_root: str,
    framework_profile: str | None,
    evaluation_mode: str,
    allow_adb_bypass: bool,
    task_names: list[str],
    framework_config_path: str | None,
    nanobot_fork_path: str | None,
    nanobot_config_path: str | None,
    gui_claw_path: str | None,
    nanobot_max_steps: int | None,
    nanobot_gui_task_max_steps: int | None,
    nanobot_gui_task_max_calls: int | None,
    nanobot_timeout_seconds: int | None,
    nanobot_enable_planner: bool | None,
    nanobot_enable_router: bool | None,
    env_auto_recover: bool,
    env_recover_unhealthy_threshold: int,
    skill_config_path: str | None,
    skill_config: dict | None,
) -> Path:
    output_root = Path(run_root).expanduser()
    output_root.mkdir(parents=True, exist_ok=True)

    canonical_tasks = sorted(task_names)
    manifest = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now().isoformat(),
        "framework_profile": framework_profile,
        "evaluation_mode": evaluation_mode,
        "allow_adb_bypass": bool(allow_adb_bypass),
        "nanobot_max_steps": nanobot_max_steps,
        "nanobot_gui_task_max_steps": nanobot_gui_task_max_steps,
        "nanobot_gui_task_max_calls": nanobot_gui_task_max_calls,
        "nanobot_timeout_seconds": nanobot_timeout_seconds,
        "nanobot_enable_planner": nanobot_enable_planner,
        "nanobot_enable_router": nanobot_enable_router,
        "env_auto_recover": env_auto_recover,
        "env_recover_unhealthy_threshold": env_recover_unhealthy_threshold,
        "skill_config": skill_config or {},
        "task_set": canonical_tasks,
        "task_set_fingerprint": _task_set_fingerprint(canonical_tasks),
        "path_fingerprints": {
            "framework_config_path": _path_fingerprint(framework_config_path),
            "nanobot_fork_path": _path_fingerprint(nanobot_fork_path),
            "nanobot_config_path": _path_fingerprint(nanobot_config_path),
            "gui_claw_path": _path_fingerprint(gui_claw_path),
            "skill_config_path": _path_fingerprint(skill_config_path),
        },
    }

    manifest_path = output_root / "run_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest_path


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add common arguments shared between eval and test commands."""
    parser.add_argument(
        "--agent-type",
        "--agent_type",
        required=True,
        dest="agent_type",
        help="Type of agent to use (registered name or path to Python file containing agent class)",
    )
    parser.add_argument("--model-name", "--model_name", dest="model_name", help="Model name to use")
    parser.add_argument(
        "--llm-base-url",
        "--llm_base_url",
        dest="llm_base_url",
        help="LLM service base URL",
    )
    parser.add_argument(
        "--api-key",
        "--api_key",
        dest="api_key",
        help="API key for LLM service",
    )
    parser.add_argument(
        "--log-file-root",
        "--log_file_root",
        dest="log_file_root",
        help="Root directory for log files",
    )
    parser.add_argument(
        "--max-round",
        "--max_round",
        "--max-step",
        "--max_step",
        dest="max_round",
        type=int,
        help="Maximum number of steps (-1 for unlimited)",
    )
    parser.add_argument(
        "--aw-host", "--aw_host", dest="aw_host", help="Android World server host", default=None
    )
    parser.add_argument("--timeout", type=int, help="Task timeout in seconds")
    parser.add_argument("--output", dest="output", help="Output directory for results")

    # Executor settings for planner-executor agents
    parser.add_argument(
        "--executor-llm-base-url",
        "--executor_llm_base_url",
        dest="executor_llm_base_url",
        help="Executor LLM service base URL",
    )
    parser.add_argument(
        "--executor-model-name",
        "--executor_model_name",
        dest="executor_model_name",
        help="Executor model name",
    )
    parser.add_argument(
        "--executor-agent-class",
        "--executor_agent_class",
        dest="executor_agent_class",
        help="Executor agent class name",
    )

    # Device configuration
    parser.add_argument(
        "--device",
        dest="device",
        default=None,
        help="Android device ID (default: get via adb devices)",
    )
    parser.add_argument(
        "--step-wait-time",
        "--step_wait_time",
        dest="step_wait_time",
        type=float,
        default=1.0,
        help="Wait time in seconds after each step (default: 1.0)",
    )
    parser.add_argument(
        "--suite-family",
        "--suite_family",
        dest="suite_family",
        choices=["mobile_world"],
        default="mobile_world",
        help="Suite family to use (default: mobile_world)",
    )
    parser.add_argument(
        "--env-name-prefix",
        "--env_name_prefix",
        "--env-prefix",
        "--env_prefix",
        dest="env_name_prefix",
        default="mobile_world_env",
        help="Name prefix for containers (default: mobile_world_env)",
    )
    parser.add_argument(
        "--env-image",
        "--env_image",
        dest="env_image",
        default="mobile_world",
        help="Image name for containers (default: mobile_world)",
    )
    parser.add_argument(
        "--enable-mcp",
        "--enable_mcp",
        dest="enable_mcp",
        action="store_true",
        help="Enable MCP server",
    )
    parser.add_argument(
        "--enable-user-interaction",
        "--enable_user_interaction",
        dest="enable_user_interaction",
        action="store_true",
        help="Enable user interaction tasks (agent-user-interaction). Default: only GUI-only tasks",
    )
    parser.add_argument(
        "--scale-factor",
        "--scale_factor",
        dest="scale_factor",
        type=int,
        default=1000,
        help="Scale factor for coordinate conversion (default: 1000)",
    )
    parser.add_argument(
        "--skip-protocol-validation",
        "--skip_protocol_validation",
        dest="skip_protocol_validation",
        action="store_true",
        help="Skip protocol pre-flight validation (debug only)",
    )
    parser.add_argument(
        "--capability-policy",
        "--capability_policy",
        dest="capability_policy_path",
        help="Path to capability policy JSON config",
    )
    parser.add_argument(
        "--mcp-tool-allowlist",
        "--mcp_tool_allowlist",
        dest="mcp_tool_allowlist",
        help="Comma-separated MCP tool allowlist override (supports '*' and fnmatch patterns)",
    )
    parser.add_argument(
        "--enable-trajectory-judge",
        "--enable_trajectory_judge",
        dest="enable_trajectory_judge",
        action="store_true",
        help="Enable optional trajectory judge backend (deterministic score remains primary signal)",
    )
    parser.add_argument(
        "--judge-model",
        "--judge_model",
        dest="judge_model",
        default="qwen3-vl-plus",
        help="Trajectory judge model name (used when --enable-trajectory-judge is set)",
    )
    parser.add_argument(
        "--judge-api-key",
        "--judge_api_key",
        dest="judge_api_key",
        help="Trajectory judge API key (falls back to JUDGE_API_KEY then API_KEY)",
    )
    parser.add_argument(
        "--judge-api-base",
        "--judge_api_base",
        dest="judge_api_base",
        help="Trajectory judge API base URL (optional OpenAI-compatible endpoint)",
    )
    parser.add_argument(
        "--framework-profile",
        "--framework_profile",
        dest="framework_profile",
        help="Optional protocol adapter profile to run via framework adapter mode (e.g. nanobot_opengui)",
    )
    parser.add_argument(
        "--framework-config",
        "--framework_config",
        dest="framework_config",
        help="Path to JSON config file providing framework_profile and related adapter options",
    )
    parser.add_argument(
        "--skill-config",
        "--skill_config",
        dest="skill_config",
        help="Path to JSON config file enabling MobileWorld-native GUI skill reuse",
    )
    parser.add_argument(
        "--nanobot-fork-path",
        "--nanobot_fork_path",
        dest="nanobot_fork_path",
        help="Path to nanobot_fork workspace for nanobot_opengui mixed execution",
    )
    parser.add_argument(
        "--nanobot-config-path",
        "--nanobot_config_path",
        dest="nanobot_config_path",
        help="Path to fixed nanobot config file (required for nanobot_opengui)",
    )
    parser.add_argument(
        "--gui-claw-path",
        "--gui_claw_path",
        dest="gui_claw_path",
        default=_DEFAULT_GUI_CLAW_PATH,
        help=f"GUI-Claw workspace path (default: {_DEFAULT_GUI_CLAW_PATH})",
    )
    parser.add_argument(
        "--evaluation-mode",
        "--evaluation_mode",
        dest="evaluation_mode",
        choices=["standard", "mixed"],
        help="Evaluation mode used for reporting comparability (standard|mixed)",
    )
    parser.add_argument(
        "--allow-adb-bypass",
        "--allow_adb_bypass",
        dest="allow_adb_bypass",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Allow mixed execution to bypass MobileWorld tool router and use ADB-capable framework lanes",
    )
    parser.add_argument(
        "--nanobot-max-steps",
        "--nanobot_max_steps",
        dest="nanobot_max_steps",
        type=int,
        default=None,
        help="Max total tool iterations for nanobot/opengui mixed loop (default for nanobot_opengui: 50)",
    )
    parser.add_argument(
        "--nanobot-gui-task-max-steps",
        "--nanobot_gui_task_max_steps",
        dest="nanobot_gui_task_max_steps",
        type=int,
        default=None,
        help="Max GUI steps per gui_task call inside nanobot/opengui mixed loop (default: 50)",
    )
    parser.add_argument(
        "--nanobot-gui-task-max-calls",
        "--nanobot_gui_task_max_calls",
        dest="nanobot_gui_task_max_calls",
        type=int,
        default=None,
        help="Max gui_task invocations per task inside nanobot/opengui mixed loop (default: 3)",
    )
    parser.add_argument(
        "--nanobot-timeout-seconds",
        "--nanobot_timeout_seconds",
        dest="nanobot_timeout_seconds",
        type=int,
        default=None,
        help="Hard timeout in seconds for one nanobot mixed execution (overrides adaptive default when set)",
    )
    parser.add_argument(
        "--nanobot-enable-planner",
        "--nanobot_enable_planner",
        dest="nanobot_enable_planner",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable nanobot planner path (default for nanobot_opengui: false)",
    )
    parser.add_argument(
        "--nanobot-enable-router",
        "--nanobot_enable_router",
        dest="nanobot_enable_router",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable nanobot tree router (default for nanobot_opengui: false; requires planner enabled)",
    )
    parser.add_argument(
        "--env-auto-recover",
        "--env_auto_recover",
        dest="env_auto_recover",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Auto-recover unhealthy backend by restarting container when unhealthy threshold is reached",
    )
    parser.add_argument(
        "--env-recover-unhealthy-threshold",
        "--env_recover_unhealthy_threshold",
        dest="env_recover_unhealthy_threshold",
        type=int,
        default=None,
        help="Consecutive unhealthy retries before triggering container restart (default: 2)",
    )


def configure_parser(subparsers: argparse._SubParsersAction) -> None:
    """Configure the eval subcommand parser."""
    # Create eval parser with 'run' as an alias for backward compatibility
    eval_parser = subparsers.add_parser(
        "eval",
        aliases=["run"],
        help="Run benchmark evaluation suite",
    )

    _add_common_arguments(eval_parser)

    # Eval-specific arguments
    eval_parser.add_argument(
        "--task",
        "--tasks",
        dest="task",
        help='Specific task(s) to run (comma-separated) or "ALL" to run all tasks and generate statistics',
    )
    eval_parser.add_argument(
        "--auto-retry",
        "--auto_retry",
        dest="auto_retry",
        type=int,
        default=10,
        help="Number of automatic retry rounds for failed/stale tasks (default: 10)",
    )
    eval_parser.add_argument(
        "--dry-run",
        "--dry_run",
        dest="dry_run",
        action="store_true",
        help="Dry run the command, print final results only without executing tasks",
    )
    eval_parser.add_argument(
        "--max-concurrency",
        "--max_concurrency",
        dest="max_concurrency",
        type=int,
        default=None,
        help="Maximum number of concurrent tasks to run, Note: min(max_concurrency, number of tasks, number of docker envs)",
    )
    eval_parser.add_argument(
        "--shuffle-tasks",
        "--shuffle_tasks",
        dest="shuffle_tasks",
        action="store_true",
        help="Shuffle the order of tasks before running",
    )


async def execute(args: argparse.Namespace) -> None:
    """Execute the eval command."""
    log_file_root = args.log_file_root or args.output or "./traj_logs"
    framework_profile = getattr(args, "framework_profile", None)
    nanobot_fork_path = getattr(args, "nanobot_fork_path", None)
    nanobot_config_path = getattr(args, "nanobot_config_path", None)
    gui_claw_path = getattr(args, "gui_claw_path", _DEFAULT_GUI_CLAW_PATH)
    evaluation_mode = getattr(args, "evaluation_mode", None)
    allow_adb_bypass = getattr(args, "allow_adb_bypass", None)
    nanobot_max_steps = getattr(args, "nanobot_max_steps", None)
    nanobot_gui_task_max_steps = getattr(args, "nanobot_gui_task_max_steps", None)
    nanobot_gui_task_max_calls = getattr(args, "nanobot_gui_task_max_calls", None)
    nanobot_timeout_seconds = getattr(args, "nanobot_timeout_seconds", None)
    nanobot_enable_planner = getattr(args, "nanobot_enable_planner", None)
    nanobot_enable_router = getattr(args, "nanobot_enable_router", None)
    env_auto_recover = getattr(args, "env_auto_recover", None)
    env_recover_unhealthy_threshold = getattr(args, "env_recover_unhealthy_threshold", None)
    judge_model = getattr(args, "judge_model", "qwen3-vl-plus")
    judge_api_base = getattr(args, "judge_api_base", None)
    judge_api_key = (
        getattr(args, "judge_api_key", None)
        or os.getenv("JUDGE_API_KEY")
        or args.api_key
        or os.getenv("API_KEY")
    )
    skill_config_path = getattr(args, "skill_config", None)
    skill_config_payload = None

    framework_config_path = getattr(args, "framework_config", None)
    if framework_config_path:
        config_payload = load_framework_config(framework_config_path)
        framework_profile = config_payload.get("framework_profile", framework_profile)
        nanobot_fork_path = config_payload.get("nanobot_fork_path", nanobot_fork_path)
        nanobot_config_path = config_payload.get("nanobot_config_path", nanobot_config_path)
        gui_claw_path = config_payload.get("gui_claw_path", gui_claw_path)
        evaluation_mode = config_payload.get("evaluation_mode", evaluation_mode)
        if "allow_adb_bypass" in config_payload:
            allow_adb_bypass = config_payload.get("allow_adb_bypass")
        if "nanobot_max_steps" in config_payload:
            nanobot_max_steps = config_payload.get("nanobot_max_steps")
        if "nanobot_gui_task_max_steps" in config_payload:
            nanobot_gui_task_max_steps = config_payload.get("nanobot_gui_task_max_steps")
        if "nanobot_gui_task_max_calls" in config_payload:
            nanobot_gui_task_max_calls = config_payload.get("nanobot_gui_task_max_calls")
        if "nanobot_timeout_seconds" in config_payload:
            nanobot_timeout_seconds = config_payload.get("nanobot_timeout_seconds")
        if "nanobot_enable_planner" in config_payload:
            nanobot_enable_planner = config_payload.get("nanobot_enable_planner")
        if "nanobot_enable_router" in config_payload:
            nanobot_enable_router = config_payload.get("nanobot_enable_router")
        if "env_auto_recover" in config_payload:
            env_auto_recover = config_payload.get("env_auto_recover")
        if "env_recover_unhealthy_threshold" in config_payload:
            env_recover_unhealthy_threshold = config_payload.get("env_recover_unhealthy_threshold")
        judge_model = config_payload.get("judge_model", judge_model)
        judge_api_base = config_payload.get("judge_api_base", judge_api_base)
        judge_api_key = config_payload.get("judge_api_key", judge_api_key)
        if "skill_config" in config_payload:
            skill_config_payload = config_payload.get("skill_config")

    if skill_config_path:
        loaded_skill_config = load_framework_config(skill_config_path)
        skill_config_payload = loaded_skill_config.get("skill_config", loaded_skill_config)

    if isinstance(evaluation_mode, str):
        evaluation_mode = evaluation_mode.strip().lower()
    if evaluation_mode and evaluation_mode not in _ALLOWED_EVALUATION_MODES:
        raise ValueError(f"Invalid evaluation_mode: {evaluation_mode}")

    if framework_profile == "nanobot_opengui":
        nanobot_fork_path = nanobot_fork_path or _DEFAULT_NANOBOT_FORK_PATH
        gui_claw_path = gui_claw_path or _DEFAULT_GUI_CLAW_PATH
        evaluation_mode = evaluation_mode or "mixed"
        allow_adb_bypass = _normalize_bool(allow_adb_bypass, default=True)
        nanobot_max_steps = _normalize_positive_int(
            nanobot_max_steps,
            default=50,
            field_name="nanobot_max_steps",
        )
        nanobot_gui_task_max_steps = _normalize_positive_int(
            nanobot_gui_task_max_steps,
            default=50,
            field_name="nanobot_gui_task_max_steps",
        )
        nanobot_gui_task_max_calls = _normalize_positive_int(
            nanobot_gui_task_max_calls,
            default=3,
            field_name="nanobot_gui_task_max_calls",
        )
        nanobot_timeout_seconds = _normalize_positive_int(
            nanobot_timeout_seconds,
            default=None,
            field_name="nanobot_timeout_seconds",
        )
        nanobot_enable_planner = _normalize_bool(nanobot_enable_planner, default=False)
        nanobot_enable_router = _normalize_bool(
            nanobot_enable_router,
            default=False,
        )
        if not nanobot_enable_planner:
            nanobot_enable_router = False
        if not allow_adb_bypass:
            raise ValueError("nanobot_opengui requires allow_adb_bypass=true")
        if not nanobot_config_path:
            raise ValueError("nanobot_config_path is required when framework_profile=nanobot_opengui")
    else:
        evaluation_mode = evaluation_mode or "standard"
        allow_adb_bypass = _normalize_bool(allow_adb_bypass, default=False)
        if nanobot_max_steps is not None:
            nanobot_max_steps = _normalize_positive_int(
                nanobot_max_steps,
                default=None,
                field_name="nanobot_max_steps",
            )
        if nanobot_timeout_seconds is not None:
            nanobot_timeout_seconds = _normalize_positive_int(
                nanobot_timeout_seconds,
                default=None,
                field_name="nanobot_timeout_seconds",
            )
        if nanobot_gui_task_max_steps is not None:
            nanobot_gui_task_max_steps = _normalize_positive_int(
                nanobot_gui_task_max_steps,
                default=None,
                field_name="nanobot_gui_task_max_steps",
            )
        if nanobot_gui_task_max_calls is not None:
            nanobot_gui_task_max_calls = _normalize_positive_int(
                nanobot_gui_task_max_calls,
                default=None,
                field_name="nanobot_gui_task_max_calls",
            )
        nanobot_enable_planner = (
            _normalize_bool(nanobot_enable_planner, default=False)
            if nanobot_enable_planner is not None
            else None
        )
        nanobot_enable_router = (
            _normalize_bool(nanobot_enable_router, default=False)
            if nanobot_enable_router is not None
            else None
        )

    env_auto_recover = _normalize_bool(env_auto_recover, default=True)
    env_recover_unhealthy_threshold = _normalize_positive_int(
        env_recover_unhealthy_threshold,
        default=2,
        field_name="env_recover_unhealthy_threshold",
    )

    # Check if running all tasks
    run_all_tasks = args.task and args.task.upper() == "ALL"
    if run_all_tasks:
        final_tasks = []
        logger.info("Running ALL tasks with statistics generation")
    else:
        final_tasks = args.task.split(",") if args.task else []

    start_time = time.time() if run_all_tasks else None

    # Parse aw_host URLs - if None, will auto-discover; if provided, split by comma
    aw_urls = None if args.aw_host is None else args.aw_host.split(",")

    task_results, task_list_with_no_results = run_agent_with_evaluation(
        agent_type=args.agent_type,
        model_name=args.model_name,
        llm_base_url=args.llm_base_url,
        log_file_root=log_file_root,
        tasks=final_tasks,
        max_step=args.max_round or -1,
        aw_urls=aw_urls,
        api_key=args.api_key or os.getenv("API_KEY"),
        executor_llm_base_url=args.executor_llm_base_url,
        executor_model_name=args.executor_model_name,
        executor_agent_class=args.executor_agent_class,
        device=args.device or "emulator-5554",
        step_wait_time=args.step_wait_time or 1.0,
        suite_family=args.suite_family or "mobile_world",
        env_name_prefix=args.env_name_prefix,
        env_image=args.env_image,
        dry_run=args.dry_run,
        enable_mcp=args.enable_mcp,
        enable_user_interaction=args.enable_user_interaction,
        max_concurrency=args.max_concurrency,
        shuffle_tasks=args.shuffle_tasks,
        scale_factor=getattr(args, "scale_factor", 1000),
        auto_retry=args.auto_retry,
        skip_protocol_validation=getattr(args, "skip_protocol_validation", False),
        capability_policy_path=getattr(args, "capability_policy_path", None),
        mcp_tool_allowlist=getattr(args, "mcp_tool_allowlist", None),
        enable_trajectory_judge=getattr(args, "enable_trajectory_judge", False),
        judge_model=judge_model,
        judge_api_key=judge_api_key,
        judge_api_base=judge_api_base,
        framework_profile=framework_profile,
        nanobot_fork_path=nanobot_fork_path,
        nanobot_config_path=nanobot_config_path,
        gui_claw_path=gui_claw_path,
        evaluation_mode=evaluation_mode,
        allow_adb_bypass=allow_adb_bypass,
        nanobot_max_steps=nanobot_max_steps,
        nanobot_gui_task_max_steps=nanobot_gui_task_max_steps,
        nanobot_gui_task_max_calls=nanobot_gui_task_max_calls,
        nanobot_timeout_seconds=nanobot_timeout_seconds,
        nanobot_enable_planner=nanobot_enable_planner,
        nanobot_enable_router=nanobot_enable_router,
        env_auto_recover=env_auto_recover,
        env_recover_unhealthy_threshold=env_recover_unhealthy_threshold,
        skill_config=skill_config_payload,
    )
    task_names_for_manifest = sorted(
        {
            str(item.get("task_name"))
            for item in task_results
            if isinstance(item, dict) and item.get("task_name")
        }
        | {str(task_name) for task_name in task_list_with_no_results}
    )
    if not task_names_for_manifest:
        task_names_for_manifest = sorted({task for task in final_tasks if task})

    run_manifest_path = _write_run_manifest(
        run_root=log_file_root,
        framework_profile=framework_profile,
        evaluation_mode=evaluation_mode,
        allow_adb_bypass=bool(allow_adb_bypass),
        task_names=task_names_for_manifest,
        framework_config_path=framework_config_path,
        nanobot_fork_path=nanobot_fork_path,
        nanobot_config_path=nanobot_config_path,
        gui_claw_path=gui_claw_path,
        nanobot_max_steps=nanobot_max_steps,
        nanobot_gui_task_max_steps=nanobot_gui_task_max_steps,
        nanobot_gui_task_max_calls=nanobot_gui_task_max_calls,
        nanobot_timeout_seconds=nanobot_timeout_seconds,
        nanobot_enable_planner=nanobot_enable_planner,
        nanobot_enable_router=nanobot_enable_router,
        env_auto_recover=env_auto_recover,
        env_recover_unhealthy_threshold=env_recover_unhealthy_threshold,
        skill_config_path=skill_config_path,
        skill_config=skill_config_payload if isinstance(skill_config_payload, dict) else None,
    )
    logger.info("Run manifest written: {}", run_manifest_path)

    if run_all_tasks and task_results:
        total_duration = time.time() - start_time

        total_tasks = len(task_results)

        successful_tasks = sum(1 for result in task_results if result["score"] > 0.99)
        overall_success_rate = successful_tasks / total_tasks if total_tasks > 0 else 0.0

        report = {
            "summary": {
                "total_tasks_assigned": total_tasks + len(task_list_with_no_results),
                "total_tasks_with_results": total_tasks,
                "successful_tasks": successful_tasks,
                "total_tasks_with_no_results": len(task_list_with_no_results),
                "overall_success_rate": overall_success_rate,
                "total_duration_seconds": total_duration,
            },
            "metadata": {
                "agent_type": args.agent_type,
                "model_name": args.model_name,
                "timestamp": datetime.now().isoformat(),
                "log_file_root": log_file_root,
                "framework_profile": framework_profile,
                "evaluation_mode": evaluation_mode,
                "allow_adb_bypass": bool(allow_adb_bypass),
                "nanobot_max_steps": nanobot_max_steps,
                "nanobot_gui_task_max_steps": nanobot_gui_task_max_steps,
                "nanobot_gui_task_max_calls": nanobot_gui_task_max_calls,
                "nanobot_timeout_seconds": nanobot_timeout_seconds,
                "nanobot_enable_planner": nanobot_enable_planner,
                "nanobot_enable_router": nanobot_enable_router,
                "env_auto_recover": env_auto_recover,
                "env_recover_unhealthy_threshold": env_recover_unhealthy_threshold,
                "skill_config": skill_config_payload if isinstance(skill_config_payload, dict) else None,
                "run_manifest": str(run_manifest_path),
            },
            "tasks_with_results": task_results,
            "tasks_with_no_results": task_list_with_no_results,
        }

        output_path = Path(log_file_root)
        output_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = output_path / f"eval_report_{timestamp}.json"

        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Pretty print results using Rich
        console = Console()

        # Create summary panel
        summary_text = Text()
        summary_text.append("Evaluation Complete!\n\n", style="bold green")
        summary_text.append(f"Overall Success Rate: {overall_success_rate:.1%}\n", style="cyan")
        summary_text.append(
            f"Successful Tasks: {successful_tasks}/{total_tasks}\n", style="magenta"
        )
        summary_text.append(f"Total Duration: {total_duration:.1f} seconds\n", style="yellow")

        summary_panel = Panel(
            summary_text,
            title="[bold blue]📊 Evaluation Summary",
            border_style="blue",
            padding=(1, 2),
        )

        console.print(summary_panel)

        # Create detailed stats table
        stats_table = Table(
            title="[bold]📈 Detailed Statistics", show_header=True, header_style="bold blue"
        )
        stats_table.add_column("Metric", style="cyan", width=25)
        stats_table.add_column("Value", style="magenta", justify="right")

        stats_table.add_row("Total Tasks Assigned", str(report["summary"]["total_tasks_assigned"]))
        stats_table.add_row(
            "Tasks with Results", str(report["summary"]["total_tasks_with_results"])
        )
        stats_table.add_row("Successful Tasks", str(report["summary"]["successful_tasks"]))
        stats_table.add_row(
            "Tasks with No Results", str(report["summary"]["total_tasks_with_no_results"])
        )
        stats_table.add_row("Success Rate", f"{report['summary']['overall_success_rate']:.1%}")

        console.print(stats_table)

        # Create metadata panel
        metadata_text = Text()
        metadata_text.append(f"Agent Type: {report['metadata']['agent_type']}\n", style="green")
        metadata_text.append(f"Model: {report['metadata']['model_name'] or 'N/A'}\n", style="green")
        metadata_text.append(f"Timestamp: {report['metadata']['timestamp']}\n", style="green")
        metadata_text.append(f"Log Root: {report['metadata']['log_file_root']}\n", style="green")
        metadata_text.append(
            f"Framework Profile: {report['metadata'].get('framework_profile') or 'builtin'}\n",
            style="green",
        )
        metadata_text.append(
            f"Evaluation Mode: {report['metadata'].get('evaluation_mode')}\n",
            style="green",
        )
        metadata_text.append(
            f"Allow ADB Bypass: {report['metadata'].get('allow_adb_bypass')}\n",
            style="green",
        )

        metadata_panel = Panel(
            metadata_text, title="[bold]🔧 Configuration", border_style="green", padding=(1, 2)
        )

        console.print(metadata_panel)

        # Show task results if available
        if task_results:
            results_table = Table(
                title="[bold]📋 Task Results", show_header=True, header_style="bold magenta"
            )
            results_table.add_column("Task", style="cyan", width=30)
            results_table.add_column("Score", style="green", justify="center")
            results_table.add_column("Status", style="yellow", justify="center")

            for result in task_results:
                status = "✅ Success" if result["score"] > 0.99 else "❌ Failed"
                status_style = "green" if result["score"] > 0.99 else "red"
                results_table.add_row(
                    result.get("task_name", "Unknown"),
                    f"{result['score']:.3f}",
                    f"[{status_style}]{status}[/{status_style}]",
                )

            console.print(results_table)

        # Show tasks with no results if any
        if task_list_with_no_results:
            no_results_text = Text()
            no_results_text.append("Tasks with no results:\n", style="bold red")
            for task in task_list_with_no_results[:5]:  # Show first 5
                no_results_text.append(f"• {task}\n", style="red")
            if len(task_list_with_no_results) > 5:
                no_results_text.append(
                    f"... and {len(task_list_with_no_results) - 5} more", style="red"
                )

            no_results_panel = Panel(
                no_results_text,
                title="[bold red]⚠️  Tasks with No Results",
                border_style="red",
                padding=(1, 2),
            )
            console.print(no_results_panel)

        # File locations panel
        files_text = Text()
        files_text.append(f"Results JSON: {report_file}\n", style="blue")
        files_text.append(f"Run Manifest: {run_manifest_path}\n", style="blue")
        files_text.append(f"Trajectory Logs: {log_file_root}", style="blue")

        files_panel = Panel(
            files_text, title="[bold]💾 Output Files", border_style="cyan", padding=(1, 2)
        )

        console.print(files_panel)
