#!/usr/bin/env python3
"""Extract OpenGUI skills from nanobot mixed GUI trace logs.

The input is one or more MobileWorld/nanobot run roots that contain
``nanobot_gui_task_runs/**/trace_*.jsonl`` files. Skills are written to the
OpenGUI skill store used by nanobot's GUI tool, usually:

    /home/jinli/Project/MobileWorld_fork/gui_skills
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_NANOBOT_ROOT = Path("/home/jinli/Project/nanobot_fork")
DEFAULT_STORE_ROOT = Path("/home/jinli/Project/MobileWorld_fork/gui_skills")
DEFAULT_MODEL = "qwen3.5-397b-a17b"
DEFAULT_CONCURRENCY = 4


@dataclass
class TraceOutcome:
    trace: Path
    processed: int = 0
    skipped: int = 0
    extracted: int = 0
    errors: int = 0


@dataclass(frozen=True)
class TracePlan:
    trace: Path
    existing_status: str
    should_process: bool


def _parse_json_object(raw: str | None, *, arg_name: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{arg_name} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit(f"{arg_name} must decode to a JSON object")
    return parsed


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _default_base_url() -> str:
    raw = (
        os.getenv("MA_INTRANET_URL")
        or os.getenv("MA_INTRANE_URL")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ).rstrip("/")
    return raw if raw.endswith("/v1") else f"{raw}/v1"


def _load_result_event(trace_path: Path) -> dict[str, Any] | None:
    result: dict[str, Any] | None = None
    try:
        with trace_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict) and event.get("type") == "result":
                    result = event
    except OSError:
        return None
    return result


def _is_abnormal(result_event: dict[str, Any] | None) -> bool:
    if not result_event:
        return False
    error = result_event.get("error")
    total_steps = result_event.get("total_steps") or 0
    if total_steps == 0 and error:
        return True
    if not isinstance(error, str):
        return False
    abnormal_prefixes = (
        "stagnation_detected",
        "step_timeout",
        "intervention_cancelled",
    )
    return any(error == prefix or error.startswith(prefix + ":") for prefix in abnormal_prefixes)


def _iter_trace_paths(roots: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    paths: list[Path] = []
    for root in roots:
        for path in root.expanduser().resolve().glob("**/nanobot_gui_task_runs/**/trace_*.jsonl"):
            if path.name == "trace.jsonl":
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            paths.append(resolved)
    return sorted(paths)


def _task_name_for_trace(trace_path: Path) -> str:
    for parent in trace_path.parents:
        if parent.name == "nanobot_gui_task_runs":
            return parent.parent.name
    return trace_path.parent.name


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_extraction_status(result_path: Path) -> str | None:
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "<unreadable>"
    if not isinstance(data, dict):
        return "<invalid>"
    status = data.get("status")
    return str(status) if status is not None else "<missing>"


def _parse_status_filter(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def _plan_trace_work(
    traces: list[Path],
    *,
    overwrite: bool,
    overwrite_statuses: set[str],
) -> tuple[list[TracePlan], Counter[str], Counter[str], Counter[str]]:
    plans: list[TracePlan] = []
    status_counts: Counter[str] = Counter()
    process_status_counts: Counter[str] = Counter()
    skip_status_counts: Counter[str] = Counter()

    for trace in traces:
        result_path = trace.parent / "extraction_result.json"
        if result_path.exists():
            existing_status = _load_extraction_status(result_path) or "<missing>"
        else:
            existing_status = "<missing_result>"

        should_process = (
            not result_path.exists()
            or overwrite
            or (bool(overwrite_statuses) and existing_status in overwrite_statuses)
        )
        status_counts[existing_status] += 1
        if should_process:
            process_status_counts[existing_status] += 1
        else:
            skip_status_counts[existing_status] += 1
        plans.append(
            TracePlan(
                trace=trace,
                existing_status=existing_status,
                should_process=should_process,
            )
        )

    return plans, status_counts, process_status_counts, skip_status_counts


@contextmanager
def _make_progress(
    enabled: bool,
    task_count: int,
    trace_count: int,
    *,
    initial_tasks: int = 0,
    initial_traces: int = 0,
):
    if not enabled:
        yield (None, None, None)
        return

    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task_progress = progress.add_task("Tasks", total=task_count, completed=initial_tasks)
        trace_progress = progress.add_task("Traces", total=trace_count, completed=initial_traces)
        yield (progress, task_progress, trace_progress)


async def _run(args: argparse.Namespace) -> int:
    nanobot_root = Path(args.nanobot_root).expanduser().resolve()
    if not nanobot_root.exists():
        raise SystemExit(f"nanobot root not found: {nanobot_root}")
    sys.path.insert(0, str(nanobot_root))

    from openai import AsyncOpenAI
    from opengui.cli import _coerce_message_content, _parse_tool_arguments, _sanitize_messages
    from opengui.interfaces import LLMResponse, ToolCall
    from opengui.skills.extractor import SkillExtractor
    from opengui.skills.library import SkillLibrary

    roots = [Path(item) for item in args.run_root]
    traces = _iter_trace_paths(roots)
    if args.limit is not None:
        traces = traces[: args.limit]

    task_totals = Counter(_task_name_for_trace(trace) for trace in traces)
    task_done: defaultdict[str, int] = defaultdict(int)

    def mark_trace_done(progress: Any, task_progress: Any, trace_progress: Any, trace: Path) -> None:
        if progress is None:
            return
        task_name = _task_name_for_trace(trace)
        task_done[task_name] += 1
        progress.advance(trace_progress)
        if task_done[task_name] >= task_totals[task_name]:
            progress.advance(task_progress)

    if args.dry_run:
        progress_context = _make_progress(not args.no_progress, len(task_totals), len(traces))
        with progress_context as progress_tuple:
            progress, task_progress, trace_progress = progress_tuple
            for trace in traces:
                result = _load_result_event(trace)
                print(
                    json.dumps(
                        {
                            "trace": str(trace),
                            "task": _task_name_for_trace(trace),
                            "success": bool((result or {}).get("success", False)),
                            "error": (result or {}).get("error"),
                            "abnormal": _is_abnormal(result),
                        },
                        ensure_ascii=False,
                    )
                )
                mark_trace_done(progress, task_progress, trace_progress, trace)
        print(f"dry_run_traces={len(traces)}")
        print(f"dry_run_tasks={len(task_totals)}")
        return 0

    api_key = args.api_key or os.getenv("MA_TOKEN") or os.getenv("API_KEY") or ""
    if not api_key:
        raise SystemExit("missing API key: set MA_TOKEN or pass --api-key")
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be >= 1")
    if args.max_screenshots < 1:
        raise SystemExit("--max-screenshots must be >= 1; use --no-screenshots for text-only extraction")
    overwrite_statuses = _parse_status_filter(args.overwrite_status)
    trace_plans, status_counts, process_status_counts, skip_status_counts = _plan_trace_work(
        traces,
        overwrite=args.overwrite,
        overwrite_statuses=overwrite_statuses,
    )
    work_traces = [plan.trace for plan in trace_plans if plan.should_process]
    skipped_traces = [plan.trace for plan in trace_plans if not plan.should_process]
    task_done = defaultdict(int)
    for trace in skipped_traces:
        task_done[_task_name_for_trace(trace)] += 1
    initial_tasks = sum(
        1
        for task_name, total in task_totals.items()
        if task_done[task_name] >= total
    )
    progress_context = _make_progress(
        not args.no_progress,
        len(task_totals),
        len(traces),
        initial_tasks=initial_tasks,
        initial_traces=len(skipped_traces),
    )

    scan_summary = {
        "traces": len(traces),
        "tasks": len(task_totals),
        "to_process": len(work_traces),
        "pre_skipped": len(skipped_traces),
        "existing_status_counts": dict(sorted(status_counts.items())),
        "process_status_counts": dict(sorted(process_status_counts.items())),
        "skip_status_counts": dict(sorted(skip_status_counts.items())),
        "overwrite": args.overwrite,
        "overwrite_statuses": sorted(overwrite_statuses),
    }
    print(json.dumps({"scan": scan_summary}, ensure_ascii=False, indent=2), flush=True)

    base_url = args.base_url or _default_base_url()
    extra_body = _parse_json_object(args.extra_body, arg_name="--extra-body")
    if args.disable_thinking:
        extra_body = _deep_merge_dict(
            {"chat_template_kwargs": {"enable_thinking": False}},
            extra_body,
        )

    class ScriptOpenAICompatibleLLMProvider:
        """OpenAI-compatible chat bridge with optional streaming aggregation."""

        def __init__(self) -> None:
            self._model = args.model
            self._client = AsyncOpenAI(api_key=api_key or "no-key", base_url=base_url)

        async def chat(
            self,
            messages: list[dict[str, Any]],
            tools: list[dict[str, Any]] | None = None,
            tool_choice: str | None = None,
            model: str | None = None,
            max_tokens: int | None = None,
        ) -> LLMResponse:
            request_kwargs: dict[str, Any] = {
                "model": model or self._model,
                "messages": _sanitize_messages(messages),
            }
            if tools:
                request_kwargs["tools"] = tools
                request_kwargs["tool_choice"] = tool_choice or "auto"
            if max_tokens is not None:
                request_kwargs["max_tokens"] = max_tokens
            if extra_body:
                request_kwargs["extra_body"] = extra_body
            if args.stream:
                return await self._chat_streaming(request_kwargs)
            return await self._chat_non_streaming(request_kwargs)

        async def _chat_non_streaming(self, request_kwargs: dict[str, Any]) -> LLMResponse:
            started = time.monotonic()
            response = await self._client.chat.completions.create(**request_kwargs)
            latency_s = time.monotonic() - started
            if not response.choices:
                raise RuntimeError("OpenAI-compatible API returned no choices")

            message = response.choices[0].message
            parsed_tool_calls: list[ToolCall] = []
            for index, tool_call in enumerate(message.tool_calls or []):
                parsed_tool_calls.append(
                    ToolCall(
                        id=tool_call.id or f"tool-call-{index}",
                        name=tool_call.function.name,
                        arguments=_parse_tool_arguments(tool_call.function.arguments),
                    )
                )

            usage_obj = getattr(response, "usage", None)
            usage = _usage_to_dict(usage_obj)
            return LLMResponse(
                content=_coerce_message_content(message.content),
                tool_calls=parsed_tool_calls or None,
                raw=response,
                usage=usage,
                latency_s=latency_s,
            )

        async def _chat_streaming(self, request_kwargs: dict[str, Any]) -> LLMResponse:
            started = time.monotonic()
            stream = await self._client.chat.completions.create(
                **request_kwargs,
                stream=True,
            )
            content_parts: list[str] = []
            tool_call_parts: dict[int, dict[str, Any]] = {}
            usage: dict[str, int] = {}
            raw_chunks: list[Any] = []
            ttft_s: float | None = None

            async for chunk in stream:
                raw_chunks.append(chunk)
                usage_obj = getattr(chunk, "usage", None)
                if usage_obj is not None:
                    usage = _usage_to_dict(usage_obj)
                for choice in getattr(chunk, "choices", []) or []:
                    delta = getattr(choice, "delta", None)
                    if delta is None:
                        continue
                    delta_content = getattr(delta, "content", None)
                    if delta_content:
                        if ttft_s is None:
                            ttft_s = time.monotonic() - started
                        content_parts.append(delta_content)
                    for tool_delta in getattr(delta, "tool_calls", None) or []:
                        if ttft_s is None:
                            ttft_s = time.monotonic() - started
                        index = getattr(tool_delta, "index", None)
                        if index is None:
                            index = len(tool_call_parts)
                        part = tool_call_parts.setdefault(
                            index,
                            {"id": None, "name": "", "arguments": ""},
                        )
                        if getattr(tool_delta, "id", None):
                            part["id"] = tool_delta.id
                        function_delta = getattr(tool_delta, "function", None)
                        if function_delta is not None:
                            if getattr(function_delta, "name", None):
                                part["name"] += function_delta.name
                            if getattr(function_delta, "arguments", None):
                                part["arguments"] += function_delta.arguments

            parsed_tool_calls = [
                ToolCall(
                    id=part["id"] or f"tool-call-{index}",
                    name=part["name"],
                    arguments=_parse_tool_arguments(part["arguments"]),
                )
                for index, part in sorted(tool_call_parts.items())
                if part["name"]
            ]
            return LLMResponse(
                content="".join(content_parts),
                tool_calls=parsed_tool_calls or None,
                raw=raw_chunks,
                usage=usage,
                ttft_s=ttft_s,
                latency_s=time.monotonic() - started,
            )

    def _usage_to_dict(usage_obj: Any) -> dict[str, int]:
        if usage_obj is None:
            return {}
        return {
            "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage_obj, "completion_tokens", 0) or 0,
            "total_tokens": getattr(usage_obj, "total_tokens", 0) or 0,
        }

    def make_llm() -> ScriptOpenAICompatibleLLMProvider:
        return ScriptOpenAICompatibleLLMProvider()

    library = SkillLibrary(store_dir=Path(args.store_root).expanduser().resolve(), merge_llm=make_llm())
    library_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(args.concurrency)

    async def process_trace(trace: Path) -> TraceOutcome:
        async with semaphore:
            outcome = TraceOutcome(trace=trace)
            try:
                result_path = trace.parent / "extraction_result.json"
                if result_path.exists() and not args.overwrite:
                    existing_status = _load_extraction_status(result_path)
                    if not overwrite_statuses or existing_status not in overwrite_statuses:
                        outcome.skipped = 1
                        return outcome
                result = _load_result_event(trace)
                if _is_abnormal(result) and not args.include_abnormal:
                    outcome.skipped = 1
                    _write_json(
                        result_path,
                        {
                            "status": "skipped_abnormal",
                            "trace": str(trace),
                            "reason": (result or {}).get("error"),
                            "timestamp": time.time(),
                        },
                    )
                    return outcome
                is_success = bool((result or {}).get("success", False))
                started = time.monotonic()
                extractor = SkillExtractor(
                    llm=make_llm(),
                    include_screenshots=not args.no_screenshots,
                    max_screenshots=args.max_screenshots,
                )
                skill = await extractor.extract_from_file(trace, is_success=is_success)
                _write_json(trace.parent / "extraction_usage.json", extractor.total_usage)
                duration_s = time.monotonic() - started
                outcome.processed = 1
                if skill is None:
                    _write_json(
                        result_path,
                        {
                            "status": "no_candidate",
                            "trace": str(trace),
                            "is_success": is_success,
                            "duration_s": duration_s,
                            "stream": args.stream,
                            "include_screenshots": not args.no_screenshots,
                            "max_screenshots": args.max_screenshots,
                            "timestamp": time.time(),
                        },
                    )
                    return outcome
                async with library_lock:
                    decision, final_id = await library.add_or_merge(skill)
                outcome.extracted = 1
                _write_json(
                    result_path,
                    {
                        "status": "processed",
                        "decision": decision,
                        "trace": str(trace),
                        "is_success": is_success,
                        "duration_s": duration_s,
                        "stream": args.stream,
                        "include_screenshots": not args.no_screenshots,
                        "max_screenshots": args.max_screenshots,
                        "extracted_skill": {
                            "skill_id": skill.skill_id,
                            "name": skill.name,
                            "app": skill.app,
                            "step_count": len(skill.steps),
                        },
                        "result_skill_id": final_id or skill.skill_id,
                        "timestamp": time.time(),
                    },
                )
                return outcome
            except Exception as exc:  # noqa: BLE001 - write auditable result and continue.
                outcome.errors = 1
                _write_json(
                    trace.parent / "extraction_result.json",
                    {
                        "status": "error",
                        "trace": str(trace),
                        "is_success": bool((_load_result_event(trace) or {}).get("success", False)),
                        "stream": args.stream,
                        "include_screenshots": not args.no_screenshots,
                        "max_screenshots": args.max_screenshots,
                        "error": repr(exc),
                        "timestamp": time.time(),
                    },
                )
                if not args.keep_going:
                    raise
                return outcome

    processed = 0
    skipped = len(skipped_traces)
    extracted = 0
    errors = 0
    with progress_context as progress_tuple:
        progress, task_progress, trace_progress = progress_tuple
        pending = [asyncio.create_task(process_trace(trace)) for trace in work_traces]
        try:
            for task in asyncio.as_completed(pending):
                outcome = await task
                processed += outcome.processed
                skipped += outcome.skipped
                extracted += outcome.extracted
                errors += outcome.errors
                if progress is not None:
                    progress.update(
                        trace_progress,
                        description=f"Traces ({_task_name_for_trace(outcome.trace)})",
                    )
                mark_trace_done(progress, task_progress, trace_progress, outcome.trace)
        except Exception:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            raise

    print(
        json.dumps(
            {
                "traces": len(traces),
                "tasks": len(task_totals),
                "concurrency": args.concurrency,
                "stream": args.stream,
                "include_screenshots": not args.no_screenshots,
                "max_screenshots": args.max_screenshots,
                "disable_thinking": args.disable_thinking,
                "overwrite_statuses": sorted(overwrite_statuses),
                "processed": processed,
                "extracted": extracted,
                "skipped": skipped,
                "errors": errors,
                "store_root": str(Path(args.store_root).expanduser().resolve()),
                "scan": scan_summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if errors == 0 else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", nargs="+", help="Nanobot mixed run root(s) under traj_logs")
    parser.add_argument("--nanobot-root", default=str(DEFAULT_NANOBOT_ROOT))
    parser.add_argument("--store-root", default=str(DEFAULT_STORE_ROOT))
    parser.add_argument("--model", default=os.getenv("MA_MODEL_NAME") or DEFAULT_MODEL)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Use streaming chat completions and aggregate the final response",
    )
    parser.add_argument(
        "--disable-thinking",
        action="store_true",
        help="Pass chat_template_kwargs.enable_thinking=false via extra_body",
    )
    parser.add_argument(
        "--extra-body",
        default=None,
        help="Additional OpenAI-compatible JSON object passed as extra_body",
    )
    parser.add_argument(
        "--no-screenshots",
        action="store_true",
        help="Extract from trajectory text only, without screenshot image blocks",
    )
    parser.add_argument(
        "--max-screenshots",
        type=int,
        default=10,
        help="Maximum screenshots included per extraction call (default: 10)",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.getenv("OPENGUI_SKILL_EXTRACT_CONCURRENCY", str(DEFAULT_CONCURRENCY))),
        help="Number of concurrent trace extraction calls (default: 4)",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--overwrite-status",
        default=None,
        help=(
            "Comma-separated existing extraction_result statuses to rerun "
            "when --overwrite is not set, e.g. error,no_candidate. "
            "Missing result files are always processed."
        ),
    )
    parser.add_argument("--include-abnormal", action="store_true")
    parser.add_argument("--keep-going", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-progress", action="store_true")
    return parser.parse_args()


def main() -> None:
    raise SystemExit(asyncio.run(_run(parse_args())))


if __name__ == "__main__":
    main()
