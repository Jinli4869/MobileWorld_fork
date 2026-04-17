import json
import os
import random
import threading
import time
from queue import Queue

from dotenv import load_dotenv
from joblib import Parallel, delayed
from loguru import logger

from mobile_world.agents.base import BaseAgent, MCPAgent
from mobile_world.agents.registry import create_agent, create_framework_adapter
from mobile_world.runtime.client import (
    AndroidEnvClient,
    AndroidMCPEnvClient,
    scan_finished_tasks,
)
from mobile_world.runtime.protocol.adapter import (
    AdapterFinalizeInput,
    AdapterInitializeInput,
    AdapterStepInput,
    FrameworkAdapter,
    is_terminal_action,
)
from mobile_world.runtime.protocol.capability_policy import resolve_capability_policy
from mobile_world.runtime.protocol.evaluator import (
    BaseEvaluator,
    EvaluatorInput,
    create_evaluator,
)
from mobile_world.runtime.protocol.metrics import MetricsCollector
from mobile_world.runtime.protocol.tool_router import UnifiedToolRouter
from mobile_world.runtime.protocol.validation import ProtocolValidationError, run_protocol_preflight
from mobile_world.runtime.utils.docker import (
    discover_backends,
)
from mobile_world.runtime.utils.models import ANSWER, UNKNOWN, JSONAction
from mobile_world.runtime.utils.trajectory_logger import METRICS_FILE_NAME, TrajLogger

load_dotenv()


