"""Nanobot/OpenGUI mixed execution adapter implementation."""

from __future__ import annotations

import asyncio
import json
import multiprocessing as mp
import os
import re
import shlex
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

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
_TOKEN_USAGE_KEYS = ("prompt_tokens", "completion_tokens", "cached_tokens", "total_tokens")


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


def _coerce_positive_int(value: Any, *, default: int | None = None) -> int | None:
    if value is None:
        return default
    if isinstance(value, str) and not value.strip():
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"invalid_positive_int:{value!r}") from None
    if parsed <= 0:
        raise ValueError(f"invalid_positive_int:{parsed}")
    return parsed


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


def _extract_json_from_tool_content(content: Any) -> dict[str, Any] | None:
    payload = _json_loads_maybe(content)
    if payload is not None:
        return payload

    if isinstance(content, dict):
        for key in ("content", "text", "output", "result"):
            payload = _json_loads_maybe(content.get(key))
            if payload is not None:
                return payload

    if isinstance(content, list):
        for item in content:
            payload = _json_loads_maybe(item)
            if payload is not None:
                return payload
            if isinstance(item, dict):
                payload = _json_loads_maybe(item.get("text"))
                if payload is not None:
                    return payload
                payload = _json_loads_maybe(item.get("content"))
                if payload is not None:
                    return payload
    return None


def _path_str_if_exists(path_like: str | None) -> str | None:
    if not isinstance(path_like, str) or not path_like.strip():
        return None
    candidate = Path(path_like.strip()).expanduser()
    try:
        resolved = candidate.resolve()
    except OSError:
        resolved = candidate
    if resolved.exists():
        return str(resolved)
    return None


def _collect_gui_artifact_refs(gui_artifacts_root: str | None) -> tuple[list[str], list[str]]:
    if not gui_artifacts_root:
        return [], []
    root = Path(gui_artifacts_root).expanduser()
    try:
        root = root.resolve()
    except OSError:
        pass
    if not root.exists() or not root.is_dir():
        return [], []

    trace_refs: set[str] = set()
    screenshot_refs: set[str] = set()

    try:
        for trace_file in root.rglob("trace.jsonl"):
            trace_refs.add(str(trace_file.resolve()))
            trace_refs.add(str(trace_file.parent.resolve()))
        for screenshot in root.rglob("screenshots/*.png"):
            screenshot_refs.add(str(screenshot.resolve()))
    except Exception:
        logger.exception("failed_to_collect_gui_artifact_refs")

    return sorted(trace_refs), sorted(screenshot_refs)


