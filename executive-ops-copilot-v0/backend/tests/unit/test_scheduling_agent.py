import json

from app.agents.scheduling import (
    AdkSchedulingAgentRunner,
    SchedulingAgentPlanner,
    classify_priority_and_risk,
    create_adk_root_agent,
    inspect_calendar_conflicts,
    scheduling_agent_definition,
    select_resolution_strategy,
    validate_scheduling_rules,
)
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
    assert scheduling_agent_definition.framework == "google-adk"
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
        agent = create_adk_root_agent("gemini-2.0-flash")
    except RuntimeError as exc:
        assert "Install google-adk" in str(exc) or "litellm" in str(exc)
    else:
        assert agent.name == "meeting_resolution_agent"


def test_adk_tool_functions_use_structured_inputs():
    request = parsed_request()
    analysis = inspect_calendar_conflicts(
        json.dumps([window.model_dump(mode="json") for window in request.intent.preferred_windows]),
        "[]",
        request.intent.duration_minutes,
    )
    rule_output = validate_scheduling_rules(json.dumps(rules().model_dump(mode="json")))
    risk_output = classify_priority_and_risk(
        json.dumps(request.model_dump(mode="json")),
        json.dumps(analysis),
        json.dumps(rule_output["violations"]),
    )
    strategy = select_resolution_strategy(
        json.dumps(request.model_dump(mode="json")),
        json.dumps(analysis),
        json.dumps(risk_output["risks"]),
    )

    assert analysis["open_slots"]
    assert rule_output == {"violations": []}
    assert risk_output["risk_level"] == "low"
    assert strategy["decision"] == "schedule"


def test_adk_runner_merges_model_reasoning_with_guardrails():
    plan = SchedulingAgentPlanner().plan(parsed_request(), rules(), [])
    output = {
        "decision": "schedule",
        "confidence": 0.93,
        "rationale": ["ADK reasoned through calendar, rules, risk, and strategy tools."],
        "risks": [],
        "risk_level": "low",
        "safe_action": "unsafe_external_write",
        "proposed_slots": [],
    }

    merged = AdkSchedulingAgentRunner("gemini-2.0-flash")._merge_model_output(output, plan)

    assert merged.confidence == 0.93
    assert merged.rationale == ["ADK reasoned through calendar, rules, risk, and strategy tools."]
    assert merged.safe_action == "propose_slot_for_human_review_before_final_send"
    assert merged.proposed_slots
