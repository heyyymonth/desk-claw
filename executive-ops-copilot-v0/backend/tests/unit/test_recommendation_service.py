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


def test_recommendation_requires_native_runner():
    blocks = [
        CalendarBlock(
            title="Booked",
            start="2026-05-11T09:00:00-07:00",
            end="2026-05-11T11:00:00-07:00",
            busy=True,
        )
    ]

    try:
        RecommendationService().generate(parsed_request(), rules(), blocks)
    except Exception as exc:
        assert getattr(exc, "code", None) == "ai_model_not_configured"
        assert exc.ai_trace["runtime"] == "native-agent"
        assert exc.ai_trace["model_status"] == "not_configured"
    else:
        raise AssertionError("missing native runner should surface as a service error")

def test_recommendation_guardrails_rationale_for_escalation_with_native_runner():
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
    plan = SchedulingAgentPlanner().plan(request, rules(), [])
    recommendation = RecommendationService(agent_runner=StubAgentRunner(plan=plan)).generate(request, rules(), [])

    assert recommendation.decision == "defer"
    assert recommendation.proposed_slots == []
    assert recommendation.rationale == ["Human escalation is required before replying or scheduling."]
    assert recommendation.risk_level == "high"
    assert recommendation.model_status == "used"


def test_recommendation_prefers_native_agent_runner_when_configured():
    plan = SchedulingAgentPlanner().plan(parsed_request(), rules(), [])
    runner = StubAgentRunner(plan=plan)

    recommendation = RecommendationService(agent_runner=runner).generate(parsed_request(), rules(), [])

    assert recommendation.decision == "schedule"
    assert recommendation.model_status == "used"
    assert recommendation.rationale == plan.rationale


def test_recommendation_reports_unavailable_native_runner_without_fallback():
    runner = StubAgentRunner(error=AgentRuntimeError("native unavailable"))

    try:
        RecommendationService(agent_runner=runner).generate(parsed_request(), rules(), [])
    except Exception as exc:
        assert getattr(exc, "code", None) == "ai_model_unavailable"
        assert exc.ai_trace["runtime"] == "native-agent"
        assert exc.ai_trace["model_status"] == "unavailable"
        assert exc.ai_trace["agent_name"] == "meeting_resolution_agent"
    else:
        raise AssertionError("native runner failure should surface as a service error")
