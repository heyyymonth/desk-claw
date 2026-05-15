import os
from datetime import datetime, timezone

import pytest

from app.db.audit import ActorContext, AuditEvent, AuditRepository
from app.db.decision_log import DecisionLogRepository
from app.db.session import Database
from app.llm.schemas import DecisionFeedback
from app.models import (
    DecisionLogInput,
    MeetingIntent,
    MeetingRequest,
    ModelStatus,
    Priority,
    Recommendation,
    RiskLevel,
)
from app.services.decision_log import DecisionLogService
from app.services.workflow_decision_log import WorkflowDecisionLogService

pytestmark = pytest.mark.postgres


def test_postgres_repositories_round_trip():
    database_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not set")

    database = Database(database_url)
    _reset_database(database)

    feedback = DecisionFeedback(action="accept", recommendation_id="rec-postgres", notes="Postgres feedback")
    feedback_service = DecisionLogService(database)
    feedback_service.log(feedback)
    assert feedback_service.list()[0].recommendation_id == "rec-postgres"

    workflow_service = WorkflowDecisionLogService(DecisionLogRepository(database))
    workflow_entry = workflow_service.log(_workflow_payload())
    assert workflow_entry.id
    assert workflow_service.list()[0].meeting_request.intent.title == "Customer review"

    audit_repository = AuditRepository(database)
    event_id = audit_repository.add_ai_event(
        AuditEvent(
            actor=ActorContext(actor_id="ea-postgres", email="ea@example.com", display_name="EA User"),
            operation="generate_recommendation",
            endpoint="/api/recommendations/generate",
            model_name="ollama_chat/gemma4:latest",
            model_status="used",
            status="success",
            latency_ms=123,
            request_payload={"raw_text": "Sensitive customer details"},
            response_payload={"decision": "schedule"},
            runtime="google-adk",
            agent_name="meeting_resolution_agent",
            tool_calls=["inspect_calendar_conflicts"],
        )
    )

    event = audit_repository.list_ai_events()[0]
    assert event["id"] == event_id
    assert event["request_payload"]["raw_text"]["redacted"] is True
    assert event["tool_calls"] == ["inspect_calendar_conflicts"]


def _reset_database(database: Database) -> None:
    with database.connect() as connection:
        connection.execute("TRUNCATE ai_audit_log, app_users, decisions, decision_log RESTART IDENTITY CASCADE")


def _workflow_payload() -> DecisionLogInput:
    now = datetime.now(timezone.utc)
    meeting_request = MeetingRequest(
        raw_text="Customer review with Alex",
        intent=MeetingIntent(
            title="Customer review",
            requester="Alex",
            duration_minutes=30,
            priority=Priority.high,
            attendees=[],
            preferred_windows=[],
            constraints=[],
            missing_fields=[],
            sensitivity=RiskLevel.low,
        ),
    )
    recommendation = Recommendation(
        decision="schedule",
        confidence=0.9,
        rationale=["Open executive window."],
        risks=[],
        proposed_slots=[
            {
                "start": now,
                "end": now,
                "reason": "Postgres integration test slot.",
            }
        ],
        model_status=ModelStatus.not_configured,
    )
    return DecisionLogInput(
        meeting_request=meeting_request,
        recommendation=recommendation,
        final_decision="accepted",
        notes="Stored through Postgres",
    )
