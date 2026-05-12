from app.db.audit import ActorContext, AuditEvent, AuditRepository
from app.db.session import Database
from app.services.telemetry_service import TelemetryService


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
            response_payload={"intent": {"requester": "Jordan", "title": "Meeting"}},
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
    assert events[0]["request_payload"]["raw_text"]["redacted"] is True
    assert events[0]["request_payload"]["raw_text"]["length"] == len("Need 30 min")
    assert events[0]["response_payload"]["intent"]["requester"]["redacted"] is True
    assert events[0]["response_payload"]["intent"]["title"] == "Meeting"


def test_ai_audit_payloads_do_not_persist_freeform_text(tmp_path):
    repository = AuditRepository(Database(f"sqlite:///{tmp_path / 'audit.db'}"))
    sensitive_request = "From Jordan at Acme: discuss confidential renewal blocker."
    sensitive_draft = "Hi Jordan, Dana can meet tomorrow to discuss the Acme blocker."

    repository.add_ai_event(
        AuditEvent(
            actor=ActorContext(actor_id="ea-1"),
            operation="generate_draft",
            endpoint="/api/drafts/generate",
            model_name="ollama_chat/gemma4:latest",
            model_status="used",
            status="success",
            latency_ms=42,
            request_payload={"raw_text": sensitive_request, "attendees": ["jordan@acme.example"]},
            response_payload={"subject": "Acme renewal blocker", "body": sensitive_draft},
            error_message="Failed while handling Acme renewal blocker",
            runtime="google-adk",
            agent_name="meeting_draft_agent",
            tool_calls=[],
        )
    )

    event = repository.list_ai_events()[0]
    serialized = str(event)

    assert sensitive_request not in serialized
    assert sensitive_draft not in serialized
    assert "jordan@acme.example" not in serialized
    assert "Acme renewal blocker" not in serialized
    assert event["request_payload"]["raw_text"]["redacted"] is True
    assert event["request_payload"]["attendees"][0]["redacted"] is True
    assert event["response_payload"]["body"]["redacted"] is True
    assert event["error_message"]["redacted"] is True


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
            error_code="adk_model_unavailable",
        )
    )

    metrics = TelemetryService(repository).ai_dashboard()

    assert metrics["total_events"] == 2
    assert metrics["success_rate"] == 0.5
    assert metrics["adk_coverage"] == 1.0
    assert metrics["tool_call_coverage"] == 0.5
    assert metrics["model_status_counts"] == {"unavailable": 1, "used": 1}
    assert metrics["recent_failures"][0]["operation"] == "generate_draft"


def test_ai_event_summaries_exclude_payloads_and_match_api_limit(tmp_path):
    repository = AuditRepository(Database(f"sqlite:///{tmp_path / 'audit.db'}"))
    actor = ActorContext(actor_id="admin-1")
    for index in range(260):
        repository.add_ai_event(
            AuditEvent(
                actor=actor,
                operation="parse_request",
                endpoint="/api/requests/parse",
                model_name="ollama_chat/gemma4:latest",
                model_status="not_configured",
                status="success",
                latency_ms=index,
                request_payload={"raw_text": f"Sensitive request {index}"},
                response_payload={"intent": {"requester": f"Requester {index}"}},
                runtime="deterministic",
                tool_calls=[],
            )
        )

    summaries = repository.list_ai_event_summaries(limit=1000)
    full_events = repository.list_ai_events(limit=1000)

    assert len(summaries) == 260
    assert len(full_events) == 260
    assert "request_payload" not in summaries[0]
    assert "response_payload" not in summaries[0]
    assert "request_payload" in full_events[0]
