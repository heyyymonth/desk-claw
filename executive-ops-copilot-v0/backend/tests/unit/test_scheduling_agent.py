from app.agents.scheduling import SchedulingAgentPlanner, create_adk_root_agent, scheduling_agent_definition
from app.llm.schemas import CalendarBlock, ExecutiveRules, ParsedMeetingRequest


def parsed_request(**intent_updates):
    intent = {
        "title": "Customer escalation",
        "requester": "Jordan",
        "duration_minutes": 30,
        "priority": "urgent",
        "meeting_type": "customer",
        "attendees": ["Jordan", "Dana"],
        "preferred_windows": [
            {
                "start": "2026-05-11T09:00:00-07:00",
                "end": "2026-05-11T10:00:00-07:00",
            }
        ],
        "constraints": [],
        "missing_fields": [],
    }
    intent.update(intent_updates)
    return ParsedMeetingRequest.model_validate({"raw_text": "Need time with Dana.", "intent": intent})


def rules():
    return ExecutiveRules.model_validate(
        {
            "executive_name": "Dana Lee",
            "timezone": "America/Los_Angeles",
            "working_hours": {"start": "09:00", "end": "17:00"},
            "protected_blocks": [],
            "preferences": ["Protect focus blocks."],
        }
    )


def test_agent_definition_names_goals_and_tools():
    assert scheduling_agent_definition.framework == "google-adk-compatible"
    assert scheduling_agent_definition.name == "meeting_resolution_agent"
    assert [tool.name for tool in scheduling_agent_definition.tools] == [
        "inspect_calendar_conflicts",
        "validate_scheduling_rules",
        "classify_priority_and_risk",
        "select_resolution_strategy",
    ]
    assert "protected executive focus time" in scheduling_agent_definition.planning_goal


def test_planner_records_tool_calls_and_schedules_open_slot():
    plan = SchedulingAgentPlanner().plan(parsed_request(), rules(), [])

    assert plan.decision == "schedule"
    assert plan.proposed_slots
    assert [call.tool_name for call in plan.tool_calls] == [
        "inspect_calendar_conflicts",
        "validate_scheduling_rules",
        "classify_priority_and_risk",
        "select_resolution_strategy",
    ]
    assert plan.tool_calls[0].summary == "Found 0 conflict(s) and 1 candidate open slot(s)."


def test_planner_defers_when_requested_window_is_blocked():
    blocks = [
        CalendarBlock(
            title="Board prep",
            start="2026-05-11T09:00:00-07:00",
            end="2026-05-11T10:00:00-07:00",
            busy=True,
        )
    ]

    plan = SchedulingAgentPlanner().plan(parsed_request(), rules(), blocks)

    assert plan.decision == "defer"
    assert plan.risk_level == "high"
    assert plan.proposed_slots == []
    assert any("conflict" in risk.message for risk in plan.risks)


def test_create_adk_root_agent_is_adk_compatible_or_reports_missing_dependency():
    try:
        agent = create_adk_root_agent()
    except RuntimeError as exc:
        assert "Install google-adk" in str(exc)
    else:
        assert agent.name == "meeting_resolution_agent"
