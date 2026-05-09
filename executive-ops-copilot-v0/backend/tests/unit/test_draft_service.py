from app.llm.schemas import DraftResponse, Recommendation
from app.services.draft_service import DraftService


class StubLLM:
    def __init__(self, output):
        self.output = output

    def generate_structured(self, prompt, schema):
        return self.output


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
        StubLLM(
            {
                "subject": "Meeting with Acme",
                "body": "We can meet Monday at 9:00 AM.",
                "tone": "warm",
                "model_status": "used",
            }
        )
    )

    draft = service.generate(recommendation())

    assert isinstance(draft, DraftResponse)
    assert draft.model_status == "used"


def test_draft_service_falls_back_without_llm():
    draft = DraftService(None).generate(recommendation("decline"))

    assert draft.tone == "firm"
    assert draft.model_status == "not_configured"
    assert "not able" in draft.body.lower()
