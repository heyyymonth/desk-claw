from datetime import timedelta

from app.llm.schemas import CalendarAnalysis, CalendarBlock, ProposedSlot, TimeWindow
from app.services.calendar import mock_calendar


class CalendarAnalyzer:
    @staticmethod
    def mock_blocks() -> list[CalendarBlock]:
        return [
            CalendarBlock(title=event.title, start=event.start, end=event.end, busy=True)
            for event in mock_calendar()
        ]

    def analyze(
        self,
        request_windows: list[TimeWindow],
        calendar_blocks: list[CalendarBlock],
        duration_minutes: int,
    ) -> CalendarAnalysis:
        busy_blocks = [block for block in calendar_blocks if block.busy]
        conflicts = [
            block
            for block in busy_blocks
            if any(_overlaps(window.start, window.end, block.start, block.end) for window in request_windows)
        ]
        open_slots = self._open_slots(request_windows, busy_blocks, duration_minutes)
        return CalendarAnalysis(conflicts=conflicts, open_slots=open_slots)

    def _open_slots(
        self,
        request_windows: list[TimeWindow],
        busy_blocks: list[CalendarBlock],
        duration_minutes: int,
    ) -> list[ProposedSlot]:
        slots = []
        for window in request_windows:
            cursor = window.start
            while cursor + timedelta(minutes=duration_minutes) <= window.end:
                end = cursor + timedelta(minutes=duration_minutes)
                if not any(_overlaps(cursor, end, block.start, block.end) for block in busy_blocks):
                    slots.append(ProposedSlot(start=cursor, end=end, reason="Open calendar slot"))
                    break
                cursor += timedelta(minutes=15)
        return slots


def _overlaps(start, end, busy_start, busy_end) -> bool:
    return start < busy_end and end > busy_start
