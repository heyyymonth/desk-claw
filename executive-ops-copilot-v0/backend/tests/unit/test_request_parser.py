import pytest
from pydantic import ValidationError

from app.agents.scheduling import AgentRuntimeError
from app.llm.schemas import ParsedMeetingRequest
from app.services.request_parser import RequestParser


class StubParserAgent:
    def __init__(self, output=None, error=None):
        self.output = output
        self.error = error

    def parse(self, raw_text):
        if self.error:
            raise self.error
        return ParsedMeetingRequest.model_validate(self.output)


def test_parse_request_uses_valid_native_output():
    native_output = {
        "raw_text": "Please meet with Acme for 30 minutes tomorrow.",
        "intent": {
            "title": "Acme meeting",
            "requester": "Jordan",
            "duration_minutes": 30,
            "priority": "normal",
            "attendees": ["Jordan", "Acme"],
            "preferred_windows": [],
            "constraints": ["tomorrow"],
            "missing_fields": [],
        },
    }

    parsed = RequestParser(agent_runner=StubParserAgent(native_output)).parse(native_output["raw_text"])

    assert isinstance(parsed, ParsedMeetingRequest)
    assert parsed.intent.title == "Acme meeting"
    assert parsed.intent.duration_minutes == 30


def test_parse_request_requires_native_runner():
    with pytest.raises(Exception) as exc:
        RequestParser().parse("Need 45 min with Finance next week")

    assert getattr(exc.value, "code", None) == "ai_model_not_configured"
    assert exc.value.ai_trace["runtime"] == "native-agent"
    assert exc.value.ai_trace["model_status"] == "not_configured"


def test_parse_request_normalizes_native_output_with_grounded_entities_and_windows():
    raw_text = (
        "Hi Morgan's team, can you find 30 minutes this week for Dana Patel from Atlas Finance "
        "to discuss renewal risk and contract timing with Morgan? Tuesday afternoon or Wednesday "
        "morning works best. Please include Priya from Legal if possible."
    )
    native_output = {
        "raw_text": raw_text,
        "intent": {
            "title": "Legal HR meeting",
            "requester": "Atlas Finance",
            "duration_minutes": 30,
            "priority": "high",
            "attendees": [],
            "preferred_windows": [],
            "constraints": ["morning", "afternoon"],
            "missing_fields": [],
            "meeting_type": "legal_hr",
            "sensitivity": "high",
        },
    }

    parsed = RequestParser(agent_runner=StubParserAgent(native_output)).parse(raw_text)

    assert parsed.intent.requester == "Dana Patel"
    assert {"Dana Patel", "Morgan", "Priya"}.issubset(set(parsed.intent.attendees))
    assert parsed.intent.meeting_type == "customer"
    assert parsed.intent.sensitivity == "medium"
    assert len(parsed.intent.preferred_windows) == 2


def test_parse_request_reports_unavailable_native_runner_without_fallback():
    with pytest.raises(Exception) as exc:
        RequestParser(agent_runner=StubParserAgent(error=AgentRuntimeError("timeout"))).parse_with_trace(
            "Please schedule 30 minutes for Dana Patel from Atlas Finance with Morgan Tuesday afternoon."
        )

    assert getattr(exc.value, "code", None) == "ai_model_unavailable"
    assert exc.value.ai_trace["runtime"] == "native-agent"
    assert exc.value.ai_trace["model_status"] == "unavailable"


def test_parsed_request_rejects_invalid_priority():
    with pytest.raises(ValidationError):
        ParsedMeetingRequest.model_validate(
            {
                "raw_text": "hello",
                "intent": {
                    "title": "hello",
                    "requester": "A",
                    "duration_minutes": 30,
                    "priority": "critical",
                    "attendees": [],
                    "constraints": [],
                    "missing_fields": [],
                },
            }
        )
