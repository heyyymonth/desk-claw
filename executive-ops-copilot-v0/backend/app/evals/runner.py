from pathlib import Path
from typing import Any

import yaml

from app.llm.schemas import CalendarBlock, ParsedMeetingRequest, TimeWindow
from app.services.draft_service import DraftService
from app.services.recommendation_service import RecommendationService
from app.services.request_parser import RequestParser
from app.services.rules_engine import RulesEngine


def run() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]
    cases = _load_yaml(root / "evals" / "cases" / "v0_scheduling_cases.yaml")["cases"]
    expected = _load_yaml(root / "evals" / "expected" / "v0_expected_outputs.yaml")["expected"]

    rules = RulesEngine().default_rules()
    parser = RequestParser(None)
    recommender = RecommendationService(None)
    drafter = DraftService(None)

    results = []
    for case in cases:
        parsed = _with_fixture_window(parser.parse(case["raw_text"]))
        recommendation = recommender.generate(parsed, rules, _calendar_blocks(case, rules))
        draft = drafter.generate(recommendation)
        failures = _assert_case(expected[case["id"]], parsed, recommendation, draft)
        results.append(
            {
                "id": case["id"],
                "passed": not failures,
                "failures": failures,
                "observed": {
                    "meeting_type": parsed.intent.meeting_type,
                    "priority": parsed.intent.priority,
                    "missing_fields": parsed.intent.missing_fields,
                    "decision": recommendation.decision,
                    "risk_level": recommendation.risk_level,
                    "safe_action": recommendation.safe_action,
                    "draft_type": draft.draft_type,
                },
            }
        )

    failed = sum(1 for result in results if not result["passed"])
    return {
        "status": "passed" if failed == 0 else "failed",
        "case_set": "v0_scheduling_cases",
        "total": len(results),
        "passed": len(results) - failed,
        "failed": failed,
        "results": results,
    }


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())


def _with_fixture_window(parsed: ParsedMeetingRequest) -> ParsedMeetingRequest:
    window = TimeWindow(start="2026-05-11T09:00:00-07:00", end="2026-05-11T17:00:00-07:00")
    intent = parsed.intent.model_copy(update={"preferred_windows": [window]})
    return parsed.model_copy(update={"intent": intent})


def _calendar_blocks(case: dict[str, Any], rules) -> list[CalendarBlock]:
    blocks = [
        CalendarBlock(title=block.label, start=block.start, end=block.end, busy=True)
        for block in rules.protected_blocks
    ]
    calendar_context = case.get("calendar_context")
    if isinstance(calendar_context, dict):
        for block in calendar_context.get("protected_blocks", []):
            blocks.append(CalendarBlock(title=block["label"], start=block["start"], end=block["end"], busy=True))
    return blocks


def _assert_case(expected: dict[str, Any], parsed, recommendation, draft) -> list[str]:
    failures: list[str] = []
    parse = expected.get("parse", {})
    _expect_value(failures, "meeting_type", parsed.intent.meeting_type, parse.get("meeting_type"))
    _expect_value(failures, "priority", parsed.intent.priority, parse.get("priority"))
    _expect_value(failures, "sensitivity", parsed.intent.sensitivity, parse.get("sensitivity"))
    _expect_value(failures, "async_candidate", parsed.intent.async_candidate, parse.get("async_candidate"))
    _expect_allowed(failures, "duration_minutes", parsed.intent.duration_minutes, parse.get("duration_minutes"))
    _expect_list(failures, "missing_fields", parsed.intent.missing_fields, parse.get("missing_fields"))
    _expect_list(failures, "constraints", parsed.intent.constraints, parse.get("constraints"))

    rec = expected.get("recommendation", {})
    _expect_allowed(failures, "decision", recommendation.decision, rec.get("decision"))
    _expect_allowed(failures, "risk_level", recommendation.risk_level, rec.get("risk_level"))
    _expect_value(failures, "safe_action", recommendation.safe_action, rec.get("safe_recommendation"))
    if "proposed_slots_count" in rec and len(recommendation.proposed_slots) != rec["proposed_slots_count"]:
        failures.append(f"proposed_slots_count expected {rec['proposed_slots_count']} got {len(recommendation.proposed_slots)}")
    if "max_confidence" in rec and recommendation.confidence > rec["max_confidence"]:
        failures.append(f"confidence expected <= {rec['max_confidence']} got {recommendation.confidence}")
    if recommendation.decision == "schedule" and "min_confidence_if_schedule" in rec:
        if recommendation.confidence < rec["min_confidence_if_schedule"]:
            failures.append(f"confidence expected >= {rec['min_confidence_if_schedule']} got {recommendation.confidence}")

    draft_expected = expected.get("draft", {})
    _expect_allowed(failures, "draft_type", draft.draft_type, draft_expected.get("draft_type"))
    _expect_allowed(failures, "tone", draft.tone, draft_expected.get("tone"))
    for forbidden in draft_expected.get("must_not_include", []):
        if forbidden.lower() in draft.body.lower():
            failures.append(f"draft body must not include '{forbidden}'")
    return failures


def _expect_value(failures: list[str], field: str, actual, expected) -> None:
    if expected is not None and actual != expected:
        failures.append(f"{field} expected {expected} got {actual}")


def _expect_allowed(failures: list[str], field: str, actual, expected) -> None:
    if expected is None:
        return
    if isinstance(expected, dict) and "allowed" in expected:
        if actual not in expected["allowed"]:
            failures.append(f"{field} expected one of {expected['allowed']} got {actual}")
    elif actual != expected:
        failures.append(f"{field} expected {expected} got {actual}")


def _expect_list(failures: list[str], field: str, actual: list[str], expected) -> None:
    if not expected:
        return
    lowered_actual = [item.lower() for item in actual]
    for item in expected.get("must_include", []):
        if item.lower() not in lowered_actual:
            failures.append(f"{field} must include {item}")
    for item in expected.get("must_not_include", []):
        if item.lower() in lowered_actual:
            failures.append(f"{field} must not include {item}")
    for item in expected.get("should_include", []):
        if not any(item.lower() in value for value in lowered_actual):
            failures.append(f"{field} should include {item}")
