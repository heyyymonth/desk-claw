from app.llm.schemas import CalendarBlock, TimeWindow
from app.services.calendar_analyzer import CalendarAnalyzer


def test_calendar_analyzer_detects_conflicts_and_open_slots():
    request_window = TimeWindow(
        start="2026-05-11T09:00:00-07:00",
        end="2026-05-11T12:00:00-07:00",
    )
    blocks = [
        CalendarBlock(
            title="Existing",
            start="2026-05-11T10:00:00-07:00",
            end="2026-05-11T10:30:00-07:00",
            busy=True,
        )
    ]

    analysis = CalendarAnalyzer().analyze([request_window], blocks, duration_minutes=30)

    assert len(analysis.conflicts) == 1
    assert analysis.conflicts[0].title == "Existing"
    assert analysis.open_slots[0].start.isoformat() == "2026-05-11T09:00:00-07:00"


def test_calendar_analyzer_ignores_non_busy_blocks():
    request_window = TimeWindow(
        start="2026-05-11T09:00:00-07:00",
        end="2026-05-11T10:00:00-07:00",
    )
    blocks = [
        CalendarBlock(
            title="FYI",
            start="2026-05-11T09:00:00-07:00",
            end="2026-05-11T10:00:00-07:00",
            busy=False,
        )
    ]

    analysis = CalendarAnalyzer().analyze([request_window], blocks, duration_minutes=30)

    assert analysis.conflicts == []
    assert len(analysis.open_slots) == 1
