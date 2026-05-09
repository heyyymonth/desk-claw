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
        )
    )

    events = repository.list_ai_events()

    assert events[0]["id"] == event_id
    assert events[0]["actor_id"] == "ea-1"
    assert events[0]["operation"] == "parse_request"
    assert events[0]["model_name"] == "gemma4:latest"
    assert events[0]["request_payload"]["raw_text"] == "Need 30 min"
    assert events[0]["response_payload"]["intent"]["requester"] == "Jordan"
