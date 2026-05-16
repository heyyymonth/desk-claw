from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_health_endpoint_contract():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_parse_request_endpoint_returns_structured_response():
    response = client.post(
        "/api/parse-request",
        json={"raw_text": "From Jordan at Atlas Finance: can Dana meet for 30 minutes next Tuesday afternoon?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"parsed_request", "recommendation", "draft_response", "next_steps"}
    assert body["parsed_request"]["intent"]["duration_minutes"] == 30
    assert body["recommendation"]["decision"] in {"schedule", "clarify", "defer", "decline"}
    assert body["draft_response"]["body"]
    assert body["next_steps"]


def test_parse_request_endpoint_accepts_text_alias():
    response = client.post(
        "/api/parse-request",
        json={"text": "I need to schedule a 30 minute sync with Sarah next week."},
    )

    assert response.status_code == 200
    assert response.json()["parsed_request"]["raw_text"] == "I need to schedule a 30 minute sync with Sarah next week."


def test_old_split_workflow_endpoints_are_not_exposed():
    assert client.post("/api/requests/parse", json={"raw_text": "Need time."}).status_code == 404
    assert client.post("/api/recommendations/generate", json={}).status_code == 404
    assert client.post("/api/drafts/generate", json={}).status_code == 404
    assert client.get("/api/rules/default").status_code == 404
    assert client.get("/api/calendar/mock").status_code == 404
    assert client.get("/metrics").status_code == 404
