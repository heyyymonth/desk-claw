from fastapi.testclient import TestClient
import httpx

from app.api.deps import get_draft_service, get_recommendation_service, get_request_parser
from app.llm.schemas import DraftResponse, ParsedMeetingRequest, Recommendation
from app.main import create_app
from app.services.request_parser import fallback_parse


class StubParser:
    def parse(self, raw_text: str) -> ParsedMeetingRequest:
        return fallback_parse(raw_text)


class StubRecommender:
    def generate(self, parsed_request, rules, calendar_blocks) -> Recommendation:
        return Recommendation.model_validate(
            {
                "decision": "clarify" if parsed_request.intent.missing_fields else "schedule",
                "confidence": 0.7,
                "rationale": ["Model-backed test double returned a valid recommendation."],
                "risks": [],
                "risk_level": "low",
                "safe_action": "propose_slot_for_human_review_before_final_send",
                "proposed_slots": [],
                "model_status": "used",
            }
        )


class StubDrafter:
    def generate(self, recommendation) -> DraftResponse:
        return DraftResponse.model_validate(
            {
                "subject": "Meeting request",
                "body": "Thanks for reaching out. We will review and confirm the next step.",
                "tone": "concise",
                "draft_type": "clarify",
                "model_status": "used",
            }
        )


app = create_app()
app.dependency_overrides[get_request_parser] = lambda: StubParser()
app.dependency_overrides[get_recommendation_service] = lambda: StubRecommender()
app.dependency_overrides[get_draft_service] = lambda: StubDrafter()
client = TestClient(app)


def test_health_endpoint_contract():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "web-backend"


def test_process_health_endpoint_contract():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "web-backend"


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


def test_chat_endpoint_proxies_to_ai_backend(monkeypatch):
    def fake_post(url, json, timeout):
        return httpx.Response(200, json={"content": "Simple explanation.", "provider": "openai", "model": "gpt-5.5"})

    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.post("/api/chat", json={"message": "Explain this architecture simply."})

    assert response.status_code == 200
    assert response.json()["content"] == "Simple explanation."
    assert response.json()["provider"] == "openai"


def test_old_split_workflow_endpoints_are_not_exposed():
    assert client.post("/api/requests/parse", json={"raw_text": "Need time."}).status_code == 404
    assert client.post("/api/recommendations/generate", json={}).status_code == 404
    assert client.post("/api/drafts/generate", json={}).status_code == 404
    assert client.get("/api/rules/default").status_code == 404
    assert client.get("/api/calendar/mock").status_code == 404
    assert client.get("/metrics").status_code == 404