def _execute_single_task(
    env: AndroidEnvClient,
    agent: BaseAgent | None,
    task_name: str,
    max_step: int,
    traj_logger: TrajLogger,
    tool_router: UnifiedToolRouter | None = None,
    enable_mcp: bool = False,
    evaluator: BaseEvaluator | None = None,
    framework_adapter: FrameworkAdapter | None = None,
    framework_options: dict | None = None,
) -> tuple[int, float]:
    """Execute a single task and return the number of steps and score.

    Returns:
        tuple[int, float]: (number of steps, score)
    """

    logger.debug(f"max_step: {max_step}")

    if enable_mcp and framework_adapter is None and not isinstance(agent, MCPAgent):
        logger.error(
            "MCP is enabled but agent type is not a MCP agent. Please use a MCP agent type."
        )

    if enable_mcp:
        traj_logger.log_tools(env.tools)
    task_goal = env.get_task_goal(task_type=task_name)

    logger.debug(f"task_goal: {task_goal}")

    run_id = f"{task_name}-0"
    step = 0
    obs = env.initialize_task(task_name=task_name)
    if framework_adapter is None:
        if agent is None:
            raise ValueError("agent must be provided when framework_adapter is not set")
        agent.initialize(task_goal)
    else:
        adapter_options = dict(framework_options or {})
        adapter_options.setdefault("output_dir", traj_logger.log_file_dir)
        init_result = framework_adapter.initialize(
            AdapterInitializeInput(
                task_name=task_name,
                task_goal=task_goal,
                run_id=run_id,
                options=adapter_options,
            )
        )
        if not init_result.ok:
            raise RuntimeError(f"Framework adapter initialize failed: {init_result.message}")
    metrics_collector = MetricsCollector(
        task_name=task_name,
        run_id=run_id,
        task_started_at=time.perf_counter(),
    )

    while True:
        step += 1
        step_started_at = time.perf_counter()

        logger.debug(f"Screenshot captured in step {step}")

        adapter_done = False
        observation_payload = {
            "screenshot": obs.screenshot,
            "tool_call": obs.tool_call,
            "ask_user_response": obs.ask_user_response,
        }
        if framework_adapter is not None:
            step_result = framework_adapter.step(
                AdapterStepInput(
                    run_id=run_id,
                    task_name=task_name,
                    step_index=step,
                    observation=observation_payload,
                )
            )
            prediction = step_result.prediction
            adapter_done = step_result.done
            action_dict = step_result.action if isinstance(step_result.action, dict) else {}
            try:
                action = JSONAction(**action_dict)
            except Exception:
                action = JSONAction(action_type=UNKNOWN)
            action_payload = action.model_dump(exclude_none=True)
            adapter_token_usage = None
            if isinstance(step_result.info, dict):
                token_candidate = step_result.info.get("token_usage")
                if isinstance(token_candidate, dict):
                    adapter_token_usage = token_candidate
            total_token_usage = adapter_token_usage
        else:
            assert agent is not None
            prediction, action = agent.predict(observation_payload)  # for backward compatibility
            action_payload = action.model_dump(exclude_none=True)
            total_token_usage = agent.get_total_token_usage()
        prediction_done_at = time.perf_counter()
        if total_token_usage is None:
            total_token_usage = {
                "completion_tokens": 0,
                "prompt_tokens": 0,
                "cached_tokens": 0,
                "total_tokens": 0,
            }
        step_preview = metrics_collector.preview_step(
            step=step,
            action_type=action.action_type,
            step_started_at=step_started_at,
            prediction_done_at=prediction_done_at,
            total_usage=total_token_usage,
        )
        traj_logger.log_traj(
            task_name,
            task_goal,
            step,
            prediction,
            action_payload,
            obs,
            total_token_usage,
            step_info={
                "step_token_usage": step_preview["token_usage_step"],
                "predict_latency_ms": step_preview["predict_latency_ms"],
            },
        )
        if prediction is None:
            logger.warning(f"Agent prediction failed in step {step}")
            step_metrics = metrics_collector.complete_step(
                step_preview=step_preview,
                step_finished_at=time.perf_counter(),
                tool_latency_ms=None,
                tool_attempted=False,
                tool_success=False,
                tool_retry=False,
                invalid_action=True,
            )
            traj_logger.log_step_metrics(step=step, metrics=step_metrics)
            break

        terminate = False
        tool_latency_ms = None
        tool_attempted = False
        tool_success = False
        tool_retry = False
        invalid_action = action.action_type in [UNKNOWN, None]
        logger.debug(f"current step {step}")

        if is_terminal_action(action.action_type) and action.action_type != ANSWER:
            logger.debug(f"task terminated in step {step} with action {action.action_type}")
            terminate = True
        else:
            logger.debug(f"execution action {action}")
            tool_attempted = True
            dispatch_started_at = time.perf_counter()
            if tool_router is not None:
                dispatch_result = tool_router.dispatch(env, action)
                tool_latency_ms = round((time.perf_counter() - dispatch_started_at) * 1000.0, 3)
                if not dispatch_result.ok:
                    normalized_error = dispatch_result.error.model_dump() if dispatch_result.error else {}
                    traj_logger.log_tool_error(step=step, error=normalized_error)
                    logger.warning(
                        "Tool dispatch failed at step {} with error {}",
                        step,
                        normalized_error,
                    )
                    tool_success = False
                    tool_retry = bool(dispatch_result.error and dispatch_result.error.retryable)
                    terminate = True
                else:
                    tool_success = True
                    if dispatch_result.observation is not None:
                        obs = dispatch_result.observation
            else:
                obs = env.execute_action(action)
                tool_latency_ms = round((time.perf_counter() - dispatch_started_at) * 1000.0, 3)
                tool_success = True
            if action.action_type in [ANSWER]:
                terminate = True
            if framework_adapter is not None and adapter_done:
                terminate = True
        step_metrics = metrics_collector.complete_step(
            step_preview=step_preview,
            step_finished_at=time.perf_counter(),
            tool_latency_ms=tool_latency_ms,
            tool_attempted=tool_attempted,
            tool_success=tool_success,
            tool_retry=tool_retry,
            invalid_action=invalid_action,
        )
        traj_logger.log_step_metrics(step=step, metrics=step_metrics)
        if terminate:
            break

        if step >= max_step:
            logger.debug("task steps reach max step, terminate")
            break

    if evaluator is None:
        evaluator = create_evaluator("task_native")
    evaluation_result = evaluator.evaluate(
        env,
        EvaluatorInput(
            task_name=task_name,
            task_goal=task_goal,
            run_id=run_id,
            artifact_paths=traj_logger.artifact_paths(),
            metadata={"max_step": max_step, "enable_mcp": enable_mcp},
        ),
    )
    metrics_summary, _ = metrics_collector.finalize(score_recorded_at=time.perf_counter())
    traj_logger.log_metrics_summary(task_name=task_name, run_id=run_id, summary=metrics_summary)
    logger.debug(f"task_score: {evaluation_result.score}, reason: {evaluation_result.reason}")
    traj_logger.log_evaluator_audit(evaluation_result.audit.model_dump())
    traj_logger.log_score(
        score=evaluation_result.score,
        reason=evaluation_result.reason,
        evaluator_name=evaluation_result.evaluator_name,
        evidence_refs=[ref.model_dump() for ref in evaluation_result.evidence_refs],
    )
    if framework_adapter is not None:
        finalize_result = framework_adapter.finalize(
            AdapterFinalizeInput(
                run_id=run_id,
                task_name=task_name,
                score=evaluation_result.score,
                reason=evaluation_result.reason,
                metrics=metrics_summary,
            )
        )
        if not finalize_result.ok:
            logger.warning("Framework adapter finalize returned non-ok for task {}", task_name)
        artifacts = framework_adapter.emit_artifacts(run_id=run_id, output_dir=traj_logger.log_file_dir)
        if artifacts.artifacts:
            traj_logger.log_adapter_artifacts([item.model_dump() for item in artifacts.artifacts])

    res = env.tear_down_task(task_type=task_name)
    if agent is not None:
        agent.done()
    logger.debug(f"tear_down_task response: {res}")

    return step, evaluation_result.score


