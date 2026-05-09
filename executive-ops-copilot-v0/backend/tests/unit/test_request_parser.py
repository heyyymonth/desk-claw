import pytest
from pydantic import ValidationError

from app.llm.schemas import ParsedMeetingRequest
from app.services.request_parser import RequestParser


class StubLLM:
    def __init__(self, output):
        self.output = output

    def generate_structured(self, prompt, schema):
        return self.output


def test_parse_request_uses_valid_mock_llm_output():
    llm_output = {
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

    parsed = RequestParser(StubLLM(llm_output)).parse(llm_output["raw_text"])

    assert isinstance(parsed, ParsedMeetingRequest)
    assert parsed.intent.title == "Acme meeting"
    assert parsed.intent.duration_minutes == 30


def test_parse_request_falls_back_when_llm_unavailable():
    parsed = RequestParser(None).parse("Need 45 min with Finance next week")

    assert parsed.raw_text == "Need 45 min with Finance next week"
    assert parsed.intent.duration_minutes == 45
    assert parsed.intent.priority == "normal"
    assert "requester" in parsed.intent.missing_fields


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
