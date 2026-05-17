import json

from app.agents.scheduling import (
    DEFAULT_MODEL_NAME,
    NATIVE_AI_RUNTIME,
    ModelResponse,
    NativeDraftAgentRunner,
    NativeRequestParserAgentRunner,
    NativeSchedulingAgentRunner,
    SchedulingAgentPlanner,
    _coerce_parsed_request_output,
    classify_priority_and_risk,
    default_model_name,
    extract_meeting_entities,
    extract_time_preferences,
    inspect_calendar_conflicts,
    local_model_name,
    request_parser_agent_definition,
    resolve_scheduling_plan,
    scheduling_agent_definition,
    select_resolution_strategy,
    validate_scheduling_rules,
)
from app.llm.schemas import CalendarBlock, ExecutiveRules, ParsedMeetingRequest, Recommendation


class StubModelClient:
    def __init__(self, output):
        self.outputs = output if isinstance(output, list) else [output]
        self.index = 0
        self.calls = []

    def complete_json(self, *, system_prompt, payload, timeout_seconds):
        self.calls.append({"system_prompt": system_prompt, "payload": payload, "timeout_seconds": timeout_seconds})
        output = self.outputs[min(self.index, len(self.outputs) - 1)]
        self.index += 1
        return ModelResponse(output=output, model_name="gpt-5.5", provider="openai")


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
    assert scheduling_agent_definition.framework == NATIVE_AI_RUNTIME
    assert scheduling_agent_definition.name == "meeting_resolution_agent"
    assert [tool.name for tool in scheduling_agent_definition.tools] == [
        "inspect_calendar_conflicts",
        "validate_scheduling_rules",
        "classify_priority_and_risk",
        "select_resolution_strategy",
    ]
    assert "protected executive focus time" in scheduling_agent_definition.planning_goal


def test_request_parser_agent_definition_uses_grounding_tools():
    assert request_parser_agent_definition.framework == NATIVE_AI_RUNTIME
    assert [tool.name for tool in request_parser_agent_definition.tools] == [
        "extract_meeting_entities",
        "extract_time_preferences",
    ]
    assert "backend entity and time-evidence tools" in request_parser_agent_definition.planning_goal


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


def test_native_agents_default_to_openai_frontier_model():
    assert local_model_name() == "gateway-default"
    assert default_model_name() == "gateway-default"
    assert DEFAULT_MODEL_NAME == "gateway-default"


def test_native_tool_functions_use_structured_inputs():
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


def test_native_runner_merges_model_reasoning_with_guardrails():
    plan = SchedulingAgentPlanner().plan(parsed_request(), rules(), [])
    output = {
        "decision": "schedule",
        "confidence": 0.93,
        "rationale": ["Model reasoned through calendar, rules, risk, and strategy tools."],
        "risks": [],
        "risk_level": "low",
        "safe_action": "unsafe_external_write",
        "proposed_slots": [],
    }

    merged = NativeSchedulingAgentRunner(model_client=StubModelClient(output))._merge_model_output(output, plan)

    assert merged.confidence == 0.93
    assert merged.rationale == ["Model reasoned through calendar, rules, risk, and strategy tools."]
    assert merged.safe_action == "propose_slot_for_human_review_before_final_send"
    assert merged.proposed_slots


def test_native_parser_runner_uses_model_first_focused_calls_without_algorithmic_evidence():
    compose_output = {
        "raw_text": "Please meet with Acme for 30 minutes tomorrow.",
        "intent": {
            "title": "Acme meeting",
            "requester": "Wrong requester",
            "duration_minutes": 60,
            "priority": "normal",
            "attendees": ["From Jordan"],
            "preferred_windows": [],
            "constraints": ["tomorrow"],
            "missing_fields": [],
        },
    }
    client = StubModelClient(
        [
            {"requester": "Jordan", "missing": False},
            {"attendees": ["Acme"]},
            {"duration_minutes": 30, "missing": False},
            {"priority": "high", "rationale": "Customer context."},
            compose_output,
        ]
    )

    parsed, trace = NativeRequestParserAgentRunner(model_client=client).parse_with_trace(compose_output["raw_text"])

    assert parsed.intent.title == "Acme meeting"
    assert parsed.intent.requester == "Jordan"
    assert parsed.intent.attendees == ["Acme"]
    assert parsed.intent.duration_minutes == 30
    assert parsed.intent.priority == "high"
    assert len(client.calls) == 5
    assert all("entity_evidence" not in call["payload"] for call in client.calls)
    assert all("time_evidence" not in call["payload"] for call in client.calls)
    assert trace["runtime"] == NATIVE_AI_RUNTIME
    assert trace["tool_calls"] == [
        "model_extract_requester",
        "model_extract_attendees",
        "model_extract_duration",
        "model_classify_priority",
        "model_compose_parsed_request",
    ]


