import pytest
from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_rules_profile_compat_endpoints():
    get_response = client.get("/api/rules")
    assert get_response.status_code == 200
    assert get_response.json()["working_hours"] == {"start": "09:00", "end": "17:00"}

    payload = get_response.json()
    payload["preferences"].append("Prefer short meetings.")
    put_response = client.put("/api/rules", json=payload)

    assert put_response.status_code == 200
    assert put_response.json()["preferences"][-1] == "Prefer short meetings."


def test_calendar_blocks_compat_endpoints():
    get_response = client.get("/api/calendar/blocks")
    assert get_response.status_code == 200
    assert "blocks" in get_response.json()

    block = {
        "title": "Hold",
        "start": "2026-05-12T09:00:00-07:00",
        "end": "2026-05-12T09:30:00-07:00",
        "busy": True,
    }
    post_response = client.post("/api/calendar/blocks", json=block)

    assert post_response.status_code == 201
    assert post_response.json()["title"] == "Hold"


@pytest.mark.evals
def test_eval_endpoint_runs_deterministic_basic_cases():
    response = client.post("/api/evals/run")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "passed"
    assert body["passed"] >= 1
    assert body["failed"] == 0
    assert body["adk_eval"]["framework"] == "google-adk"
    assert body["adk_eval"]["metric"] == "tool_trajectory_avg_score"
    assert body["adk_eval"]["passed"] is True


def test_full_workflow_decision_log_post_contract():
    parsed_request = {
        "raw_text": "Important customer meeting from Alex for 30 minutes next week",
        "intent": {
            "title": "Customer meeting",
            "requester": "Alex",
            "duration_minutes": 30,
            "priority": "high",
            "attendees": [],
            "preferred_windows": [],
            "constraints": ["Requested for next week"],
            "missing_fields": [],
        },
    }
    recommendation = {
        "decision": "schedule",
        "confidence": 0.84,
        "rationale": ["Found a safe slot."],
        "risks": [],
        "proposed_slots": [
            {
                "start": "2026-05-11T11:00:00-07:00",
                "end": "2026-05-11T11:30:00-07:00",
                "reason": "Open",
            }
        ],
        "model_status": "not_configured",
    }

    response = client.post(
        "/api/decisions",
        json={
            "meeting_request": parsed_request,
            "recommendation": recommendation,
            "final_decision": "accepted",
            "notes": "",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["meeting_request"]["intent"]["title"] == "Customer meeting"
