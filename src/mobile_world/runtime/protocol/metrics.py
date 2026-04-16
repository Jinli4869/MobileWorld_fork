"""Metrics collection helpers for KPI instrumentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mobile_world.runtime.protocol.events import MetricsQualityFlags
from mobile_world.runtime.protocol.normalization import normalize_metrics_event


def _safe_ms(seconds: float) -> float:
    return round(max(seconds, 0.0) * 1000.0, 3)


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return round(values[0], 3)
    sorted_values = sorted(values)
    idx = (len(sorted_values) - 1) * q
    lower = int(idx)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = idx - lower
    value = sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight
    return round(value, 3)


def _empty_usage() -> dict[str, int]:
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_tokens": 0,
        "total_tokens": 0,
    }


def _normalize_usage(usage: dict[str, int] | None) -> dict[str, int]:
    normalized = _empty_usage()
    if not usage:
        return normalized
    for key in normalized:
        normalized[key] = max(int(usage.get(key, 0) or 0), 0)
    if "total_tokens" not in usage:
        normalized["total_tokens"] = normalized["prompt_tokens"] + normalized["completion_tokens"]
    return normalized


def _delta_usage(current: dict[str, int], previous: dict[str, int]) -> dict[str, int]:
    delta = {}
    for key in _empty_usage():
        delta[key] = max(current.get(key, 0) - previous.get(key, 0), 0)
    if delta["total_tokens"] == 0:
        delta["total_tokens"] = delta["prompt_tokens"] + delta["completion_tokens"]
    return delta


@dataclass
class StepMetric:
    step: int
    action_type: str | None
    predict_latency_ms: float
    step_latency_ms: float
    token_usage_step: dict[str, int]
    token_usage_total: dict[str, int]
    tool_latency_ms: float | None
    tool_attempted: bool
    tool_success: bool
    tool_retry: bool
    invalid_action: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "action_type": self.action_type,
            "predict_latency_ms": self.predict_latency_ms,
            "step_latency_ms": self.step_latency_ms,
            "token_usage_step": self.token_usage_step,
            "token_usage_total": self.token_usage_total,
            "tool_latency_ms": self.tool_latency_ms,
            "tool_attempted": self.tool_attempted,
            "tool_success": self.tool_success,
            "tool_retry": self.tool_retry,
            "invalid_action": self.invalid_action,
        }


@dataclass
class MetricsCollector:
    """Collect and aggregate per-step KPI telemetry."""

    task_name: str
    run_id: str
    task_started_at: float
    _last_total_usage: dict[str, int] = field(default_factory=_empty_usage)
    _steps: list[StepMetric] = field(default_factory=list)
    _first_token_latency_ms: float | None = None
    _first_action_ms: float | None = None

    def preview_step(
        self,
        *,
        step: int,
        action_type: str | None,
        step_started_at: float,
        prediction_done_at: float,
        total_usage: dict[str, int] | None,
    ) -> dict[str, Any]:
        current_total = _normalize_usage(total_usage)
        step_usage = _delta_usage(current_total, self._last_total_usage)
        predict_latency_ms = _safe_ms(prediction_done_at - step_started_at)
        if self._first_token_latency_ms is None:
            if step_usage["total_tokens"] > 0:
                self._first_token_latency_ms = predict_latency_ms
            elif step == 1:
                # Fallback policy when provider does not expose token deltas:
                # use first model turn wall-clock latency as estimated TTFT.
                self._first_token_latency_ms = predict_latency_ms
        return {
            "step": step,
            "action_type": action_type,
            "step_started_at": step_started_at,
            "predict_latency_ms": predict_latency_ms,
            "token_usage_step": step_usage,
            "token_usage_total": current_total,
        }

    def complete_step(
        self,
        *,
        step_preview: dict[str, Any],
        step_finished_at: float,
        tool_latency_ms: float | None,
        tool_attempted: bool,
        tool_success: bool,
        tool_retry: bool,
        invalid_action: bool,
    ) -> dict[str, Any]:
        step_latency_ms = _safe_ms(step_finished_at - (step_preview["step_started_at"]))
        if self._first_action_ms is None and tool_attempted:
            self._first_action_ms = _safe_ms(step_finished_at - self.task_started_at)
        metric = StepMetric(
            step=step_preview["step"],
            action_type=step_preview["action_type"],
            predict_latency_ms=step_preview["predict_latency_ms"],
            step_latency_ms=step_latency_ms,
            token_usage_step=step_preview["token_usage_step"],
            token_usage_total=step_preview["token_usage_total"],
            tool_latency_ms=tool_latency_ms,
            tool_attempted=tool_attempted,
            tool_success=tool_success,
            tool_retry=tool_retry,
            invalid_action=invalid_action,
        )
        self._last_total_usage = step_preview["token_usage_total"]
        self._steps.append(metric)
        return metric.as_dict()

    def finalize(self, *, score_recorded_at: float) -> tuple[dict[str, Any], Any]:
        total_steps = len(self._steps)
        total_usage = self._last_total_usage
        per_step_total_tokens = [item.token_usage_step["total_tokens"] for item in self._steps]
        step_latencies = [item.step_latency_ms for item in self._steps]
        tool_latencies = [item.tool_latency_ms for item in self._steps if item.tool_latency_ms is not None]

        tool_calls = sum(1 for item in self._steps if item.tool_attempted)
        tool_successes = sum(1 for item in self._steps if item.tool_attempted and item.tool_success)
        tool_retries = sum(1 for item in self._steps if item.tool_retry)
        invalid_actions = sum(1 for item in self._steps if item.invalid_action)

        ttft_ms = self._first_token_latency_ms
        ttfa_ms = self._first_action_ms
        tts_ms = _safe_ms(score_recorded_at - self.task_started_at)

        quality_flags = MetricsQualityFlags(
            token_usage="native" if total_usage["total_tokens"] > 0 else "unavailable",
            latency="estimated" if total_steps > 0 else "unavailable",
            cost="unavailable",
        )
        token_usage_summary = {
            "total": total_usage,
            "per_step_total_tokens": per_step_total_tokens,
            "avg_total_tokens_per_step": round(sum(per_step_total_tokens) / total_steps, 3)
            if total_steps
            else 0.0,
            "source": "native" if total_usage["total_tokens"] > 0 else "unavailable",
        }
        latency_summary = {
            "ttft_ms": ttft_ms,
            "ttfa_ms": ttfa_ms,
            "tts_ms": tts_ms,
            "ttft_source": "estimated_from_predict_latency" if ttft_ms is not None else "unavailable",
            "ttfa_source": "estimated_from_first_tool_action" if ttfa_ms is not None else "unavailable",
            "tts_source": "estimated_from_task_wallclock",
            "step_latency_ms": {
                "p50": _percentile(step_latencies, 0.50),
                "p95": _percentile(step_latencies, 0.95),
            },
            "tool_latency_ms": {
                "p50": _percentile(tool_latencies, 0.50),
                "p95": _percentile(tool_latencies, 0.95),
            },
        }
        reliability_summary = {
            "total_steps": total_steps,
            "tool_calls": tool_calls,
            "tool_successes": tool_successes,
            "tool_retries": tool_retries,
            "invalid_actions": invalid_actions,
            "tool_success_rate": round(tool_successes / tool_calls, 6) if tool_calls else 1.0,
            "tool_retry_rate": round(tool_retries / tool_calls, 6) if tool_calls else 0.0,
            "invalid_action_rate": round(invalid_actions / total_steps, 6) if total_steps else 0.0,
        }
        summary = {
            "quality_flags": quality_flags.model_dump(),
            "token_usage": token_usage_summary,
            "latency": latency_summary,
            "reliability": reliability_summary,
            "cost": {"cost_per_success": None, "source": "unavailable"},
            "per_step": [item.as_dict() for item in self._steps],
        }
        event = normalize_metrics_event(
            task_name=self.task_name,
            run_id=self.run_id,
            quality_flags=quality_flags,
            token_usage=token_usage_summary,
            latency=latency_summary,
            reliability=reliability_summary,
            cost={"cost_per_success": None},
            info={"step_count": total_steps},
        )
        return summary, event
