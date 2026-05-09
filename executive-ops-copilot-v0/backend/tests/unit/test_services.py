from app.services.drafter import draft_response
from app.services.parser import parse_meeting_request
from app.services.recommender import build_recommendation
from app.services.rules import default_rules


def test_parse_request_extracts_priority_and_duration():
    parsed = parse_meeting_request("Urgent investor meeting from Maya for 45 minutes next week")

    assert parsed.intent.title == "Investor meeting"
    assert parsed.intent.requester == "Maya"
    assert parsed.intent.duration_minutes == 45
    assert parsed.intent.priority == "urgent"


def test_recommendation_clarifies_missing_requester():
    parsed = parse_meeting_request("Can we meet about pricing next week?")
    recommendation = build_recommendation(parsed, default_rules())

    assert recommendation.decision == "clarify"
    assert recommendation.proposed_slots == []
    assert recommendation.risks


def test_draft_response_uses_recommendation_slot():
    parsed = parse_meeting_request("Important investor meeting from Maya for 30 minutes next week")
    recommendation = build_recommendation(parsed, default_rules())
    draft = draft_response(parsed, recommendation)

    assert draft.subject == "Re: Investor meeting"
    assert "Please confirm" in draft.body