def _process_task_on_env(
    task_name: str,
    env_queue: Queue,
    agent_type: str,
    model_name: str,
    llm_base_url: str,
    api_key: str | None,
    log_file_root: str,
    max_step: int,
    retry_on_device_unhealthy: int = 2,
    enable_mcp: bool = False,
    enable_user_interaction: bool = False,
    capability_policy_path: str | None = None,
    mcp_tool_allowlist: str | list[str] | None = None,
    enable_trajectory_judge: bool = False,
    judge_model: str = "qwen3-vl-plus",
    judge_api_key: str | None = None,
    judge_api_base: str | None = None,
    framework_profile: str | None = None,
    nanobot_fork_path: str | None = None,
    **kwargs,
) -> dict:
    """Process a single task on a specific environment.

    Args:
        task_name: Name of the task to execute
        env_url: URL of the environment to use
        agent_type: Type of agent to create
        model_name: Model name for the agent
        llm_base_url: LLM service base URL
        api_key: API key for LLM service
        log_file_root: Root directory for log files
        max_step: Maximum steps for task execution
        **kwargs: Additional kwargs for agent creation

    Returns:
        dict: Task result containing task_name, success, score, steps, duration_seconds
    """
    # Create thread-specific log file
    thread_id = threading.current_thread().ident
    thread_log_file = os.path.join(log_file_root, task_name, f"thread_{thread_id}.log")
    os.makedirs(os.path.dirname(thread_log_file), exist_ok=True)
    traj_logger = TrajLogger(log_file_root, task_name)

    def thread_filter(record):
        return record["extra"].get("thread_id") == thread_id

    thread_handler_id = logger.add(
        thread_log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | container: {extra[container_name]} | {message}",
        level="DEBUG",
        enqueue=True,
        filter=thread_filter,
    )
    env, container_name = env_queue.get()

    try:
        with logger.contextualize(thread_id=thread_id, container_name=container_name):
            logger.info("Processing task '{}' on environment {}", task_name, env.base_url)

            policy_path = capability_policy_path
            allowlist_override = mcp_tool_allowlist
            if isinstance(allowlist_override, str):
                allowlist_override = [
                    token.strip() for token in allowlist_override.split(",") if token.strip()
                ]

            task_tags: list[str] = []
            try:
                task_metadata = env.get_task_metadata(task_type=task_name)
                task_tags = task_metadata.get("tags", [])
            except Exception:
                logger.exception("Failed to load task metadata for capability policy")

            effective_policy_profile = framework_profile or agent_type

            capability_decision = resolve_capability_policy(
                task_tags=task_tags,
                profile_name=effective_policy_profile,
                enable_mcp=enable_mcp,
                enable_user_interaction=enable_user_interaction,
                policy_path=policy_path,
                mcp_allowlist_override=allowlist_override,
            )
            capability_manifest = capability_decision.as_manifest()

            if enable_mcp:
                assert isinstance(env, AndroidMCPEnvClient), (
                    f"env must be a AndroidMCPEnvClient, but got {type(env)}"
                )
                try:
                    env.set_mcp_timeout(capability_decision.mcp_timeout_seconds)
                    env.reset_tools(
                        task_type=task_name,
                        allowlist=capability_decision.enabled_mcp_tools,
                    )
                except Exception as e:
                    logger.exception(f"Error resetting tools for task {task_name}: {e}")
                    return None
                traj_logger.log_tools(env.tools)

            traj_logger.log_tool_manifest(capability_manifest)
            traj_logger.log_policy_manifest(capability_manifest)
            tool_router = UnifiedToolRouter(capability_decision)
            evaluator = create_evaluator(
                "task_native",
                enable_trajectory_judge=enable_trajectory_judge,
                judge_model=judge_model,
                judge_api_key=judge_api_key,
                judge_api_base=judge_api_base,
            )

            framework_adapter: FrameworkAdapter | None = None
            agent: BaseAgent | None = None
            framework_options: dict | None = None
            if framework_profile:
                framework_adapter = create_framework_adapter(
                    framework_profile,
                    model_name=model_name,
                    llm_base_url=llm_base_url,
                    api_key=api_key,
                    env=env,
                    nanobot_fork_path=nanobot_fork_path,
                    **kwargs,
                )
                framework_options = {
                    "nanobot_fork_path": nanobot_fork_path,
                }
            else:
                agent = create_agent(agent_type, model_name, llm_base_url, api_key, env=env, **kwargs)

            task_start_time = time.time()
            while True:
                try:
                    task_steps, task_score = _execute_single_task(
                        env,
                        agent,
                        task_name,
                        max_step,
                        traj_logger=traj_logger,
                        tool_router=tool_router,
                        enable_mcp=enable_mcp,
                        evaluator=evaluator,
                        framework_adapter=framework_adapter,
                        framework_options=framework_options,
                    )
                    break
                except Exception as e:
                    if "Device is not healthy" in str(e) and retry_on_device_unhealthy > 0:
                        logger.warning("Device is not healthy, retrying...")
                        time.sleep(20)
                        retry_on_device_unhealthy -= 1
                        traj_logger.reset_traj()
                        continue
                    else:
                        logger.exception(f"Error executing task {task_name}")
                        return None

            task_duration = time.time() - task_start_time
            task_success = task_score > 0.0

            logger.info(
                "Task '{}' completed on {}: success={}, score={}, steps={}, duration={:.1f}s",
                task_name,
                env.base_url,
                task_success,
                task_score,
                task_steps,
                task_duration,
            )

            return {
                "task_name": task_name,
                "score": task_score,
            }
    finally:
        # Remove the thread-specific handler
        logger.remove(thread_handler_id)
        env_queue.put((env, container_name))


