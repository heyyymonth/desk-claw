from datetime import datetime
from zoneinfo import ZoneInfo
from app.models import MockCalendarEvent


def mock_calendar() -> list[MockCalendarEvent]:
    tz = ZoneInfo("America/Los_Angeles")
    return [
        MockCalendarEvent(
            title="Leadership sync",
            start=datetime(2026, 5, 11, 13, 0, tzinfo=tz),
            end=datetime(2026, 5, 11, 14, 0, tzinfo=tz),
        ),
        MockCalendarEvent(
            title="Product review",
            start=datetime(2026, 5, 12, 10, 0, tzinfo=tz),
            end=datetime(2026, 5, 12, 11, 30, tzinfo=tz),
        ),
    ]
