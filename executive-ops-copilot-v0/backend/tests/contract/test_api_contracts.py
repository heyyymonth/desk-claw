from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import create_app


client = TestClient(create_app())
ADMIN_HEADERS = {"X-DeskAI-Admin-Key": "test-admin-key"}


def test_parse_request_endpoint_contract():
    response = client.post("/api/requests/parse", json={"raw_text": "Need 30 min with Legal"})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"raw_text", "intent"}
    assert body["intent"]["duration_minutes"] == 30


def test_recommendation_endpoint_contract():
    payload = {
        "parsed_request": {
            "raw_text": "Need 30 min",
            "intent": {
                "title": "Meeting",
                "requester": "Jordan",
                "duration_minutes": 30,
                "priority": "normal",
                "attendees": ["Jordan"],
                "preferred_windows": [
                    {
                        "start": "2026-05-11T09:00:00-07:00",
                        "end": "2026-05-11T10:00:00-07:00",
                    }
                ],
                "constraints": [],
                "missing_fields": [],
            },
        },
        "rules": {
            "executive_name": "Avery Chen",
            "timezone": "America/Los_Angeles",
            "working_hours": {"start": "09:00", "end": "17:00"},
            "protected_blocks": [],
            "preferences": [],
        },
        "calendar_blocks": [],
    }

    response = client.post("/api/recommendations/generate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "decision",
        "confidence",
        "rationale",
        "risks",
        "risk_level",
        "safe_action",
        "proposed_slots",
        "model_status",
    }
    assert body["decision"] == "schedule"


def test_draft_endpoint_contract():
    response = client.post(
        "/api/drafts/generate",
        json={
            "recommendation": {
                "decision": "schedule",
                "confidence": 0.8,
                "rationale": ["Works."],
                "risks": [],
                "proposed_slots": [
                    {
                        "start": "2026-05-11T09:00:00-07:00",
                        "end": "2026-05-11T09:30:00-07:00",
                        "reason": "Open slot",
                    }
                ],
                "model_status": "not_configured",
            }
        },
    )

    assert response.status_code == 200
    assert set(response.json()) == {"subject", "body", "tone", "draft_type", "model_status"}


def test_feedback_and_decisions_contract():
    post = client.post(
        "/api/feedback",
        json={"action": "mark_wrong", "recommendation_id": "rec-1", "notes": "Conflict missed"},
    )
    get = client.get("/api/decisions")

    assert post.status_code == 201
    assert post.json()["action"] == "mark_wrong"
    assert get.status_code == 200
    assert isinstance(get.json(), list)


def test_workflow_decision_log_contract():
    payload = {
        "meeting_request": {
            "raw_text": "Need 30 min",
            "intent": {
                "title": "Meeting",
                "requester": "Jordan",
                "duration_minutes": 30,
                "priority": "normal",
                "attendees": [],
                "preferred_windows": [],
                "constraints": [],
                "missing_fields": [],
            },
        },
        "recommendation": {
            "decision": "schedule",
            "confidence": 0.8,
            "rationale": ["Works."],
            "risks": [],
            "proposed_slots": [],
            "model_status": "not_configured",
        },
        "final_decision": "accepted",
        "notes": "",
    }

    post = client.post("/api/decisions", json=payload)

    assert post.status_code == 201
    assert post.json()["final_decision"] == "accepted"


def test_default_rules_and_calendar_endpoints():
    assert client.get("/api/rules/default").status_code == 200
    assert client.get("/api/calendar/mock").status_code == 200


def test_ai_audit_endpoint_ignores_untrusted_actor_headers():
    parse = client.post(
        "/api/requests/parse",
        json={"raw_text": "From Jordan: need 30 minutes with Dana tomorrow."},
        headers={"X-Actor-Id": "ea-1", "X-Actor-Email": "ea@example.com", "X-Actor-Name": "EA User"},
    )

    assert parse.status_code == 200

    audit = client.get("/api/audit/ai?limit=5", headers=ADMIN_HEADERS)

    assert audit.status_code == 200
    body = audit.json()
    assert body["limit"] == 5
    assert body["events"][0]["actor_id"] == "local-user"
    assert body["events"][0]["operation"] == "parse_request"
    assert body["events"][0]["model_name"].startswith("ollama_chat/")
    assert body["events"][0]["runtime"] in {"google-adk", "deterministic"}
    assert "tool_calls" in body["events"][0]
    assert body["events"][0]["request_payload"]["raw_text"].startswith("From Jordan")
    assert body["events"][0]["response_payload"]["intent"]["requester"]


def test_ai_audit_endpoint_records_trusted_actor_context(monkeypatch):
    monkeypatch.setenv("ACTOR_AUTH_TOKEN", "test-actor-token")
    get_settings.cache_clear()

    parse = client.post(
        "/api/requests/parse",
        json={"raw_text": "From Jordan: need 30 minutes with Dana tomorrow."},
        headers={
            "X-DeskAI-Actor-Token": "test-actor-token",
            "X-Actor-Id": "ea-1",
            "X-Actor-Email": "ea@example.com",
            "X-Actor-Name": "EA User",
        },
    )

    assert parse.status_code == 200

    audit = client.get("/api/audit/ai?limit=5", headers=ADMIN_HEADERS)

    assert audit.status_code == 200
    body = audit.json()
    assert body["events"][0]["actor_id"] == "ea-1"


def test_ai_workflow_rejects_missing_actor_token_when_actor_auth_is_configured(monkeypatch):
    monkeypatch.setenv("ACTOR_AUTH_TOKEN", "test-actor-token")
    get_settings.cache_clear()

    response = client.post(
        "/api/requests/parse",
        json={"raw_text": "From Jordan: need 30 minutes with Dana tomorrow."},
        headers={"X-Actor-Id": "ea-1"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Trusted actor authentication is required."


def test_ai_metrics_endpoint_exposes_backend_quality_dashboard_data():
    client.post("/api/requests/parse", json={"raw_text": "Need 30 min with Legal"})

    response = client.get("/api/telemetry/ai/dashboard", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["total_events"] >= 1
    assert 0 <= body["success_rate"] <= 1
    assert 0 <= body["adk_coverage"] <= 1
    assert "operation_metrics" in body
    assert "tool_metrics" in body
    assert "insights" in body
    assert "recent_failures" in body


def test_ai_audit_endpoint_requires_admin_access():
    response = client.get("/api/audit/ai?limit=5")

    assert response.status_code == 401


def test_ai_metrics_endpoint_requires_admin_access():
    response = client.get("/api/telemetry/ai/dashboard")

    assert response.status_code == 401


def test_admin_ai_endpoints_fail_closed_without_configured_key(monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    get_settings.cache_clear()

    response = client.get("/api/audit/ai?limit=5", headers=ADMIN_HEADERS)

    assert response.status_code == 503
    assert response.json()["detail"] == "Admin API access is not configured."
