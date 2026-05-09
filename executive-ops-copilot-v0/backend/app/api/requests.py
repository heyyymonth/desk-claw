from fastapi import APIRouter, Depends

from app.api.deps import get_request_parser
from app.llm.schemas import ParseRequestPayload, ParsedMeetingRequest
from app.services.request_parser import RequestParser


router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.post("/parse", response_model=ParsedMeetingRequest)
def parse_request(payload: ParseRequestPayload, service: RequestParser = Depends(get_request_parser)):
    return service.parse(payload.raw_text)
