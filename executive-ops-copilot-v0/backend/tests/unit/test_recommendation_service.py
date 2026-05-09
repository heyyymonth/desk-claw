from app.llm.schemas import CalendarBlock, ExecutiveRules, ParsedMeetingRequest
from app.services.recommendation_service import RecommendationService


class StubLLM:
    def __init__(self, output):
        self.output = output

    def generate_structured(self, prompt, schema):
        return self.output


def parsed_request():
    return ParsedMeetingRequest.model_validate(
        {
            "raw_text": "Need 30 min with Acme.",
            "intent": {
                "title": "Acme meeting",
                "requester": "Jordan",
                "duration_minutes": 30,
                "priority": "normal",
                "attendees": ["Jordan"],
                "preferred_windows": [
                    {
                        "start": "2026-05-11T09:00:00-07:00",
                        "end": "2026-05-11T11:00:00-07:00",
                    }
                ],
                "constraints": [],
                "missing_fields": [],
            },
        }
    )


def rules():
    return ExecutiveRules.model_validate(
        {
            "executive_name": "Avery Chen",
            "timezone": "America/Los_Angeles",
            "working_hours": {"start": "09:00", "end": "17:00"},
            "protected_blocks": [],
            "preferences": [],
        }
    )


def test_recommendation_uses_valid_llm_rationale_but_deterministic_slots():
    llm = StubLLM(
        {
            "decision": "schedule",
            "confidence": 0.9,
            "rationale": ["The meeting fits policy."],
            "risks": [],
            "proposed_slots": [],
            "model_status": "used",
        }
    )

    recommendation = RecommendationService(llm).generate(parsed_request(), rules(), [])

    assert recommendation.decision == "schedule"
    assert recommendation.model_status == "used"
    assert recommendation.proposed_slots[0].start.isoformat() == "2026-05-11T09:00:00-07:00"


def test_recommendation_falls_back_when_calendar_has_no_slot():
    blocks = [
        CalendarBlock(
            title="Booked",
            start="2026-05-11T09:00:00-07:00",
            end="2026-05-11T11:00:00-07:00",
            busy=True,
        )
    ]

    recommendation = RecommendationService(None).generate(parsed_request(), rules(), blocks)

    assert recommendation.decision == "defer"
    assert recommendation.proposed_slots == []
    assert recommendation.model_status == "not_configured"
