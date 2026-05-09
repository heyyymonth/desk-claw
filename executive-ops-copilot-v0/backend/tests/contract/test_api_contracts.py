from fastapi.testclient import TestClient

from app.main import create_app


client = TestClient(create_app())


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