def test_native_draft_runner_returns_model_draft_with_tool_trace():
    output = {
        "subject": "Meeting time available",
        "body": "We can meet Monday at 9:00 AM. Please confirm.",
        "tone": "warm",
        "draft_type": "accept",
        "model_status": "used",
    }
    recommendation = Recommendation.model_validate(
        {
            "decision": "schedule",
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
            "model_status": "used",
        }
    )

    draft, trace = NativeDraftAgentRunner(model_client=StubModelClient(output)).generate_with_trace(recommendation)

    assert draft.subject == "Meeting time available"
    assert trace["tool_calls"] == ["compose_guarded_draft"]


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


def test_request_parser_coerces_common_model_json_to_schema_shape():
    output = {
        "intent": {"action": "schedule_meeting", "missing_fields": None},
        "meeting_request": {
            "subject": "Executive prep: Vendor contract renewal",
            "duration": "30 minutes",
            "attendees": ["Dana from Legal"],
        },
        "datetime": {"date": "tomorrow", "time_window": "afternoon"},
    }

    coerced = _coerce_parsed_request_output("Please schedule prep with Dana.", output)
    parsed = ParsedMeetingRequest.model_validate(coerced)

    assert parsed.intent.title == "Executive prep: Vendor contract renewal"
    assert parsed.intent.duration_minutes == 30
    assert parsed.intent.priority == "normal"
    assert parsed.intent.attendees == ["Dana"]
    assert parsed.intent.missing_fields == ["requester"]


def test_request_parser_coerces_flat_gemma_json_to_schema_shape():
    output = {
        "requester": "Unknown requester",
        "attendees": ["Alex"],
        "title": "Launch plan meeting",
        "meeting_type": "internal",
        "sensitivity": "low",
        "priority": "normal",
        "duration": 30,
        "preferred_windows": [
            {
                "start": "2026-05-19T13:00:00-07:00",
                "end": "2026-05-19T17:00:00-07:00",
            }
        ],
        "timezone": "America/Los_Angeles",
    }

    coerced = _coerce_parsed_request_output("Schedule launch plan meeting with Alex Tuesday afternoon.", output)
    parsed = ParsedMeetingRequest.model_validate(coerced)

    assert parsed.intent.title == "Launch plan meeting"
    assert parsed.intent.duration_minutes == 30
    assert parsed.intent.meeting_type == "internal"
    assert parsed.intent.attendees == ["Alex"]
    assert parsed.intent.preferred_windows[0].start.isoformat() == "2026-05-19T13:00:00-07:00"
    assert parsed.intent.missing_fields == ["requester"]


def test_request_parser_focused_outputs_clean_attendee_artifacts():
    output = {
        "raw_text": "From Jordan at Atlas Finance: can Dana meet for 30 minutes next Tuesday afternoon? Please include Priya from Legal.",
        "intent": {
            "title": "Atlas Finance renewal discussion",
            "requester": "Wrong",
            "duration_minutes": 60,
            "priority": "normal",
            "meeting_type": "customer",
            "attendees": ["From Jordan"],
            "preferred_windows": [],
            "constraints": ["tuesday", "afternoon"],
            "missing_fields": [],
            "sensitivity": "medium",
        },
    }
    focused_outputs = {
        "requester": {"requester": "Jordan", "missing": False},
        "attendees": {"attendees": ["Dana", "Priya from Legal", "From Jordan", "Dana"]},
        "duration": {"duration_minutes": 30, "missing": False},
        "priority": {"priority": "high", "rationale": "Customer renewal risk."},
    }

    coerced = _coerce_parsed_request_output(output["raw_text"], output, focused_outputs=focused_outputs)
    parsed = ParsedMeetingRequest.model_validate(coerced)

    assert parsed.intent.requester == "Jordan"
    assert parsed.intent.attendees == ["Dana", "Priya"]
    assert parsed.intent.duration_minutes == 30
    assert parsed.intent.priority == "high"
