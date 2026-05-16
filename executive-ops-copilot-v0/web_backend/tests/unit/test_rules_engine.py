import pytest
from pydantic import ValidationError

from app.llm.schemas import ExecutiveRules
from app.services.rules_engine import RulesEngine


def valid_rules_payload():
    return {
        "executive_name": "Avery Chen",
        "timezone": "America/Los_Angeles",
        "working_hours": {"start": "09:00", "end": "17:00"},
        "protected_blocks": [
            {
                "label": "Focus",
                "start": "2026-05-11T13:00:00-07:00",
                "end": "2026-05-11T14:00:00-07:00",
            }
        ],
        "preferences": ["Avoid Fridays"],
    }


def test_rules_validate_working_hours_and_blocks():
    rules = ExecutiveRules.model_validate(valid_rules_payload())
    violations = RulesEngine().validate(rules)

    assert violations == []


def test_rules_reject_end_before_start():
    payload = valid_rules_payload()
    payload["working_hours"] = {"start": "18:00", "end": "09:00"}

    with pytest.raises(ValidationError):
        ExecutiveRules.model_validate(payload)


def test_rules_engine_flags_protected_block_outside_working_hours():
    payload = valid_rules_payload()
    payload["protected_blocks"][0]["start"] = "2026-05-11T18:00:00-07:00"
    payload["protected_blocks"][0]["end"] = "2026-05-11T19:00:00-07:00"
    rules = ExecutiveRules.model_validate(payload)

    violations = RulesEngine().validate(rules)

    assert violations
    assert violations[0].code == "protected_block_outside_working_hours"