def _compute_gui_task_latency_ms_from_trace(trace_path: Path) -> float | None:
    if not trace_path.exists() or not trace_path.is_file():
        return None
    first_ts: float | None = None
    last_ts: float | None = None
    try:
        with trace_path.open(encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                payload = _json_loads_maybe(line)
                if payload is None:
                    continue
                timestamp = payload.get("timestamp")
                if not isinstance(timestamp, (int, float)):
                    continue
                ts = float(timestamp)
                if first_ts is None:
                    first_ts = ts
                last_ts = ts
    except Exception:
        logger.exception("failed_to_compute_gui_task_latency_from_trace")
        return None

    if first_ts is None or last_ts is None or last_ts < first_ts:
        return None
    return round((last_ts - first_ts) * 1000.0, 3)


def _empty_token_usage() -> dict[str, int]:
    return {key: 0 for key in _TOKEN_USAGE_KEYS}


def _normalize_token_usage(usage: Any) -> dict[str, int]:
    if usage is None:
        return _empty_token_usage()

    if isinstance(usage, dict):
        usage_dict = usage
    else:
        usage_dict = {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "cached_tokens": getattr(usage, "cached_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }

    prompt_tokens = _coerce_int(usage_dict.get("prompt_tokens"), default=0)
    completion_tokens = _coerce_int(usage_dict.get("completion_tokens"), default=0)
    cached_tokens = _coerce_int(usage_dict.get("cached_tokens"), default=0)
    total_tokens = _coerce_int(usage_dict.get("total_tokens"), default=-1)
    if total_tokens < 0:
        total_tokens = prompt_tokens + completion_tokens + cached_tokens
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cached_tokens": cached_tokens,
        "total_tokens": total_tokens,
    }


def _token_usage_has_signal(usage: dict[str, int]) -> bool:
    normalized = _normalize_token_usage(usage)
    return any(normalized[key] > 0 for key in _TOKEN_USAGE_KEYS)


def _add_token_usage(lhs: Any, rhs: Any) -> dict[str, int]:
    left = _normalize_token_usage(lhs)
    right = _normalize_token_usage(rhs)
    merged = {key: left[key] + right[key] for key in _TOKEN_USAGE_KEYS}
    if merged["total_tokens"] <= 0:
        merged["total_tokens"] = (
            merged["prompt_tokens"] + merged["completion_tokens"] + merged["cached_tokens"]
        )
    return merged


def _fill_missing_token_usage(primary: Any, fallback: Any) -> dict[str, int]:
    primary_usage = _normalize_token_usage(primary)
    fallback_usage = _normalize_token_usage(fallback)
    merged: dict[str, int] = {}
    for key in _TOKEN_USAGE_KEYS:
        primary_value = primary_usage[key]
        merged[key] = primary_value if primary_value > 0 else fallback_usage[key]
    if merged["total_tokens"] <= 0:
        merged["total_tokens"] = merged["prompt_tokens"] + merged["completion_tokens"] + merged["cached_tokens"]
    return merged


def _collect_trace_files_from_refs(trace_refs: list[str]) -> list[Path]:
    trace_files: set[Path] = set()
    for trace_ref in trace_refs:
        if not isinstance(trace_ref, str) or not trace_ref.strip():
            continue
        candidate = Path(trace_ref).expanduser()
        try:
            candidate = candidate.resolve()
        except OSError:
            pass
        if candidate.is_file() and candidate.name == "trace.jsonl":
            trace_files.add(candidate)
            continue
        if candidate.is_dir():
            maybe_trace = candidate / "trace.jsonl"
            if maybe_trace.exists() and maybe_trace.is_file():
                trace_files.add(maybe_trace)
    return sorted(trace_files)


def _compute_gui_latency_stats_from_trace_refs(trace_refs: list[str]) -> tuple[float | None, float | None]:
    latencies: list[float] = []
    for trace_file in _collect_trace_files_from_refs(trace_refs):
        latency_ms = _compute_gui_task_latency_ms_from_trace(trace_file)
        if latency_ms is not None:
            latencies.append(latency_ms)

    if not latencies:
        return None, None
    total_latency_ms = round(sum(latencies), 3)
    avg_latency_ms = round(total_latency_ms / len(latencies), 3)
    return total_latency_ms, avg_latency_ms


def _compute_gui_token_usage_from_trace_refs(trace_refs: list[str]) -> dict[str, int]:
    total_usage = _empty_token_usage()
    for trace_file in _collect_trace_files_from_refs(trace_refs):
        try:
            with trace_file.open(encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    payload = _json_loads_maybe(line)
                    if payload is None:
                        continue
                    token_usage = payload.get("token_usage")
                    if token_usage is None:
                        continue
                    total_usage = _add_token_usage(total_usage, token_usage)
        except Exception:
            logger.exception("failed_to_compute_gui_token_usage_from_trace")
    return total_usage


def _instrument_provider_usage(
    provider: Any,
    *,
    usage_bucket: dict[str, int],
    usage_stats: dict[str, int],
    response_transform: Callable[[Any], Any] | None = None,
) -> None:
    if provider is None:
        return

    def _observe_usage(response: Any) -> None:
        usage_stats["calls"] = _coerce_int(usage_stats.get("calls"), default=0) + 1
        normalized = _normalize_token_usage(getattr(response, "usage", None))
        if _token_usage_has_signal(normalized):
            usage_bucket.update(_add_token_usage(usage_bucket, normalized))
            return
        usage_stats["missing"] = _coerce_int(usage_stats.get("missing"), default=0) + 1

    original_chat = getattr(provider, "chat_with_retry", None)
    if callable(original_chat):
        async def _wrapped_chat_with_retry(*args: Any, **kwargs: Any) -> Any:
            response = await original_chat(*args, **kwargs)
            if response_transform is not None:
                response = response_transform(response)
            _observe_usage(response)
            return response

        setattr(provider, "chat_with_retry", _wrapped_chat_with_retry)

    original_chat_stream = getattr(provider, "chat_stream_with_retry", None)
    if callable(original_chat_stream):
        async def _wrapped_chat_stream_with_retry(*args: Any, **kwargs: Any) -> Any:
            response = await original_chat_stream(*args, **kwargs)
            if response_transform is not None:
                response = response_transform(response)
            _observe_usage(response)
            return response

        setattr(provider, "chat_stream_with_retry", _wrapped_chat_stream_with_retry)


def _goal_requires_pure_answer(task_goal: str | None, task_name: str | None = None) -> bool:
    normalized_goal = (task_goal or "").strip().lower()
    normalized_task_name = (task_name or "").strip().lower()

    english_hints = (
        "respond only with",
        "respond only",
        "single number",
        "single integer",
        "no other text",
        "only with an integer",
        "only with a single number",
        "only give",
        "only output",
        "only provide",
        "only return",
        "output the company name in english",
        "company name in english",
    )
    chinese_hints = (
        "请只回答一个整数",
        "只回答一个整数",
        "只回复该整数",
        "不要返回任何其他文本",
        "不要返回其他文本",
        "不要返回任何其他内容",
        "只返回一个数字",
        "仅输出",
        "只输出",
        "仅返回",
        "只返回",
        "公司英文名",
    )
    task_name_hints = (
        "countfilelines",
        "checkinvoicetask",
        "chromesearchbeijingweathertask",
        "googlemapsalibabasouthneighbortask",
    )

    return (
        any(hint in normalized_goal for hint in english_hints)
        or any(hint in (task_goal or "") for hint in chinese_hints)
        or any(hint in normalized_task_name for hint in task_name_hints)
    )


def _normalize_numeric_text(value: str) -> str:
    normalized = value.replace(",", "").strip()
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _extract_pure_answer_text(summary: str | None) -> str | None:
    if not summary:
        return None
    answer_line_match = re.search(
        r"(?im)^\s*(?:\*\*)?\s*answer\s*(?:\*\*)?\s*[:：]\s*(.+?)\s*$",
        summary,
    )
    if answer_line_match:
        answer_line = answer_line_match.group(1).strip().strip("`* ")
        if answer_line:
            numeric = re.fullmatch(r"[-+]?\d[\d,]*(?:\.\d+)?", answer_line)
            if numeric:
                return _normalize_numeric_text(answer_line)
            short_answer = answer_line.splitlines()[0].strip().rstrip(".")
            if short_answer and len(short_answer) <= 128 and "|" not in short_answer:
                return short_answer
    lines = [line.strip() for line in summary.splitlines() if line.strip()]
    if lines:
        tail = lines[-1].strip("`* ").strip()
        if re.fullmatch(r"[-+]?\d[\d,]*(?:\.\d+)?", tail):
            return _normalize_numeric_text(tail)
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9 .&'/-]{1,100}", tail):
            return tail.rstrip(".")
    number_matches = re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", summary)
    if number_matches:
        return _normalize_numeric_text(number_matches[-1])
    company_match = re.search(
        r"(?i)\b(?:company|neighbor|neighbour|answer)\b[^A-Za-z0-9]{0,20}([A-Za-z][A-Za-z0-9 .&'/-]{1,100})",
        summary,
    )
    if company_match:
        candidate = company_match.group(1).strip().rstrip(".")
        if candidate:
            return candidate
    if len(lines) == 1:
        candidate = lines[0].strip("`* ").strip()
        if candidate and len(candidate) <= 128 and "|" not in candidate:
            return candidate
    return None


def _extract_answer_from_message_tool_calls(messages: list[dict[str, Any]] | None) -> str | None:
    if not isinstance(messages, list):
        return None

    candidates: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        if role == "assistant":
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list):
                for tool_call in tool_calls:
                    if not isinstance(tool_call, dict):
                        continue
                    fn_payload = (
                        tool_call.get("function")
                        if isinstance(tool_call.get("function"), dict)
                        else tool_call
                    )
                    tool_name = fn_payload.get("name")
                    if not isinstance(tool_name, str):
                        continue
                    normalized_tool_name = tool_name.strip().lower()
                    if normalized_tool_name not in {
                        "message",
                        "tool.message",
                        "send_message",
                    }:
                        continue
                    args = _json_loads_maybe(fn_payload.get("arguments")) or {}
                    for key in ("content", "text", "message"):
                        value = args.get(key)
                        if isinstance(value, str) and value.strip():
                            candidates.append(value.strip())

        if role == "tool":
            tool_name_raw = message.get("name")
            tool_name = (
                tool_name_raw.strip().lower()
                if isinstance(tool_name_raw, str)
                else ""
            )
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                if "message" in tool_name:
                    candidates.append(content.strip())
                elif len(content.strip()) <= 512:
                    candidates.append(content.strip())
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text")
                        if isinstance(text, str) and text.strip() and len(text.strip()) <= 512:
                            candidates.append(text.strip())
            elif isinstance(content, dict):
                for key in ("text", "content", "output", "result"):
                    value = content.get(key)
                    if isinstance(value, str) and value.strip() and len(value.strip()) <= 512:
                        candidates.append(value.strip())

    for candidate in reversed(candidates):
        parsed = _extract_pure_answer_text(candidate)
        if parsed:
            return parsed
        if len(candidate) <= 128 and "|" not in candidate:
            return candidate
    return None


def _normalize_answer_for_task(
    *,
    task_name: str | None,
    answer_text: str | None,
    summary_text: str | None,
) -> str | None:
    normalized_task_name = (task_name or "").strip().lower()
    candidate = answer_text.strip() if isinstance(answer_text, str) and answer_text.strip() else None
    summary = summary_text or ""

    if "chromesearchbeijingweathertask" in normalized_task_name:
        for source in (candidate, summary):
            if not isinstance(source, str) or not source.strip():
                continue
            if re.fullmatch(r"[-+]?\d[\d,]*(?:\.\d+)?", source.strip()):
                return _normalize_numeric_text(source.strip())
            number_matches = re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", source)
            if number_matches:
                return _normalize_numeric_text(number_matches[-1])
        return None

    if "googlemapsalibabasouthneighbortask" in normalized_task_name:
        for source in (candidate, summary):
            if not isinstance(source, str) or not source.strip():
                continue
            direct = source.strip().strip("`* ").rstrip(".")
            tail_match = re.search(
                r"(?i)\b(?:is|是)\s+([A-Za-z][A-Za-z0-9 .&'/-]{0,100})$",
                direct,
            )
            if tail_match:
                return tail_match.group(1).strip().rstrip(".")
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9 .&'/-]{1,100}", direct):
                return direct
            company_match = re.search(
                r"(?i)(?:answer|company|neighbor|neighbour)\s*[:：]?\s*([A-Za-z][A-Za-z0-9 .&'/-]{1,100})",
                source,
            )
            if company_match:
                return company_match.group(1).strip().rstrip(".")
        return None

    if candidate is None:
        return None
    if re.fullmatch(r"[-+]?\d[\d,]*(?:\.\d+)?", candidate):
        return _normalize_numeric_text(candidate)
    return candidate


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
        nanobot_max_steps: int | None = None,
        nanobot_timeout_seconds: int | None = None,
        nanobot_enable_planner: bool | None = None,
        nanobot_enable_router: bool | None = None,
        nanobot_gui_task_max_steps: int | None = None,
        nanobot_gui_task_max_calls: int | None = None,
        nanobot_no_log_watchdog_seconds: int | None = None,
    ) -> None:
        self.model_name = model_name
        self.llm_base_url = llm_base_url
        self.api_key = api_key
        self.nanobot_root = _resolve_nanobot_fork_path(nanobot_fork_path)
        self.nanobot_config_path = nanobot_config_path
        self.gui_claw_path = gui_claw_path or _DEFAULT_GUI_CLAW_PATH
        self.evaluation_mode = (evaluation_mode or "mixed").strip().lower()
        self.allow_adb_bypass = True if allow_adb_bypass is None else bool(allow_adb_bypass)
        self.nanobot_max_steps = _coerce_positive_int(nanobot_max_steps, default=None)
        self.nanobot_timeout_seconds = _coerce_positive_int(nanobot_timeout_seconds, default=None)
        self.nanobot_enable_planner = False if nanobot_enable_planner is None else bool(nanobot_enable_planner)
        self.nanobot_enable_router = False if nanobot_enable_router is None else bool(nanobot_enable_router)
        self.nanobot_gui_task_max_steps = _coerce_positive_int(
            nanobot_gui_task_max_steps,
            default=50,
        )
        self.nanobot_gui_task_max_calls = _coerce_positive_int(
            nanobot_gui_task_max_calls,
            default=3,
        )
        self.nanobot_no_log_watchdog_seconds = _coerce_positive_int(
            nanobot_no_log_watchdog_seconds,
            default=120,
        )

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
        try:
            runtime_nanobot_max_steps = _coerce_positive_int(
                options.get("nanobot_max_steps"),
                default=self.nanobot_max_steps,
            )
        except ValueError as exc:
            return AdapterInitializeResult(
                ok=False,
                message=f"nanobot_max_steps_invalid:{exc}",
            )
        try:
            runtime_nanobot_timeout_seconds = _coerce_positive_int(
                options.get("nanobot_timeout_seconds"),
                default=self.nanobot_timeout_seconds,
            )
        except ValueError as exc:
            return AdapterInitializeResult(
                ok=False,
                message=f"nanobot_timeout_seconds_invalid:{exc}",
            )
        runtime_nanobot_enable_planner = _coerce_bool(
            options.get("nanobot_enable_planner"),
            default=self.nanobot_enable_planner,
        )
        runtime_nanobot_enable_router = _coerce_bool(
            options.get("nanobot_enable_router"),
            default=self.nanobot_enable_router,
        )
        if not runtime_nanobot_enable_planner:
            runtime_nanobot_enable_router = False
        try:
            runtime_nanobot_gui_task_max_steps = _coerce_positive_int(
                options.get(
                    "nanobot_gui_task_max_steps",
                    options.get("gui_task_max_steps"),
                ),
                default=self.nanobot_gui_task_max_steps,
            )
        except ValueError as exc:
            return AdapterInitializeResult(
                ok=False,
                message=f"nanobot_gui_task_max_steps_invalid:{exc}",
            )
        try:
            runtime_nanobot_gui_task_max_calls = _coerce_positive_int(
                options.get(
                    "nanobot_gui_task_max_calls",
                    options.get("gui_task_max_calls"),
                ),
                default=self.nanobot_gui_task_max_calls,
            )
        except ValueError as exc:
            return AdapterInitializeResult(
                ok=False,
                message=f"nanobot_gui_task_max_calls_invalid:{exc}",
            )
        try:
            runtime_nanobot_no_log_watchdog_seconds = _coerce_positive_int(
                options.get(
                    "nanobot_no_log_watchdog_seconds",
                    options.get("nanobot_watchdog_no_log_seconds"),
                ),
                default=self.nanobot_no_log_watchdog_seconds,
            )
        except ValueError as exc:
            return AdapterInitializeResult(
                ok=False,
                message=f"nanobot_no_log_watchdog_seconds_invalid:{exc}",
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
            "nanobot_max_steps": runtime_nanobot_max_steps,
            "nanobot_timeout_seconds": runtime_nanobot_timeout_seconds,
            "nanobot_enable_planner": runtime_nanobot_enable_planner,
            "nanobot_enable_router": runtime_nanobot_enable_router,
            "nanobot_gui_task_max_steps": runtime_nanobot_gui_task_max_steps,
            "nanobot_gui_task_max_calls": runtime_nanobot_gui_task_max_calls,
            "nanobot_no_log_watchdog_seconds": runtime_nanobot_no_log_watchdog_seconds,
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
                "nanobot_max_steps": runtime_nanobot_max_steps,
                "nanobot_timeout_seconds": runtime_nanobot_timeout_seconds,
                "nanobot_enable_planner": runtime_nanobot_enable_planner,
                "nanobot_enable_router": runtime_nanobot_enable_router,
                "nanobot_gui_task_max_steps": runtime_nanobot_gui_task_max_steps,
                "nanobot_gui_task_max_calls": runtime_nanobot_gui_task_max_calls,
                "nanobot_no_log_watchdog_seconds": runtime_nanobot_no_log_watchdog_seconds,
            },
        )

    def _derive_execution_timeout_seconds(self) -> int | None:
        explicit_timeout = self._state.get("nanobot_timeout_seconds")
        if explicit_timeout is not None:
            try:
                parsed = int(explicit_timeout)
            except (TypeError, ValueError):
                return None
            if parsed > 0:
                return parsed
        task_name = str(self._state.get("task_name") or "").lower()
        task_goal = str(self._state.get("task_goal") or "").lower()
        long_task_hints = (
            "chrome",
            "googlemaps",
            "mastodon",
            "follow",
            "sendinterview",
            "checkeventtime",
            "search",
            "email",
            "map",
        )
        if any(hint in task_name for hint in long_task_hints) or any(
            hint in task_goal for hint in long_task_hints
        ):
            return 600
        return 300

    def _derive_no_log_watchdog_seconds(self) -> int | None:
        explicit = self._state.get("nanobot_no_log_watchdog_seconds")
        if explicit is None:
            explicit = self.nanobot_no_log_watchdog_seconds
        try:
            parsed = int(explicit) if explicit is not None else None
        except (TypeError, ValueError):
            return None
        if parsed is None or parsed <= 0:
            return None
        return parsed

    @staticmethod
    def _safe_mtime(path: Path) -> float:
        try:
            if path.exists():
                return float(path.stat().st_mtime)
        except OSError:
            return 0.0
        return 0.0

    def _compute_no_log_watchdog_marker(self, *, run_id: str) -> float:
        task_output_dir = Path(str(self._state.get("output_dir", "."))).expanduser().resolve()
        marker = self._safe_mtime(task_output_dir)

        runtime_dir = task_output_dir / ".nanobot_runtime" / run_id
        marker = max(marker, self._safe_mtime(runtime_dir))
        marker = max(marker, self._safe_mtime(runtime_dir / "adb_wrapper_calls.log"))
        if runtime_dir.exists() and runtime_dir.is_dir():
            try:
                for child in runtime_dir.iterdir():
                    marker = max(marker, self._safe_mtime(child))
            except OSError:
                pass

        gui_root = task_output_dir / "nanobot_gui_task_runs"
        marker = max(marker, self._safe_mtime(gui_root))
        if gui_root.exists() and gui_root.is_dir():
            try:
                for child in gui_root.iterdir():
                    marker = max(marker, self._safe_mtime(child))
            except OSError:
                pass

        try:
            for log_file in task_output_dir.glob("thread_*.log"):
                marker = max(marker, self._safe_mtime(log_file))
        except OSError:
            pass

        return marker

    def _collect_wrapper_adb_call_stats(self, *, run_id: str) -> tuple[int, int]:
        output_dir = Path(str(self._state.get("output_dir", "."))).expanduser().resolve()
        call_log_path = output_dir / ".nanobot_runtime" / run_id / "adb_wrapper_calls.log"
        if not call_log_path.exists():
            return 0, 0

        wrapper_mw_adb_calls = 0
        wrapper_adb_calls = 0
        try:
            for line in call_log_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("mw_adb\t"):
                    wrapper_mw_adb_calls += 1
                elif line.startswith("adb\t"):
                    wrapper_adb_calls += 1
        except Exception:
            logger.exception("failed_to_read_adb_wrapper_call_log")
        return wrapper_mw_adb_calls, wrapper_adb_calls

    def _estimate_gui_stats_from_artifacts(
        self, *, gui_artifacts_root: str | None
    ) -> tuple[list[str], list[str], int, int, float | None, float | None, dict[str, int]]:
        local_trace_refs, local_screenshot_refs = _collect_gui_artifact_refs(gui_artifacts_root)
        gui_task_runs: set[str] = set()
        for screenshot in local_screenshot_refs:
            screenshot_path = Path(screenshot)
            parent = screenshot_path.parent
            if parent.name == "screenshots":
                gui_task_runs.add(str(parent.parent))
        for trace_ref in local_trace_refs:
            trace_path = Path(trace_ref)
            if trace_path.is_dir():
                gui_task_runs.add(str(trace_path))
            elif trace_path.name == "trace.jsonl":
                gui_task_runs.add(str(trace_path.parent))
        gui_task_calls = len(gui_task_runs)
        gui_steps = len(local_screenshot_refs)
        total_latency_ms, avg_latency_ms = _compute_gui_latency_stats_from_trace_refs(local_trace_refs)
        gui_trace_usage = _compute_gui_token_usage_from_trace_refs(local_trace_refs)
        return (
            local_trace_refs,
            local_screenshot_refs,
            gui_task_calls,
            gui_steps,
            total_latency_ms,
            avg_latency_ms,
            gui_trace_usage,
        )

    def _run_coro_sync(
        self,
        *,
        task_name: str,
        task_goal: str,
        run_id: str,
        timeout_seconds: int | None = None,
    ) -> tuple[dict[str, Any] | None, bool, bool]:
        self._state["_last_execution_timeout_reason"] = None
        def _thread_worker(result_holder: dict[str, Any], error_holder: dict[str, BaseException]) -> None:
            try:
                coro = self._execute_with_nanobot_loop(
                    task_name=task_name,
                    task_goal=task_goal,
                    run_id=run_id,
                )
                if timeout_seconds is not None and timeout_seconds > 0:
                    coro = asyncio.wait_for(coro, timeout=float(timeout_seconds))
                result_holder["value"] = asyncio.run(coro)
            except BaseException as exc:
                error_holder["error"] = exc

        if os.name != "posix":
            result_holder: dict[str, Any] = {}
            error_holder: dict[str, BaseException] = {}
            done_event = threading.Event()

            def _wrapped_thread_worker() -> None:
                try:
                    _thread_worker(result_holder, error_holder)
                finally:
                    done_event.set()

            worker = threading.Thread(
                target=_wrapped_thread_worker,
                name="nanobot_mixed_coro_runner",
                daemon=True,
            )
            worker.start()
            wait_timeout: float | None = None
            if timeout_seconds is not None and timeout_seconds > 0:
                wait_timeout = float(timeout_seconds) + 5.0
            finished = done_event.wait(wait_timeout)
            if not finished:
                self._state["_last_execution_timeout_reason"] = "nanobot_execution_timeout"
                return None, True, False
            if "error" in error_holder:
                raise error_holder["error"]
            return result_holder.get("value"), False, False

        ctx = mp.get_context("fork")
        recv_conn, send_conn = ctx.Pipe(duplex=False)

        def _subprocess_worker(conn: Any) -> None:
            try:
                coro = self._execute_with_nanobot_loop(
                    task_name=task_name,
                    task_goal=task_goal,
                    run_id=run_id,
                )
                result = asyncio.run(coro)
                conn.send({"ok": True, "result": result})
            except BaseException as exc:  # pragma: no cover - defensive runtime path
                conn.send(
                    {
                        "ok": False,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    }
                )
            finally:
                conn.close()

        proc = ctx.Process(
            target=_subprocess_worker,
            args=(send_conn,),
            daemon=True,
        )
        proc.start()
        send_conn.close()

        wait_timeout: float | None = None
        if timeout_seconds is not None and timeout_seconds > 0:
            wait_timeout = float(timeout_seconds)
        watchdog_seconds = self._derive_no_log_watchdog_seconds()
        watchdog_poll_seconds = 1.0
        last_marker = self._compute_no_log_watchdog_marker(run_id=run_id)
        start_monotonic = time.monotonic()
        last_progress_monotonic = start_monotonic

        timeout_triggered = False
        execution_cancelled = False
        payload: dict[str, Any] | None = None
        try:
            while True:
                if recv_conn.poll(watchdog_poll_seconds):
                    payload = recv_conn.recv()
                    break
                now_monotonic = time.monotonic()
                if wait_timeout is not None and (now_monotonic - start_monotonic) >= wait_timeout:
                    timeout_triggered = True
                    self._state["_last_execution_timeout_reason"] = "nanobot_execution_timeout"
                    break
                if watchdog_seconds is not None:
                    marker = self._compute_no_log_watchdog_marker(run_id=run_id)
                    if marker > last_marker + 1e-6:
                        last_marker = marker
                        last_progress_monotonic = now_monotonic
                    elif (now_monotonic - last_progress_monotonic) >= float(watchdog_seconds):
                        timeout_triggered = True
                        self._state["_last_execution_timeout_reason"] = "nanobot_no_log_watchdog_timeout"
                        break
        finally:
            recv_conn.close()

        if timeout_triggered:
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=8)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=5)
                execution_cancelled = True
            return None, True, execution_cancelled

        proc.join(timeout=5)
        if payload is None:
            return None, True, False
        if not payload.get("ok", False):
            error_type = str(payload.get("error_type") or "RuntimeError")
            error_text = str(payload.get("error") or "nanobot_subprocess_failed")
            if error_type == "TimeoutError":
                return None, True, True
            raise RuntimeError(f"{error_type}: {error_text}")
        result = payload.get("result")
        if isinstance(result, dict):
            return result, False, False
        return {}, False, False

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
            from nanobot.providers.base import LLMResponse

            config_path = Path(self._state["nanobot_config_path"]).expanduser().resolve()
            set_config_path(config_path)
            config = load_config(config_path)
            config.agents.defaults.workspace = self._state["gui_claw_path"]
            runtime_model = self.model_name or config.agents.defaults.model
            config.agents.defaults.model = runtime_model

            output_dir = Path(str(self._state.get("output_dir", "."))).expanduser().resolve()
            gui_artifacts_root = output_dir / "nanobot_gui_task_runs"
            gui_artifacts_root.mkdir(parents=True, exist_ok=True)
            if hasattr(config.gui, "artifacts_dir"):
                config.gui.artifacts_dir = str(gui_artifacts_root)

            provider_name = str(getattr(config.agents.defaults, "provider", "auto") or "auto").strip().lower()
            inferred_provider_name = _infer_provider_name(self.model_name, self.llm_base_url)
            if provider_name in {"", "auto"}:
                provider_name = inferred_provider_name
            elif self.llm_base_url and inferred_provider_name not in {"", "custom"}:
                # Explicit runtime base URL takes precedence over static config provider.
                provider_name = inferred_provider_name
            config.agents.defaults.provider = provider_name

            provider_cfg = getattr(config.providers, provider_name, None)
            if provider_cfg is None:
                provider_name = inferred_provider_name if inferred_provider_name not in {"", "custom"} else "custom"
                config.agents.defaults.provider = provider_name
                provider_cfg = getattr(config.providers, provider_name, None) or config.providers.custom

            runtime_api_key = _resolve_runtime_api_key(provider_name, self.api_key)
            if runtime_api_key and hasattr(provider_cfg, "api_key"):
                provider_cfg.api_key = runtime_api_key
            if self.llm_base_url and hasattr(provider_cfg, "api_base"):
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

            config.gui.model = runtime_model
            config.gui.provider = provider_name
            if getattr(config.gui, "evaluation", None) is not None:
                config.gui.evaluation.judge_model = runtime_model

            gui_task_max_steps = _coerce_int(
                self._state.get("nanobot_gui_task_max_steps"),
                default=50,
            )
            if gui_task_max_steps <= 0:
                gui_task_max_steps = 50
            config.gui.max_steps = gui_task_max_steps
            enable_planner = bool(self._state.get("nanobot_enable_planner", False))
            enable_router = bool(self._state.get("nanobot_enable_router", False))
            config.gui.enable_planner = enable_planner
            config.gui.enable_router = bool(enable_planner and enable_router)

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
                model_override=runtime_model,
                provider_override=provider_name,
            )
            gui_provider, gui_model = _resolve_gui_runtime(config)
            gui_task_max_calls = _coerce_int(
                self._state.get("nanobot_gui_task_max_calls"),
                default=3,
            )
            if gui_task_max_calls <= 0:
                gui_task_max_calls = 3
            gui_task_call_count = 0
            gui_task_call_cap_reached = False

            def _apply_gui_task_call_cap(response: Any) -> Any:
                nonlocal gui_task_call_count, gui_task_call_cap_reached
                tool_calls = getattr(response, "tool_calls", None)
                if not isinstance(tool_calls, list) or not tool_calls:
                    return response
                requested_gui_calls = sum(
                    1 for tool_call in tool_calls if str(getattr(tool_call, "name", "")).lower() == "gui_task"
                )
                if requested_gui_calls <= 0:
                    return response
                if gui_task_call_count + requested_gui_calls > gui_task_max_calls:
                    gui_task_call_cap_reached = True
                    summary = (
                        f"Stopped because gui_task call cap was reached "
                        f"({gui_task_call_count}/{gui_task_max_calls})."
                    )
                    content = getattr(response, "content", None)
                    if isinstance(content, str) and content.strip():
                        summary = f"{content.strip()}\n\n{summary}"
                    return LLMResponse(
                        content=summary,
                        tool_calls=[],
                        finish_reason="stop",
                        usage=getattr(response, "usage", {}) or {},
                        reasoning_content=getattr(response, "reasoning_content", None),
                        thinking_blocks=getattr(response, "thinking_blocks", None),
                    )
                gui_task_call_count += requested_gui_calls
                return response

            main_usage_accum = _empty_token_usage()
            gui_usage_accum = _empty_token_usage()
            main_usage_stats = {"calls": 0, "missing": 0}
            gui_usage_stats = {"calls": 0, "missing": 0}
            shared_provider_for_gui = gui_provider is provider and gui_provider is not None
            _instrument_provider_usage(
                provider,
                usage_bucket=main_usage_accum,
                usage_stats=main_usage_stats,
                response_transform=_apply_gui_task_call_cap,
            )
            if gui_provider is not None and not shared_provider_for_gui:
                _instrument_provider_usage(
                    gui_provider,
                    usage_bucket=gui_usage_accum,
                    usage_stats=gui_usage_stats,
                )
            cron_store_path = config.workspace_path / "cron" / "jobs.json"
            cron = CronService(cron_store_path)

            agent_loop = AgentLoop(
                bus=bus,
                provider=provider,
                workspace=config.workspace_path,
                model=runtime_model,
                max_iterations=int(
                    self._state.get("nanobot_max_steps")
                    or config.agents.defaults.max_tool_iterations
                ),
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
            "gui_artifacts_root": str(gui_artifacts_root),
            "wrapper_mw_adb_calls": wrapper_mw_adb_calls,
            "wrapper_adb_calls": wrapper_adb_calls,
            "token_usage_main": main_usage_accum,
            "token_usage_gui_task": gui_usage_accum,
            "token_usage_incomplete": (
                _coerce_int(main_usage_stats.get("missing"), default=0) > 0
                or _coerce_int(gui_usage_stats.get("missing"), default=0) > 0
                or bool(shared_provider_for_gui)
            ),
            "token_usage_shared_provider": bool(shared_provider_for_gui),
            "gui_task_max_calls": gui_task_max_calls,
            "gui_task_calls_executed": gui_task_call_count,
            "gui_task_call_cap_reached": bool(gui_task_call_cap_reached),
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
        screenshot_refs: list[str] = []

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

            tool_name_raw = message.get("name")
            tool_name = str(tool_name_raw).lower() if isinstance(tool_name_raw, str) else ""
            if role == "tool" and "gui_task" in tool_name:
                payload = _extract_json_from_tool_content(message.get("content"))
                if payload is None:
                    continue
                gui_steps += _coerce_int(payload.get("steps_taken"), default=0)
                trace_path = payload.get("trace_path")
                if isinstance(trace_path, str) and trace_path.strip():
                    trace_refs.append(trace_path.strip())
                run_dir = payload.get("run_dir")
                if isinstance(run_dir, str) and run_dir.strip():
                    trace_refs.append(run_dir.strip())
                for key in ("trace_jsonl", "trajectory_path"):
                    maybe_trace = payload.get(key)
                    if isinstance(maybe_trace, str) and maybe_trace.strip():
                        trace_refs.append(maybe_trace.strip())
                post_run_state = payload.get("post_run_state")
                if isinstance(post_run_state, dict):
                    latest_screenshot = post_run_state.get("latest_screenshot_path")
                    if isinstance(latest_screenshot, str) and latest_screenshot.strip():
                        screenshot_refs.append(latest_screenshot.strip())
                        parent = Path(latest_screenshot.strip()).expanduser().parent
                        if parent.name == "screenshots":
                            trace_refs.append(str(parent.parent))

        dedup_trace_refs = sorted({path for path in trace_refs})
        dedup_screenshot_refs = sorted({path for path in screenshot_refs})
        return {
            "adb_calls": adb_calls,
            "gui_task_calls": gui_task_calls,
            "deeplink_calls": deeplink_calls,
            "gui_steps": gui_steps,
            "trace_refs": dedup_trace_refs,
            "screenshot_refs": dedup_screenshot_refs,
        }

    def _run_nanobot_mixed_execution(
        self,
        *,
        task_name: str,
        task_goal: str,
        run_id: str,
    ) -> dict[str, Any]:
        timeout_seconds = self._derive_execution_timeout_seconds()
        raw_result: dict[str, Any] | None = None
        timeout_triggered = False
        execution_cancelled = False
        try:
            raw_result, timeout_triggered, execution_cancelled = self._run_coro_sync(
                task_name=task_name,
                task_goal=task_goal,
                run_id=run_id,
                timeout_seconds=timeout_seconds,
            )
        except TimeoutError:
            timeout_triggered = True
            execution_cancelled = True
            raw_result = None
            self._state["_last_execution_timeout_reason"] = "nanobot_execution_timeout"
        if timeout_triggered or raw_result is None:
            timeout_reason = str(
                self._state.get("_last_execution_timeout_reason") or "nanobot_execution_timeout"
            )
            watchdog_seconds = self._derive_no_log_watchdog_seconds()
            if timeout_reason == "nanobot_no_log_watchdog_timeout" and watchdog_seconds:
                timeout_error = f"{timeout_reason}:{watchdog_seconds}s"
            else:
                timeout_error = f"{timeout_reason}:{timeout_seconds}s"
            gui_artifacts_root = str(
                Path(str(self._state.get("output_dir", "."))).expanduser().resolve()
                / "nanobot_gui_task_runs"
            )
            gui_task_max_calls = _coerce_int(
                self._state.get("nanobot_gui_task_max_calls"),
                default=3,
            )
            wrapper_mw_adb_calls, wrapper_adb_calls = self._collect_wrapper_adb_call_stats(run_id=run_id)
            (
                local_trace_refs,
                local_screenshot_refs,
                timeout_gui_task_calls,
                timeout_gui_steps,
                timeout_gui_total_latency_ms,
                timeout_gui_avg_latency_ms,
                timeout_gui_trace_usage,
            ) = self._estimate_gui_stats_from_artifacts(gui_artifacts_root=gui_artifacts_root)
            timeout_main_usage = _empty_token_usage()
            timeout_gui_usage = _normalize_token_usage(timeout_gui_trace_usage)
            timeout_total_usage = _add_token_usage(timeout_main_usage, timeout_gui_usage)
            return {
                "execution_mode": "mixed",
                "success": False,
                "summary": "nanobot_mixed_execution_timeout",
                "error": timeout_error,
                "adb_calls": wrapper_mw_adb_calls + wrapper_adb_calls,
                "gui_task_calls": timeout_gui_task_calls,
                "deeplink_calls": 0,
                "gui_steps": timeout_gui_steps,
                "trace_refs": local_trace_refs,
                "gui_screenshot_refs": local_screenshot_refs,
                "gui_artifacts_root": _path_str_if_exists(gui_artifacts_root),
                "gui_task_total_latency_ms": timeout_gui_total_latency_ms,
                "gui_task_avg_latency_ms": timeout_gui_avg_latency_ms,
                "token_usage_main": timeout_main_usage,
                "token_usage_gui_task": timeout_gui_usage,
                "token_usage_total": timeout_total_usage,
                "token_usage_incomplete": True,
                "gui_task_max_calls": gui_task_max_calls,
                "gui_task_calls_executed": timeout_gui_task_calls,
                "gui_task_call_cap_reached": False,
                "timeout_triggered": True,
                "timeout_reason": timeout_reason,
                "watchdog_triggered": timeout_reason == "nanobot_no_log_watchdog_timeout",
                "no_log_watchdog_seconds": watchdog_seconds,
                "execution_cancelled": bool(execution_cancelled),
                "effective_timeout_seconds": timeout_seconds,
            }
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
        local_trace_refs, local_screenshot_refs = _collect_gui_artifact_refs(
            raw_result.get("gui_artifacts_root")
        )
        message_trace_refs = [ref for ref in (lane_stats.get("trace_refs") or []) if isinstance(ref, str)]
        message_screenshot_refs = [
            ref for ref in (lane_stats.get("screenshot_refs") or []) if isinstance(ref, str)
        ]
        merged_trace_refs_raw = sorted({*message_trace_refs, *local_trace_refs})
        merged_screenshot_refs_raw = sorted({*message_screenshot_refs, *local_screenshot_refs})
        merged_trace_refs = [
            normalized for ref in merged_trace_refs_raw if (normalized := _path_str_if_exists(ref)) is not None
        ]
        merged_screenshot_refs = [
            normalized
            for ref in merged_screenshot_refs_raw
            if (normalized := _path_str_if_exists(ref)) is not None
        ]
        gui_task_total_latency_ms, gui_task_avg_latency_ms = _compute_gui_latency_stats_from_trace_refs(
            merged_trace_refs
        )
        main_usage = _normalize_token_usage(raw_result.get("token_usage_main"))
        gui_usage_provider = _normalize_token_usage(raw_result.get("token_usage_gui_task"))
        gui_usage_trace = _compute_gui_token_usage_from_trace_refs(merged_trace_refs)
        gui_usage = _fill_missing_token_usage(gui_usage_provider, gui_usage_trace)
        token_usage_shared_provider = bool(raw_result.get("token_usage_shared_provider", False))
        if token_usage_shared_provider:
            total_usage = main_usage
        else:
            total_usage = _add_token_usage(main_usage, gui_usage)
        token_usage_incomplete = bool(raw_result.get("token_usage_incomplete", False))
        if token_usage_shared_provider:
            token_usage_incomplete = True
        gui_task_max_calls = _coerce_int(raw_result.get("gui_task_max_calls"), default=3)
        gui_task_calls_executed = _coerce_int(
            raw_result.get("gui_task_calls_executed"),
            default=merged_gui_task_calls,
        )
        gui_task_call_cap_reached = bool(raw_result.get("gui_task_call_cap_reached", False))
        return {
            "execution_mode": "mixed",
            "success": bool(raw_result.get("success", False)),
            "summary": str(raw_result.get("summary") or ""),
            "messages": raw_result.get("messages"),
            "error": raw_result.get("error"),
            "adb_calls": merged_adb_calls,
            "gui_task_calls": merged_gui_task_calls,
            "deeplink_calls": _coerce_int(lane_stats.get("deeplink_calls")),
            "gui_steps": _coerce_int(lane_stats.get("gui_steps")),
            "trace_refs": merged_trace_refs,
            "gui_screenshot_refs": merged_screenshot_refs,
            "gui_artifacts_root": _path_str_if_exists(raw_result.get("gui_artifacts_root")),
            "gui_task_total_latency_ms": gui_task_total_latency_ms,
            "gui_task_avg_latency_ms": gui_task_avg_latency_ms,
            "token_usage_main": main_usage,
            "token_usage_gui_task": gui_usage,
            "token_usage_total": total_usage,
            "token_usage_incomplete": token_usage_incomplete,
            "gui_task_max_calls": gui_task_max_calls,
            "gui_task_calls_executed": gui_task_calls_executed,
            "gui_task_call_cap_reached": gui_task_call_cap_reached,
            "timeout_triggered": False,
            "timeout_reason": None,
            "watchdog_triggered": False,
            "no_log_watchdog_seconds": self._derive_no_log_watchdog_seconds(),
            "execution_cancelled": False,
            "effective_timeout_seconds": timeout_seconds,
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
        task_goal = str(self._state.get("task_goal", payload.task_name) or payload.task_name)

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
                "gui_screenshot_refs": [],
                "token_usage_main": _empty_token_usage(),
                "token_usage_gui_task": _empty_token_usage(),
                "token_usage_total": _empty_token_usage(),
                "token_usage_incomplete": True,
                "gui_task_max_calls": _coerce_int(
                    self._state.get("nanobot_gui_task_max_calls"),
                    default=3,
                ),
                "gui_task_calls_executed": 0,
                "gui_task_call_cap_reached": False,
                "timeout_triggered": False,
                "timeout_reason": None,
                "watchdog_triggered": False,
                "no_log_watchdog_seconds": self._derive_no_log_watchdog_seconds(),
                "execution_cancelled": False,
                "effective_timeout_seconds": self._derive_execution_timeout_seconds(),
            }
            execution_source = "nanobot_loop_error"

        pure_answer_required = _goal_requires_pure_answer(task_goal, payload.task_name)
        derived_answer_text: str | None = None
        if pure_answer_required:
            derived_answer_text = _extract_pure_answer_text(
                str(mixed_result.get("summary") or "")
            )
            if not derived_answer_text:
                derived_answer_text = _extract_answer_from_message_tool_calls(
                    mixed_result.get("messages")
                    if isinstance(mixed_result.get("messages"), list)
                    else None
                )
            derived_answer_text = _normalize_answer_for_task(
                task_name=payload.task_name,
                answer_text=derived_answer_text,
                summary_text=str(mixed_result.get("summary") or ""),
            )

        token_usage_main = _normalize_token_usage(mixed_result.get("token_usage_main"))
        token_usage_gui_task = _normalize_token_usage(mixed_result.get("token_usage_gui_task"))
        token_usage_total = _normalize_token_usage(mixed_result.get("token_usage_total"))
        if not _token_usage_has_signal(token_usage_total):
            token_usage_total = _add_token_usage(token_usage_main, token_usage_gui_task)
        token_usage_incomplete = _coerce_bool(
            mixed_result.get("token_usage_incomplete"),
            default=False,
        )
        gui_task_max_calls = _coerce_int(
            mixed_result.get("gui_task_max_calls"),
            default=_coerce_int(self._state.get("nanobot_gui_task_max_calls"), default=3),
        )
        gui_task_calls_executed = _coerce_int(
            mixed_result.get("gui_task_calls_executed"),
            default=_coerce_int(mixed_result.get("gui_task_calls")),
        )
        gui_task_call_cap_reached = bool(mixed_result.get("gui_task_call_cap_reached", False))

        self._task_executed = True
        self._mixed_summary = {
            "execution_mode": "mixed",
            "evaluation_mode": self._state.get("evaluation_mode", "mixed"),
            "allow_adb_bypass": bool(self._state.get("allow_adb_bypass", True)),
            "nanobot_max_steps": self._state.get("nanobot_max_steps"),
            "nanobot_enable_planner": bool(self._state.get("nanobot_enable_planner", False)),
            "nanobot_enable_router": bool(self._state.get("nanobot_enable_router", False)),
            "nanobot_timeout_seconds": self._derive_execution_timeout_seconds(),
            "nanobot_gui_task_max_steps": _coerce_int(
                self._state.get("nanobot_gui_task_max_steps"),
                default=50,
            ),
            "nanobot_gui_task_max_calls": _coerce_int(
                self._state.get("nanobot_gui_task_max_calls"),
                default=3,
            ),
            "nanobot_no_log_watchdog_seconds": _coerce_int(
                self._state.get("nanobot_no_log_watchdog_seconds"),
                default=120,
            ),
            "timeout_triggered": bool(mixed_result.get("timeout_triggered", False)),
            "timeout_reason": mixed_result.get("timeout_reason"),
            "watchdog_triggered": bool(mixed_result.get("watchdog_triggered", False)),
            "no_log_watchdog_seconds": mixed_result.get("no_log_watchdog_seconds"),
            "execution_cancelled": bool(mixed_result.get("execution_cancelled", False)),
            "effective_timeout_seconds": mixed_result.get("effective_timeout_seconds"),
            "adb_calls": _coerce_int(mixed_result.get("adb_calls")),
            "gui_task_calls": _coerce_int(mixed_result.get("gui_task_calls")),
            "deeplink_calls": _coerce_int(mixed_result.get("deeplink_calls")),
            "gui_steps": _coerce_int(mixed_result.get("gui_steps")),
            "gui_task_total_latency_ms": mixed_result.get("gui_task_total_latency_ms"),
            "gui_task_avg_latency_ms": mixed_result.get("gui_task_avg_latency_ms"),
            "token_usage_main": token_usage_main,
            "token_usage_gui_task": token_usage_gui_task,
            "token_usage_total": token_usage_total,
            "token_usage_incomplete": token_usage_incomplete,
            "gui_task_max_calls": gui_task_max_calls,
            "gui_task_calls_executed": gui_task_calls_executed,
            "gui_task_call_cap_reached": gui_task_call_cap_reached,
            "trace_refs": list(mixed_result.get("trace_refs") or []),
            "gui_screenshot_refs": list(mixed_result.get("gui_screenshot_refs") or []),
            "gui_artifacts_root": mixed_result.get("gui_artifacts_root"),
            "success": bool(mixed_result.get("success", False)),
            "summary": str(mixed_result.get("summary") or ""),
            "error": mixed_result.get("error"),
            "derived_answer_text": derived_answer_text,
        }

        action_payload: dict[str, Any]
        if derived_answer_text:
            action_payload = {"action_type": "answer", "text": derived_answer_text}
        else:
            action_payload = {"action_type": "finished"}

        return AdapterStepResult(
            prediction=str(mixed_result.get("summary") or "nanobot_mixed_execution_completed"),
            action=action_payload,
            done=True,
            info={
                "framework": "nanobot_opengui",
                "execution_mode": "mixed",
                "allow_adb_bypass": bool(self._state.get("allow_adb_bypass", True)),
                "nanobot_max_steps": self._state.get("nanobot_max_steps"),
                "nanobot_gui_task_max_steps": _coerce_int(
                    self._state.get("nanobot_gui_task_max_steps"),
                    default=50,
                ),
                "nanobot_gui_task_max_calls": _coerce_int(
                    self._state.get("nanobot_gui_task_max_calls"),
                    default=3,
                ),
                "nanobot_no_log_watchdog_seconds": _coerce_int(
                    self._state.get("nanobot_no_log_watchdog_seconds"),
                    default=120,
                ),
                "execution_source": execution_source,
                "token_usage": token_usage_total,
                "nanobot_success": bool(mixed_result.get("success", False)),
                "nanobot_error": mixed_result.get("error"),
                "token_usage_incomplete": token_usage_incomplete,
                "gui_task_calls_executed": gui_task_calls_executed,
                "gui_task_call_cap_reached": gui_task_call_cap_reached,
                "timeout_triggered": bool(mixed_result.get("timeout_triggered", False)),
                "timeout_reason": mixed_result.get("timeout_reason"),
                "watchdog_triggered": bool(mixed_result.get("watchdog_triggered", False)),
                "no_log_watchdog_seconds": mixed_result.get("no_log_watchdog_seconds"),
                "execution_cancelled": bool(mixed_result.get("execution_cancelled", False)),
                "effective_timeout_seconds": mixed_result.get("effective_timeout_seconds"),
                "pure_answer_required": pure_answer_required,
                "derived_answer_text": derived_answer_text,
                "gui_screenshot_count": len(mixed_result.get("gui_screenshot_refs") or []),
                "gui_task_avg_latency_ms": mixed_result.get("gui_task_avg_latency_ms"),
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
            "nanobot_max_steps": self._state.get("nanobot_max_steps"),
            "nanobot_enable_planner": bool(self._state.get("nanobot_enable_planner", False)),
            "nanobot_enable_router": bool(self._state.get("nanobot_enable_router", False)),
            "nanobot_timeout_seconds": self._derive_execution_timeout_seconds(),
            "nanobot_gui_task_max_steps": _coerce_int(
                self._state.get("nanobot_gui_task_max_steps"),
                default=50,
            ),
            "nanobot_gui_task_max_calls": _coerce_int(
                self._state.get("nanobot_gui_task_max_calls"),
                default=3,
            ),
            "nanobot_no_log_watchdog_seconds": _coerce_int(
                self._state.get("nanobot_no_log_watchdog_seconds"),
                default=120,
            ),
            "timeout_triggered": bool((self._mixed_summary or {}).get("timeout_triggered", False)),
            "timeout_reason": (self._mixed_summary or {}).get("timeout_reason"),
            "watchdog_triggered": bool((self._mixed_summary or {}).get("watchdog_triggered", False)),
            "no_log_watchdog_seconds": (self._mixed_summary or {}).get("no_log_watchdog_seconds"),
            "execution_cancelled": bool((self._mixed_summary or {}).get("execution_cancelled", False)),
            "effective_timeout_seconds": (self._mixed_summary or {}).get("effective_timeout_seconds"),
            "adb_calls": _coerce_int((self._mixed_summary or {}).get("adb_calls")),
            "gui_task_calls": _coerce_int((self._mixed_summary or {}).get("gui_task_calls")),
            "deeplink_calls": _coerce_int((self._mixed_summary or {}).get("deeplink_calls")),
            "gui_steps": _coerce_int((self._mixed_summary or {}).get("gui_steps")),
            "gui_task_total_latency_ms": (self._mixed_summary or {}).get("gui_task_total_latency_ms"),
            "gui_task_avg_latency_ms": (self._mixed_summary or {}).get("gui_task_avg_latency_ms"),
            "token_usage_main": _normalize_token_usage((self._mixed_summary or {}).get("token_usage_main")),
            "token_usage_gui_task": _normalize_token_usage((self._mixed_summary or {}).get("token_usage_gui_task")),
            "token_usage_total": _normalize_token_usage((self._mixed_summary or {}).get("token_usage_total")),
            "token_usage_incomplete": bool((self._mixed_summary or {}).get("token_usage_incomplete", False)),
            "gui_task_max_calls": _coerce_int((self._mixed_summary or {}).get("gui_task_max_calls"), default=0),
            "gui_task_calls_executed": _coerce_int((self._mixed_summary or {}).get("gui_task_calls_executed"), default=0),
            "gui_task_call_cap_reached": bool((self._mixed_summary or {}).get("gui_task_call_cap_reached", False)),
            "trace_refs": list((self._mixed_summary or {}).get("trace_refs") or []),
            "gui_screenshot_refs": list((self._mixed_summary or {}).get("gui_screenshot_refs") or []),
            "gui_artifacts_root": (self._mixed_summary or {}).get("gui_artifacts_root"),
            "nanobot_success": bool((self._mixed_summary or {}).get("success", False)),
            "nanobot_summary": (self._mixed_summary or {}).get("summary"),
            "nanobot_error": (self._mixed_summary or {}).get("error"),
            "derived_answer_text": (self._mixed_summary or {}).get("derived_answer_text"),
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
                    artifact_type="nanobot_gui_trace",
                    description="GUI trace path reported by nanobot mixed execution",
                    metadata={
                        "task_name": payload.task_name,
                        "run_id": payload.run_id,
                    },
                )
            )
        for screenshot_ref in mixed_summary["gui_screenshot_refs"]:
            self._artifacts.append(
                ArtifactRecord(
                    path=str(screenshot_ref),
                    artifact_type="nanobot_gui_screenshot",
                    description="GUI screenshot captured during nanobot gui_task execution",
                    metadata={
                        "task_name": payload.task_name,
                        "run_id": payload.run_id,
                    },
                )
            )
        gui_artifacts_root = mixed_summary.get("gui_artifacts_root")
        if isinstance(gui_artifacts_root, str) and gui_artifacts_root.strip():
            self._artifacts.append(
                ArtifactRecord(
                    path=gui_artifacts_root,
                    artifact_type="nanobot_gui_artifacts_root",
                    description="Root directory that stores gui_task traces and screenshots",
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