def _init_env(
    env_url: str, device: str, step_wait_time: float, suite_family: str, enable_mcp: bool
) -> AndroidEnvClient:
    """Initialize the environment."""
    if enable_mcp:
        env = AndroidMCPEnvClient(env_url, device, step_wait_time=step_wait_time)
    else:
        env = AndroidEnvClient(env_url, device, step_wait_time=step_wait_time)
    env.switch_suite_family(suite_family)
    return env


def run_agent_with_evaluation(
    agent_type: str,
    model_name: str,
    llm_base_url: str,
    log_file_root: str,
    tasks: list[str],
    max_step: int = -1,
    aw_urls: list[str] | None = None,
    api_key: str | None = None,
    device: str = "emulator-5554",
    step_wait_time: float = 1.0,
    suite_family: str = "mobile_world",
    env_name_prefix: str = "mobile_world_env",
    env_image: str = "mobile_world",
    dry_run: bool = False,
    enable_mcp: bool = False,
    enable_user_interaction: bool = False,
    max_concurrency: int | None = None,
    shuffle_tasks: bool = False,
    auto_retry: int = 10,
    skip_protocol_validation: bool = False,
    capability_policy_path: str | None = None,
    mcp_tool_allowlist: str | None = None,
    enable_trajectory_judge: bool = False,
    judge_model: str = "qwen3-vl-plus",
    judge_api_key: str | None = None,
    judge_api_base: str | None = None,
    framework_profile: str | None = None,
    nanobot_fork_path: str | None = None,
    **kwargs,
) -> list[dict]:
    """Run the agent and return the evaluation results.

    Args:
        agent_type: Type of agent to use
        model_name: Model name for the agent
        llm_base_url: LLM service base URL
        log_file_root: Root directory for log files
        tasks: List of task names to execute (empty list for all tasks)
        max_step: Maximum steps for task execution
        aw_urls: List of Android World backend URLs. If None, auto-discover from containers
        api_key: API key for LLM service
        device: Android device ID
        step_wait_time: Wait time after each step
        suite_family: Suite family to use
        **kwargs: Additional kwargs for agent creation

    Returns:
        list[dict]: The evaluation results for each task, containing task_name, success, score, steps, duration_seconds, env_url
    """

    if skip_protocol_validation:
        logger.warning("Protocol pre-flight validation explicitly skipped by CLI flag")
    else:
        try:
            validation_report = run_protocol_preflight(strict=True)
        except ProtocolValidationError:
            logger.exception("Protocol pre-flight validation failed")
            raise
        logger.info(
            "Protocol pre-flight passed. Checked adapters: {}",
            validation_report.checked_adapters,
        )

    container_names = None
    if aw_urls is None or len(aw_urls) == 0:
        logger.info("No backend URLs specified, auto-discovering from containers...")
        aw_urls, container_names = discover_backends(image_filter=env_image, prefix=env_name_prefix)
        logger.info("Container names: {}", container_names)
        if not aw_urls:
            logger.error("No backend URLs found. Please start containers or specify --aw-host")
            return [], []

    logger.info("Using {} backend URL(s): {}", len(aw_urls), aw_urls)

    envs = Parallel(
        n_jobs=min(max_concurrency if max_concurrency is not None else len(aw_urls), len(aw_urls)),
        backend="threading",
    )(
        delayed(_init_env)(env_url, device, step_wait_time, suite_family, enable_mcp)
        for env_url in aw_urls
    )

    if len(tasks) != 0:
        task_list = tasks
    else:
        task_list = envs[0].get_suite_task_list(enable_mcp=enable_mcp, enable_user_interaction=enable_user_interaction)

    logger.info("Task list: {} ({} tasks)", task_list, len(task_list))

    num_envs = len(envs)
    max_attempts = min(1 + auto_retry, 10)  # Cap at 10 to prevent infinite loops

    for attempt in range(max_attempts):
        # Scan finished tasks each iteration (picks up results from previous attempts)
        finished_task_list, finished_scores = scan_finished_tasks(log_file_root, task_list)
        logger.info("Finished task list: {} ({} tasks)", finished_task_list, len(finished_task_list))

        pending_tasks = [task for task in task_list if task not in finished_task_list]
        logger.info(
            "Attempt {}/{}: {} remaining tasks to execute",
            attempt + 1, max_attempts, len(pending_tasks),
        )

        if not pending_tasks:
            logger.info("All tasks finished, no retry needed")
            break

        env_queue = Queue[tuple[AndroidEnvClient, str | None]](maxsize=num_envs)
        for i, env in enumerate(envs):
            env_queue.put((env, container_names[i] if container_names else None))

        if shuffle_tasks:
            random.shuffle(pending_tasks)

        if not dry_run:
            task_results = Parallel(
                n_jobs=min(max_concurrency if max_concurrency is not None else num_envs, num_envs),
                backend="threading",
            )(
                delayed(_process_task_on_env)(
                    task_name=task_name,
                    env_queue=env_queue,
                    agent_type=agent_type,
                    model_name=model_name,
                    llm_base_url=llm_base_url,
                    api_key=api_key,
                    log_file_root=log_file_root,
                    max_step=max_step,
                    enable_mcp=enable_mcp,
                    enable_user_interaction=enable_user_interaction,
                    capability_policy_path=capability_policy_path,
                    mcp_tool_allowlist=mcp_tool_allowlist,
                    enable_trajectory_judge=enable_trajectory_judge,
                    judge_model=judge_model,
                    judge_api_key=judge_api_key,
                    judge_api_base=judge_api_base,
                    framework_profile=framework_profile,
                    nanobot_fork_path=nanobot_fork_path,
                    **kwargs,
                )
                for task_name in pending_tasks
            )
        else:
            logger.info("Dry run mode, skipping task execution")
            task_results = []
            break

        # Identify failed tasks for potential retry
        failed_this_round = [
            task_name for task_name, task_result in zip(pending_tasks, task_results)
            if task_result is None
        ]

        logger.info(
            "Attempt {}/{} done: {} succeeded, {} failed/stale",
            attempt + 1, max_attempts,
            len(pending_tasks) - len(failed_this_round), len(failed_this_round),
        )

        if not failed_this_round or attempt >= max_attempts - 1:
            break

        logger.info("Auto-retrying {} failed tasks (retry {}/{})", len(failed_this_round), attempt + 1, auto_retry)

    # Final scan to get all finished results (including from retries)
    finished_task_list, finished_scores = scan_finished_tasks(log_file_root, task_list)
    # Build final results from scan (authoritative source)
    success_task_results = []
    for task_name, score in zip(finished_task_list, finished_scores):
        metrics_summary = None
        metrics_path = os.path.join(log_file_root, task_name, METRICS_FILE_NAME)
        if os.path.exists(metrics_path):
            try:
                with open(metrics_path, encoding="utf-8") as f:
                    metrics_summary = json.load(f)
            except Exception:
                logger.exception("Failed to parse metrics summary for task {}", task_name)
        success_task_results.append(
            {
                "task_name": task_name,
                "score": score,
                "metrics": metrics_summary,
            }
        )

    task_list_with_no_results = [task for task in task_list if task not in finished_task_list]
    logger.info(f"Final: {len(success_task_results)} tasks with results, {len(task_list_with_no_results)} with no results")

    return (success_task_results, task_list_with_no_results)
