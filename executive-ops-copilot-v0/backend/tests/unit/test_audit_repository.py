from app.db.audit import ActorContext, AuditEvent, AuditRepository
from app.db.session import Database


def test_ai_audit_logging_round_trip(tmp_path):
    repository = AuditRepository(Database(f"sqlite:///{tmp_path / 'audit.db'}"))
    actor = ActorContext(actor_id="ea-1", email="ea@example.com", display_name="EA User")

    event_id = repository.add_ai_event(
        AuditEvent(
            actor=actor,
            operation="parse_request",
            endpoint="/api/requests/parse",
            model_name="gemma4:latest",
            model_status="used",
            status="success",
            latency_ms=42,
            request_payload={"raw_text": "Need 30 min"},
            response_payload={"intent": {"requester": "Jordan"}},
            runtime="google-adk",
            agent_name="meeting_request_parser_agent",
            tool_calls=[],
        )
    )

    events = repository.list_ai_events()

    assert events[0]["id"] == event_id
    assert events[0]["actor_id"] == "ea-1"
    assert events[0]["operation"] == "parse_request"
    assert events[0]["model_name"] == "gemma4:latest"
    assert events[0]["runtime"] == "google-adk"
    assert events[0]["agent_name"] == "meeting_request_parser_agent"
    assert events[0]["tool_calls"] == []
    assert events[0]["request_payload"]["raw_text"] == "Need 30 min"
    assert events[0]["response_payload"]["intent"]["requester"] == "Jordan"


def test_ai_metrics_summarize_adk_quality_and_tool_coverage(tmp_path):
    repository = AuditRepository(Database(f"sqlite:///{tmp_path / 'audit.db'}"))
    actor = ActorContext(actor_id="admin-1")
    repository.add_ai_event(
        AuditEvent(
            actor=actor,
            operation="generate_recommendation",
            endpoint="/api/recommendations/generate",
            model_name="ollama_chat/gemma4:latest",
            model_status="used",
            status="success",
            latency_ms=100,
            request_payload={},
            response_payload={},
            runtime="google-adk",
            agent_name="meeting_resolution_agent",
            tool_calls=["inspect_calendar_conflicts", "validate_scheduling_rules"],
        )
    )
    repository.add_ai_event(
        AuditEvent(
            actor=actor,
            operation="generate_draft",
            endpoint="/api/drafts/generate",
            model_name="ollama_chat/gemma4:latest",
            model_status="unavailable",
            status="error",
            latency_ms=300,
            request_payload={},
            runtime="google-adk",
            agent_name="meeting_draft_agent",
            tool_calls=[],
            error_code="ollama_unavailable",
        )
    )

    metrics = repository.ai_metrics()

    assert metrics["total_events"] == 2
    assert metrics["success_rate"] == 0.5
    assert metrics["adk_coverage"] == 1.0
    assert metrics["tool_call_coverage"] == 0.5
    assert metrics["model_status_counts"] == {"unavailable": 1, "used": 1}
    assert metrics["recent_failures"][0]["operation"] == "generate_draft"
