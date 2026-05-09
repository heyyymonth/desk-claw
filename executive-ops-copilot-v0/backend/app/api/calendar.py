from fastapi import APIRouter, status

from app.llm.schemas import CalendarBlock, CalendarResponse
from app.services.calendar_analyzer import CalendarAnalyzer


router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/blocks", response_model=CalendarResponse)
def calendar_blocks():
    return CalendarResponse(blocks=CalendarAnalyzer.mock_blocks())


@router.post("/blocks", response_model=CalendarBlock, status_code=status.HTTP_201_CREATED)
def create_calendar_block(payload: CalendarBlock):
    return payload


@router.get("/mock", response_model=CalendarResponse)
def mock_calendar():
    return CalendarResponse(blocks=CalendarAnalyzer.mock_blocks())
