import json
from pathlib import Path

from app.agents.scheduling import (
    DEFAULT_ADK_MODEL,
    AdkSchedulingAgentRunner,
    SchedulingAgentPlanner,
    _tool_call_names_from_event,
    _tool_response_objects_from_event,
    classify_priority_and_risk,
    create_adk_draft_agent,
    create_adk_request_parser_agent,
    create_adk_root_agent,
    default_adk_model_name,
    extract_meeting_entities,
    extract_time_preferences,
    inspect_calendar_conflicts,
    local_adk_model_name,
    request_parser_agent_definition,
    resolve_scheduling_plan,
    scheduling_agent_definition,
    select_resolution_strategy,
    validate_scheduling_rules,
)
from app.llm.schemas import CalendarBlock, ExecutiveRules, ParsedMeetingRequest, Recommendation


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


def test_request_parser_agent_definition_uses_parallelizable_evidence_tools():
    assert request_parser_agent_definition.framework == "google-adk"
    assert [tool.name for tool in request_parser_agent_definition.tools] == [
        "extract_meeting_entities",
        "extract_time_preferences",
    ]
    assert "independent tools" in request_parser_agent_definition.planning_goal


def test_adk_runner_timeout_boundary_uses_processes_not_threads():
    source = Path("app/agents/scheduling.py").read_text()

    assert "ThreadPoolExecutor" not in source
    assert "multiprocessing.get_context" in source
    assert "process.terminate()" in source


def test_adk_tool_call_trace_reads_function_call_events():
    event = type(
        "Event",
        (),
        {
            "content": type(
                "Content",
                (),
                {
                    "parts": [
                        type("Part", (), {"function_call": type("FunctionCall", (), {"name": "inspect_calendar_conflicts"})()})(),
                        type("Part", (), {"function_call": type("FunctionCall", (), {"name": "validate_scheduling_rules"})()})(),
                    ]
                },
            )()
        },
    )()

    assert _tool_call_names_from_event(event) == ["inspect_calendar_conflicts", "validate_scheduling_rules"]


def test_adk_tool_response_trace_reads_function_response_events():
    event = type(
        "Event",
        (),
        {
            "content": type(
                "Content",
                (),
                {
                    "parts": [
                        type(
                            "Part",
                            (),
                            {
                                "function_response": type(
                                    "FunctionResponse",
                                    (),
                                    {"response": {"decision": "schedule"}},
                                )()
                            },
                        )(),
                    ]
                },
            )()
        },
    )()

    assert _tool_response_objects_from_event(event) == [{"decision": "schedule"}]


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


def test_resolve_scheduling_plan_tool_returns_recommendation_payload():
    request = parsed_request()
    payload = {
        "parsed_request": request.model_dump(mode="json"),
        "rules": rules().model_dump(mode="json"),
        "calendar_blocks": [],
    }

    output = resolve_scheduling_plan(json.dumps(payload))

    recommendation = Recommendation.model_validate(output)
    assert recommendation.model_status == "used"
    assert recommendation.decision == "schedule"
    assert recommendation.proposed_slots


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
    agent = create_adk_root_agent()

    assert agent.name == "meeting_resolution_agent"
    assert len(agent.tools) == 1


def test_adk_agents_default_to_local_gemma4_but_accept_other_models():
    assert local_adk_model_name() == "ollama_chat/gemma4:latest"
    assert default_adk_model_name() == "ollama_chat/gemma4:latest"
    assert DEFAULT_ADK_MODEL == "ollama_chat/gemma4:latest"
    parser_agent = create_adk_request_parser_agent()
    assert parser_agent.name == "meeting_request_parser_agent"
    assert len(parser_agent.tools) == 2
    assert create_adk_draft_agent().name == "meeting_draft_agent"
    assert create_adk_root_agent("gemini-2.0-flash").name == "meeting_resolution_agent"


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

    merged = AdkSchedulingAgentRunner(DEFAULT_ADK_MODEL)._merge_model_output(output, plan)

    assert merged.confidence == 0.93
    assert merged.rationale == ["ADK reasoned through calendar, rules, risk, and strategy tools."]
    assert merged.safe_action == "propose_slot_for_human_review_before_final_send"
    assert merged.proposed_slots


def test_request_parser_entity_and_time_tools_ground_customer_renewal_request():
    raw_text = (
        "Hi Morgan's team, can you find 30 minutes this week for Dana Patel from Atlas Finance "
        "to discuss renewal risk and contract timing with Morgan? Tuesday afternoon or Wednesday "
        "morning works best. Please include Priya from Legal if possible, and keep the note concise."
    )

    entities = extract_meeting_entities(raw_text)
    time_preferences = extract_time_preferences(raw_text)

    assert entities["requester"] == "Dana Patel"
    assert "Atlas Finance" in entities["organizations"]
    assert {"Dana Patel", "Morgan", "Priya"}.issubset(set(entities["attendees"]))
    assert entities["title"] == "Atlas Finance renewal discussion"
    assert entities["meeting_type"] == "customer"
    assert entities["sensitivity"] == "medium"
    assert len(time_preferences["preferred_windows"]) == 2
    assert time_preferences["preferred_windows"][0]["start"] == "2026-05-12T13:00:00-07:00"
    assert time_preferences["preferred_windows"][1]["start"] == "2026-05-13T09:00:00-07:00"
