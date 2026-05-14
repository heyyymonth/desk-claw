from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_parse_recommend_draft_contract_flow():
    parse_response = client.post(
        "/api/parse-request",
        json={"raw_text": "Important customer meeting from Alex for 30 minutes next week"},
    )
    assert parse_response.status_code == 200
    meeting_request = parse_response.json()
    assert meeting_request["intent"]["title"] == "Customer meeting"

    rules = client.get("/api/default-rules").json()
    recommendation_response = client.post(
        "/api/recommendation",
        json={"meeting_request": meeting_request, "rules": rules},
    )
    assert recommendation_response.status_code == 200
    recommendation = recommendation_response.json()
    assert recommendation["decision"] in {"schedule", "clarify", "defer", "decline"}

    draft_response = client.post(
        "/api/draft-response",
        json={"meeting_request": meeting_request, "recommendation": recommendation},
    )
    assert draft_response.status_code == 200
    assert draft_response.json()["body"]
