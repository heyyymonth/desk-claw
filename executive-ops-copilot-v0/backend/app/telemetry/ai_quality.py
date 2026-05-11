from typing import Any, Iterable


def build_ai_quality_dashboard(events: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(events)
    if total == 0:
        return {
            "total_events": 0,
            "success_rate": 0.0,
            "adk_coverage": 0.0,
            "tool_call_coverage": 0.0,
            "avg_latency_ms": 0,
            "p95_latency_ms": 0,
            "model_status_counts": {},
            "operation_metrics": [],
            "tool_metrics": [],
            "insights": [
                {
                    "severity": "info",
                    "title": "No AI telemetry yet",
                    "detail": "Run parse, recommendation, or draft workflows to populate the technical dashboard.",
                    "reason": "empty_telemetry_window",
                }
            ],
            "slowest_events": [],
            "recent_failures": [],
        }

    successful = [event for event in events if event["status"] == "success"]
    adk_events = [event for event in events if event["runtime"] == "google-adk"]
    tool_events = [event for event in adk_events if event.get("tool_calls")]
    latencies = sorted(int(event["latency_ms"]) for event in events)
    operations = sorted({event["operation"] for event in events})
    tool_metrics = _tool_metrics(events)
    recent_failures = [
        _event_summary(event)
        for event in events
        if event["status"] != "success" or event["model_status"] in {"unavailable", "invalid_output"}
    ][:5]

    dashboard = {
        "total_events": total,
        "success_rate": round(len(successful) / total, 3),
        "adk_coverage": round(len(adk_events) / total, 3),
        "tool_call_coverage": round(len(tool_events) / max(1, len(adk_events)), 3),
        "avg_latency_ms": round(sum(latencies) / total),
        "p95_latency_ms": _percentile(latencies, 0.95),
        "model_status_counts": _counts(event["model_status"] for event in events),
        "operation_metrics": [_operation_metric(operation, events) for operation in operations],
        "tool_metrics": tool_metrics,
        "slowest_events": [
            _event_summary(event)
            for event in sorted(events, key=lambda row: int(row["latency_ms"]), reverse=True)[:5]
        ],
        "recent_failures": recent_failures,
    }
    dashboard["insights"] = _insights(dashboard, events)
    return dashboard


def _insights(dashboard: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []
    unavailable = [event for event in events if event["model_status"] == "unavailable"]
    invalid = [event for event in events if event["model_status"] == "invalid_output"]
    adk_events = [event for event in events if event["runtime"] == "google-adk"]
    adk_without_tools = [event for event in adk_events if not event.get("tool_calls")]

    if dashboard["adk_coverage"] < 1.0:
        insights.append(
            {
                "severity": "warning",
                "title": "Some AI workflow events did not use ADK",
                "detail": "Events with deterministic runtime indicate fallback or mock mode. Production AI model calls should remain on the ADK path.",
                "reason": "adk_coverage_gap",
            }
        )
    if unavailable:
        sample = unavailable[0]
        insights.append(
            {
                "severity": "critical",
                "title": "Configured model unavailable before completion",
                "detail": sample.get("error_message") or "The ADK runner could not complete against the configured model endpoint.",
                "operation": sample["operation"],
                "agent_name": sample.get("agent_name"),
                "reason": "model_unavailable_or_connection_failed",
            }
        )
    if invalid:
        sample = invalid[0]
        insights.append(
            {
                "severity": "critical",
                "title": "Model returned invalid structured output",
                "detail": sample.get("error_message") or "The ADK output could not be validated against the backend contract.",
                "operation": sample["operation"],
                "agent_name": sample.get("agent_name"),
                "reason": "model_output_validation_failed",
            }
        )
    if adk_without_tools:
        insights.append(
            {
                "severity": "info",
                "title": "ADK events without tool traces",
                "detail": "Parser and draft agents may not need tools; recommendation events should show calendar, rules, risk, and strategy tools.",
                "reason": "missing_or_not_applicable_tool_trace",
            }
        )
    if dashboard["p95_latency_ms"] > 30000:
        insights.append(
            {
                "severity": "warning",
                "title": "High p95 AI latency",
                "detail": "The slowest ADK or fallback events are exceeding 30 seconds and should be checked against model endpoint health and prompt/tool-call loops.",
                "reason": "high_latency",
            }
        )
    if not insights:
        insights.append(
            {
                "severity": "info",
                "title": "AI telemetry window is healthy",
                "detail": "No unavailable models, invalid outputs, or latency warnings were detected in the current sample.",
                "reason": "healthy_window",
            }
        )
    return insights


def _tool_metrics(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tool_names = sorted({tool for event in events for tool in event.get("tool_calls", [])})
    metrics = []
    for tool in tool_names:
        rows = [event for event in events if tool in event.get("tool_calls", [])]
        failures = [event for event in rows if event["status"] != "success" or event["model_status"] in {"unavailable", "invalid_output"}]
        metrics.append(
            {
                "tool_name": tool,
                "calls": len(rows),
                "failure_count": len(failures),
                "success_rate": round((len(rows) - len(failures)) / len(rows), 3) if rows else 0.0,
                "avg_latency_ms": round(sum(int(event["latency_ms"]) for event in rows) / len(rows)) if rows else 0,
                "failure_reasons": _counts(_failure_reason(event) for event in failures),
            }
        )
    return metrics


def _failure_reason(event: dict[str, Any]) -> str:
    if event.get("error_code"):
        return str(event["error_code"])
    if event["model_status"] == "unavailable":
        return "model_unavailable_or_connection_failed"
    if event["model_status"] == "invalid_output":
        return "model_output_validation_failed"
    if event["status"] != "success":
        return "workflow_error"
    return "none"


def _counts(values: Iterable[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    index = min(len(values) - 1, round((len(values) - 1) * percentile))
    return values[index]


def _operation_metric(operation: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [event for event in events if event["operation"] == operation]
    latencies = [int(event["latency_ms"]) for event in rows]
    adk_rows = [event for event in rows if event["runtime"] == "google-adk"]
    return {
        "operation": operation,
        "total": len(rows),
        "success_rate": round(sum(1 for event in rows if event["status"] == "success") / len(rows), 3),
        "adk_coverage": round(len(adk_rows) / len(rows), 3),
        "avg_latency_ms": round(sum(latencies) / len(latencies)),
        "tool_calls_avg": round(sum(len(event["tool_calls"]) for event in rows) / len(rows), 2),
        "model_status_counts": _counts(event["model_status"] for event in rows),
    }


def _event_summary(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event["id"],
        "created_at": event["created_at"],
        "operation": event["operation"],
        "model_name": event["model_name"],
        "model_status": event["model_status"],
        "runtime": event["runtime"],
        "agent_name": event["agent_name"],
        "latency_ms": event["latency_ms"],
        "status": event["status"],
        "error_code": event["error_code"],
        "tool_calls": event["tool_calls"],
    }
