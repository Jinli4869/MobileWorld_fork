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
from pathlib import Path
from typing import Any


DEFAULT_NANOBOT_ROOT = Path("/home/jinli/Project/nanobot_fork")
DEFAULT_STORE_ROOT = Path("/home/jinli/Project/MobileWorld_fork/gui_skills")
DEFAULT_MODEL = "qwen3.5-397b-a17b"


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


@contextmanager
def _make_progress(enabled: bool, task_count: int, trace_count: int):
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
        task_progress = progress.add_task("Tasks", total=task_count)
        trace_progress = progress.add_task("Traces", total=trace_count)
        yield (progress, task_progress, trace_progress)


async def _run(args: argparse.Namespace) -> int:
    nanobot_root = Path(args.nanobot_root).expanduser().resolve()
    if not nanobot_root.exists():
        raise SystemExit(f"nanobot root not found: {nanobot_root}")
    sys.path.insert(0, str(nanobot_root))

    from opengui.cli import OpenAICompatibleLLMProvider
    from opengui.skills.extractor import SkillExtractor
    from opengui.skills.library import SkillLibrary

    roots = [Path(item) for item in args.run_root]
    traces = _iter_trace_paths(roots)
    if args.limit is not None:
        traces = traces[: args.limit]

    task_totals = Counter(_task_name_for_trace(trace) for trace in traces)
    task_done: defaultdict[str, int] = defaultdict(int)
    progress_context = _make_progress(not args.no_progress, len(task_totals), len(traces))

    def mark_trace_done(progress: Any, task_progress: Any, trace_progress: Any, trace: Path) -> None:
        if progress is None:
            return
        task_name = _task_name_for_trace(trace)
        task_done[task_name] += 1
        progress.advance(trace_progress)
        if task_done[task_name] >= task_totals[task_name]:
            progress.advance(task_progress)

    if args.dry_run:
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
    llm = OpenAICompatibleLLMProvider(
        base_url=args.base_url or _default_base_url(),
        model=args.model,
        api_key=api_key,
    )
    extractor = SkillExtractor(llm=llm)
    library = SkillLibrary(store_dir=Path(args.store_root).expanduser().resolve(), merge_llm=llm)

    processed = 0
    skipped = 0
    extracted = 0
    errors = 0
    with progress_context as progress_tuple:
        progress, task_progress, trace_progress = progress_tuple
        for trace in traces:
            if progress is not None:
                progress.update(trace_progress, description=f"Traces ({_task_name_for_trace(trace)})")
            try:
                result_path = trace.parent / "extraction_result.json"
                if result_path.exists() and not args.overwrite:
                    skipped += 1
                    continue
                result = _load_result_event(trace)
                if _is_abnormal(result) and not args.include_abnormal:
                    skipped += 1
                    _write_json(
                        result_path,
                        {
                            "status": "skipped_abnormal",
                            "trace": str(trace),
                            "reason": (result or {}).get("error"),
                            "timestamp": time.time(),
                        },
                    )
                    continue
                is_success = bool((result or {}).get("success", False))
                skill = await extractor.extract_from_file(trace, is_success=is_success)
                _write_json(trace.parent / "extraction_usage.json", extractor.total_usage)
                extractor.reset_usage()
                processed += 1
                if skill is None:
                    _write_json(
                        result_path,
                        {
                            "status": "no_candidate",
                            "trace": str(trace),
                            "is_success": is_success,
                            "timestamp": time.time(),
                        },
                    )
                    continue
                decision, final_id = await library.add_or_merge(skill)
                extracted += 1
                _write_json(
                    result_path,
                    {
                        "status": "processed",
                        "decision": decision,
                        "trace": str(trace),
                        "is_success": is_success,
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
            except Exception as exc:  # noqa: BLE001 - write auditable result and continue.
                errors += 1
                _write_json(
                    trace.parent / "extraction_result.json",
                    {
                        "status": "error",
                        "trace": str(trace),
                        "is_success": bool((_load_result_event(trace) or {}).get("success", False)),
                        "error": repr(exc),
                        "timestamp": time.time(),
                    },
                )
                if not args.keep_going:
                    raise
            finally:
                mark_trace_done(progress, task_progress, trace_progress, trace)

    print(
        json.dumps(
            {
                "traces": len(traces),
                "tasks": len(task_totals),
                "processed": processed,
                "extracted": extracted,
                "skipped": skipped,
                "errors": errors,
                "store_root": str(Path(args.store_root).expanduser().resolve()),
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
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--include-abnormal", action="store_true")
    parser.add_argument("--keep-going", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-progress", action="store_true")
    return parser.parse_args()


def main() -> None:
    raise SystemExit(asyncio.run(_run(parse_args())))


if __name__ == "__main__":
    main()
