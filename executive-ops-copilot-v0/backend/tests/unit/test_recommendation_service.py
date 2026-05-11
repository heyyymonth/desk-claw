from app.agents.scheduling import AgentRuntimeError, SchedulingAgentPlanner
from app.llm.schemas import CalendarBlock, ExecutiveRules, ParsedMeetingRequest
from app.services.recommendation_service import RecommendationService


class StubAgentRunner:
    def __init__(self, plan=None, error: Exception | None = None):
        self._plan = plan
        self.error = error

    def plan(self, parsed_request, rules, calendar_blocks):
        if self.error:
            raise self.error
        return self._plan


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


def test_recommendation_guardrails_rationale_for_escalation():
    request = parsed_request().model_copy(
        update={
            "intent": parsed_request().intent.model_copy(
                update={
                    "meeting_type": "customer",
                    "priority": "urgent",
                    "escalation_required": True,
                }
            )
        }
    )
    recommendation = RecommendationService(None).generate(request, rules(), [])

    assert recommendation.decision == "defer"
    assert recommendation.proposed_slots == []
    assert recommendation.rationale == ["Human escalation is required before replying or scheduling."]
    assert recommendation.risk_level == "high"


def test_recommendation_prefers_adk_agent_runner_when_configured():
    plan = SchedulingAgentPlanner().plan(parsed_request(), rules(), [])
    runner = StubAgentRunner(plan=plan)

    recommendation = RecommendationService(agent_runner=runner).generate(parsed_request(), rules(), [])

    assert recommendation.decision == "schedule"
    assert recommendation.model_status == "used"
    assert recommendation.rationale == plan.rationale


def test_recommendation_falls_back_when_adk_agent_runner_is_unavailable():
    runner = StubAgentRunner(error=AgentRuntimeError("ADK unavailable"))

    recommendation = RecommendationService(None, agent_runner=runner).generate(parsed_request(), rules(), [])

    assert recommendation.decision == "schedule"
    assert recommendation.model_status == "unavailable"
