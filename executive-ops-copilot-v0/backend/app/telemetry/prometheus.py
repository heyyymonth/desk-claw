from typing import Any

PROMETHEUS_TEXT_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def build_prometheus_metrics(
    *,
    health: dict[str, Any],
    ai_dashboard: dict[str, Any] | None,
    scrape_error: str | None = None,
) -> str:
    lines: list[str] = []
    _gauge(lines, "desk_ai_backend_health_status", "Backend health status from /api/health.", 1, {"status": health.get("status", "unknown")})
    _gauge(
        lines,
        "desk_ai_backend_info",
        "Backend runtime configuration metadata.",
        1,
        {
            "model": health.get("model", "unknown"),
            "model_runtime": health.get("model_runtime", "unknown"),
            "ollama": health.get("ollama", "unknown"),
        },
    )

    warmup = health.get("model_warmup") if isinstance(health.get("model_warmup"), dict) else {}
    warmup_status = str(warmup.get("status", "unknown"))
    _gauge(lines, "desk_ai_model_warmup_ready", "Whether startup model warmup is ready.", 1 if warmup_status == "ready" else 0, {"status": warmup_status})
    _optional_gauge(lines, "desk_ai_model_warmup_elapsed_seconds", "Total backend-observed startup warmup seconds.", warmup.get("elapsed_seconds"))
    _optional_gauge(lines, "desk_ai_ollama_warmup_total_seconds", "Ollama-reported warmup request seconds.", warmup.get("ollama_total_seconds"))
    _optional_gauge(lines, "desk_ai_ollama_warmup_load_seconds", "Ollama-reported model load seconds during warmup.", warmup.get("ollama_load_seconds"))

    _gauge(lines, "desk_ai_telemetry_scrape_error", "Whether the telemetry read model failed during this scrape.", 1 if scrape_error else 0, {"error_type": scrape_error or "none"})
    if ai_dashboard is None:
        return "\n".join(lines) + "\n"

    _gauge(lines, "desk_ai_ai_events_observed", "AI audit events in the telemetry sample window.", ai_dashboard.get("total_events", 0))
    _gauge(lines, "desk_ai_ai_success_ratio", "AI workflow success ratio in the telemetry sample window.", ai_dashboard.get("success_rate", 0))
    _gauge(lines, "desk_ai_ai_adk_coverage_ratio", "Share of sampled AI events that used Google ADK.", ai_dashboard.get("adk_coverage", 0))
    _gauge(lines, "desk_ai_ai_tool_call_coverage_ratio", "Share of sampled ADK events with tool traces.", ai_dashboard.get("tool_call_coverage", 0))
    _gauge(lines, "desk_ai_ai_latency_ms", "AI workflow latency in milliseconds.", ai_dashboard.get("avg_latency_ms", 0), {"stat": "avg"})
    _gauge(lines, "desk_ai_ai_latency_ms", "AI workflow latency in milliseconds.", ai_dashboard.get("p95_latency_ms", 0), {"stat": "p95"})

    for model_status, count in sorted(ai_dashboard.get("model_status_counts", {}).items()):
        _gauge(lines, "desk_ai_ai_model_status_events", "AI events by model status.", count, {"model_status": model_status})

    for operation in ai_dashboard.get("operation_metrics", []):
        labels = {"operation": operation.get("operation", "unknown")}
        _gauge(lines, "desk_ai_ai_operation_events", "AI events by operation.", operation.get("total", 0), labels)
        _gauge(lines, "desk_ai_ai_operation_success_ratio", "AI success ratio by operation.", operation.get("success_rate", 0), labels)
        _gauge(lines, "desk_ai_ai_operation_adk_coverage_ratio", "ADK coverage by operation.", operation.get("adk_coverage", 0), labels)
        _gauge(lines, "desk_ai_ai_operation_latency_ms", "Average AI latency by operation.", operation.get("avg_latency_ms", 0), labels | {"stat": "avg"})
        _gauge(lines, "desk_ai_ai_operation_tool_calls_avg", "Average tool calls by operation.", operation.get("tool_calls_avg", 0), labels)
        for model_status, count in sorted(operation.get("model_status_counts", {}).items()):
            _gauge(lines, "desk_ai_ai_operation_model_status_events", "AI model status counts by operation.", count, labels | {"model_status": model_status})

    for tool in ai_dashboard.get("tool_metrics", []):
        labels = {"tool_name": tool.get("tool_name", "unknown")}
        _gauge(lines, "desk_ai_ai_tool_calls", "Sampled AI tool calls by tool.", tool.get("calls", 0), labels)
        _gauge(lines, "desk_ai_ai_tool_failures", "Sampled AI tool failures by tool.", tool.get("failure_count", 0), labels)
        _gauge(lines, "desk_ai_ai_tool_success_ratio", "Sampled AI tool success ratio by tool.", tool.get("success_rate", 0), labels)
        _gauge(lines, "desk_ai_ai_tool_latency_ms", "Average AI event latency for calls involving this tool.", tool.get("avg_latency_ms", 0), labels | {"stat": "avg"})
        for reason, count in sorted(tool.get("failure_reasons", {}).items()):
            _gauge(lines, "desk_ai_ai_tool_failure_reasons", "Sampled AI tool failures by reason.", count, labels | {"reason": reason})

    _gauge(lines, "desk_ai_ai_recent_failures_observed", "Recent failed or degraded AI events in the telemetry sample.", len(ai_dashboard.get("recent_failures", [])))
    return "\n".join(lines) + "\n"


def _optional_gauge(lines: list[str], name: str, help_text: str, value: Any) -> None:
    if value is not None:
        _gauge(lines, name, help_text, value)


def _gauge(lines: list[str], name: str, help_text: str, value: Any, labels: dict[str, Any] | None = None) -> None:
    if not any(line == f"# HELP {name} {help_text}" for line in lines):
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
    suffix = _labels(labels or {})
    lines.append(f"{name}{suffix} {_number(value)}")


def _labels(labels: dict[str, Any]) -> str:
    if not labels:
        return ""
    rendered = ",".join(f'{key}="{_escape_label(value)}"' for key, value in sorted(labels.items()))
    return "{" + rendered + "}"


def _escape_label(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _number(value: Any) -> str:
    try:
        return str(float(value))
    except (TypeError, ValueError):
        return "0.0"
