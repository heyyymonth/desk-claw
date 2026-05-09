import json
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.main import create_app


ROOT = Path(__file__).resolve().parents[2]
client = TestClient(create_app())


def load_schema(name: str) -> dict:
    return json.loads((ROOT.parent / "contracts" / "schemas" / name).read_text())


def assert_valid(instance: dict, schema_name: str) -> None:
    Draft202012Validator(load_schema(schema_name)).validate(instance)


def parsed_payload() -> dict:
    return {
        "raw_text": "Need 30 min",
        "intent": {
            "title": "Meeting",
            "requester": "Jordan",
            "duration_minutes": 30,
            "priority": "normal",
            "meeting_type": "other",
            "attendees": ["Jordan"],
            "preferred_windows": [
                {
                    "start": "2026-05-11T09:00:00-07:00",
                    "end": "2026-05-11T10:00:00-07:00",
                }
            ],
            "constraints": [],
            "missing_fields": [],
            "sensitivity": "low",
            "async_candidate": False,
            "escalation_required": False,
        },
    }


def rules_payload() -> dict:
    return {
        "executive_name": "Avery Chen",
        "timezone": "America/Los_Angeles",
        "working_hours": {"start": "09:00", "end": "17:00"},
        "protected_blocks": [],
        "preferences": [],
    }


def test_endpoint_responses_validate_against_v0_json_schemas():
    parsed = client.post("/api/requests/parse", json={"raw_text": "Need 30 min with Legal"}).json()
    assert_valid(parsed, "meeting_request.schema.json")

    rules = client.get("/api/rules/default").json()
    assert_valid(rules, "executive_rules.schema.json")

    recommendation = client.post(
        "/api/recommendations/generate",
        json={"parsed_request": parsed_payload(), "rules": rules_payload(), "calendar_blocks": []},
    ).json()
    assert_valid(recommendation, "recommendation.schema.json")

    draft = client.post("/api/drafts/generate", json={"recommendation": recommendation}).json()
    assert_valid(draft, "draft_response.schema.json")
