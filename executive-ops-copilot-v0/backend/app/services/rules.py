from datetime import datetime
from zoneinfo import ZoneInfo
from app.models import ExecutiveRules, ProtectedBlock, WorkingHours


def default_rules() -> ExecutiveRules:
    tz = ZoneInfo("America/Los_Angeles")
    return ExecutiveRules(
        executive_name="Executive",
        timezone="America/Los_Angeles",
        working_hours=WorkingHours(start="09:00", end="17:00"),
        protected_blocks=[
            ProtectedBlock(
                label="CEO focus block",
                start=datetime(2026, 5, 11, 9, 0, tzinfo=tz),
                end=datetime(2026, 5, 11, 11, 0, tzinfo=tz),
            ),
            ProtectedBlock(
                label="Board prep",
                start=datetime(2026, 5, 12, 14, 0, tzinfo=tz),
                end=datetime(2026, 5, 12, 16, 0, tzinfo=tz),
            ),
        ],
        preferences=[
            "Prefer investor and customer meetings before 2 PM.",
            "Avoid scheduling over protected blocks.",
            "Ask for clarification when requester, purpose, or duration is missing.",
        ],
    )
