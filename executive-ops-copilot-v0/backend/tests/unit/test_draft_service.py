from app.agents.scheduling import AgentRuntimeError
from app.llm.schemas import DraftResponse, Recommendation
from app.services.draft_service import DraftService


class StubDraftAgent:
    def __init__(self, output=None, error=None):
        self.output = output
        self.error = error

    def generate(self, recommendation):
        if self.error:
            raise self.error
        return DraftResponse.model_validate(self.output)


def recommendation(decision="schedule"):
    return Recommendation.model_validate(
        {
            "decision": decision,
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
    )


def test_draft_service_validates_llm_output():
    service = DraftService(
        agent_runner=StubDraftAgent(
            {
            "subject": "Meeting with Acme",
            "body": "We can meet Monday at 9:00 AM.",
            "tone": "warm",
            "draft_type": "accept",
            "model_status": "used",
        })
    )

    draft = service.generate(recommendation())

    assert isinstance(draft, DraftResponse)
    assert draft.model_status == "used"


def test_draft_service_falls_back_without_llm():
    draft = DraftService(None).generate(recommendation("decline"))

    assert draft.tone == "firm"
    assert draft.model_status == "not_configured"
    assert "not able" in draft.body.lower()


def test_draft_service_guardrails_defer_draft_from_llm():
    service = DraftService(
        agent_runner=StubDraftAgent(
            {
            "subject": "Meeting time available",
            "body": "We can meet Monday at 9:00 AM. Please confirm.",
            "tone": "warm",
            "draft_type": "accept",
            "model_status": "used",
        })
    )

    draft = service.generate(recommendation("defer"))

    assert draft.draft_type == "defer"
    assert draft.model_status == "used"
    assert "before proposing a time" in draft.body
    assert "9:00 AM" not in draft.body


def test_draft_service_reports_unavailable_adk_runner():
    service = DraftService(agent_runner=StubDraftAgent(error=AgentRuntimeError("timeout")))

    try:
        service.generate(recommendation())
    except Exception as exc:
        assert getattr(exc, "code", None) == "ollama_unavailable"
    else:
        raise AssertionError("ADK runner failure should surface as service error")
