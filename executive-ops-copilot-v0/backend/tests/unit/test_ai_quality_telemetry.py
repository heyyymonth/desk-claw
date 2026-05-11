from app.telemetry.ai_quality import build_ai_quality_dashboard


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
