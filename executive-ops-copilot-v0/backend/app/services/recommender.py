from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.models import (
    Decision,
    ExecutiveRules,
    MeetingRequest,
    ModelStatus,
    ProposedSlot,
    Recommendation,
    RecommendationRisk,
    RiskLevel,
)
from app.services.calendar import mock_calendar


def build_recommendation(meeting_request: MeetingRequest, rules: ExecutiveRules) -> Recommendation:
    intent = meeting_request.intent
    risks: list[RecommendationRisk] = []
    rationale = [
        f"Request priority is {intent.priority.value}.",
        "Checked mock calendar events and protected executive blocks.",
    ]

    if intent.missing_fields:
        risks.append(RecommendationRisk(level=RiskLevel.medium, message="Request is missing: " + ", ".join(intent.missing_fields)))
        return Recommendation(
            decision=Decision.clarify,
            confidence=0.72,
            rationale=rationale + ["Clarification is needed before offering a slot."],
            risks=risks,
            proposed_slots=[],
            model_status=ModelStatus.not_configured,
        )

    slot = _first_available_slot(intent.duration_minutes, rules)
    if not slot:
        risks.append(RecommendationRisk(level=RiskLevel.high, message="No safe mock-calendar slot found in the V0 search window."))
        return Recommendation(
            decision=Decision.defer,
            confidence=0.61,
            rationale=rationale + ["EA review is needed because the mock calendar is constrained."],
            risks=risks,
            proposed_slots=[],
            model_status=ModelStatus.not_configured,
        )

    if intent.priority.value in {"high", "urgent"}:
        risks.append(RecommendationRisk(level=RiskLevel.low, message="High-priority request should be reviewed before final send."))

    return Recommendation(
        decision=Decision.schedule,
        confidence=0.84,
        rationale=rationale + ["Found a slot that avoids protected blocks and mock calendar events."],
        risks=risks,
        proposed_slots=[slot],
        model_status=ModelStatus.not_configured,
    )


def _first_available_slot(duration_minutes: int, rules: ExecutiveRules) -> ProposedSlot | None:
    tz = ZoneInfo(rules.timezone)
    busy = [(block.start, block.end) for block in rules.protected_blocks]
    busy.extend((event.start, event.end) for event in mock_calendar())
    start_hour, start_minute = [int(part) for part in rules.working_hours.start.split(":")]
    end_hour, end_minute = [int(part) for part in rules.working_hours.end.split(":")]

    for day in range(0, 5):
        cursor = datetime(2026, 5, 11 + day, start_hour, start_minute, tzinfo=tz)
        day_end = datetime(2026, 5, 11 + day, end_hour, end_minute, tzinfo=tz)
        while cursor + timedelta(minutes=duration_minutes) <= day_end:
            candidate_end = cursor + timedelta(minutes=duration_minutes)
            if not _overlaps(cursor, candidate_end, busy):
                return ProposedSlot(start=cursor, end=candidate_end, reason="First V0 mock-calendar slot that satisfies rules.")
            cursor += timedelta(minutes=30)
    return None


def _overlaps(start: datetime, end: datetime, busy: list[tuple[datetime, datetime]]) -> bool:
    return any(start < busy_end and end > busy_start for busy_start, busy_end in busy)
