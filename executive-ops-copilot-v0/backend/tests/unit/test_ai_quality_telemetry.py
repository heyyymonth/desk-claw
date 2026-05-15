from app.telemetry.ai_quality import build_ai_quality_dashboard
from app.telemetry.prometheus import build_prometheus_metrics


def test_ai_quality_dashboard_identifies_tool_and_model_failures():
    dashboard = build_ai_quality_dashboard(
        [
            {
                "id": "evt-1",
                "created_at": "2026-05-11T10:00:00Z",
                "operation": "generate_recommendation",
                "model_name": "ollama_chat/gemma4:latest",
                "model_status": "used",
                "runtime": "google-adk",
                "agent_name": "meeting_resolution_agent",
                "latency_ms": 200,
                "status": "success",
                "error_code": None,
                "error_message": None,
                "tool_calls": ["inspect_calendar_conflicts", "validate_scheduling_rules"],
            },
            {
                "id": "evt-2",
                "created_at": "2026-05-11T10:01:00Z",
                "operation": "generate_recommendation",
                "model_name": "ollama_chat/gemma4:latest",
                "model_status": "unavailable",
                "runtime": "google-adk",
                "agent_name": "meeting_resolution_agent",
                "latency_ms": 45000,
                "status": "error",
                "error_code": "adk_model_unavailable",
                "error_message": "Connection refused",
                "tool_calls": ["inspect_calendar_conflicts"],
            },
        ]
    )

    assert dashboard["total_events"] == 2
    assert dashboard["success_rate"] == 0.5
    assert dashboard["adk_coverage"] == 1.0
    assert dashboard["tool_metrics"][0]["tool_name"] == "inspect_calendar_conflicts"
    assert dashboard["tool_metrics"][0]["failure_count"] == 1
    assert any(insight["reason"] == "model_unavailable_or_connection_failed" for insight in dashboard["insights"])


def test_prometheus_export_includes_health_latency_and_tool_failure_metrics():
    text = build_prometheus_metrics(
        health={
            "status": "ok",
            "model": "ollama_chat/gemma4:latest",
            "model_runtime": "google-adk",
            "ollama": "configured",
            "model_warmup": {"status": "ready", "elapsed_seconds": 4.2, "ollama_load_seconds": 2.1},
        },
        ai_dashboard={
            "total_events": 2,
            "success_rate": 0.5,
            "adk_coverage": 1.0,
            "tool_call_coverage": 1.0,
            "avg_latency_ms": 22600,
            "p95_latency_ms": 45000,
            "model_status_counts": {"used": 1, "unavailable": 1},
            "operation_metrics": [
                {
                    "operation": "generate_recommendation",
                    "total": 2,
                    "success_rate": 0.5,
                    "adk_coverage": 1.0,
                    "avg_latency_ms": 22600,
                    "tool_calls_avg": 1.5,
                    "model_status_counts": {"used": 1, "unavailable": 1},
                }
            ],
            "tool_metrics": [
                {
                    "tool_name": 'inspect_calendar_conflicts"\n',
                    "calls": 2,
                    "failure_count": 1,
                    "success_rate": 0.5,
                    "avg_latency_ms": 22600,
                    "failure_reasons": {"adk_model_unavailable": 1},
                }
            ],
            "recent_failures": [{"id": "evt-2"}],
        },
    )

    assert 'desk_ai_backend_health_status{status="ok"} 1.0' in text
    assert "desk_ai_model_warmup_elapsed_seconds 4.2" in text
    assert 'desk_ai_ai_latency_ms{stat="p95"} 45000.0' in text
    assert 'desk_ai_ai_tool_failures{tool_name="inspect_calendar_conflicts\\"\\n"} 1.0' in text
    assert 'desk_ai_ai_tool_failure_reasons{reason="adk_model_unavailable",tool_name="inspect_calendar_conflicts\\"\\n"} 1.0' in text
