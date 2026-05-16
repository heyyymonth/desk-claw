from fastapi import APIRouter, Depends

from app.api.deps import (
    get_calendar_blocks,
    get_draft_service,
    get_recommendation_service,
    get_request_parser,
    get_rules,
)
from app.llm.schemas import ParseRequestPayload, ParseRequestResponse
from app.services.ai_client import AiBackendClient, ChatPayload, ChatResponse
from app.services.draft_service import DraftService
from app.services.recommendation_service import RecommendationService
from app.services.request_parser import RequestParser

router = APIRouter(tags=["requests"])


@router.post("/api/parse-request", response_model=ParseRequestResponse)
def parse_request(
    payload: ParseRequestPayload,
    parser: RequestParser = Depends(get_request_parser),
    recommender: RecommendationService = Depends(get_recommendation_service),
    drafter: DraftService = Depends(get_draft_service),
):
    parsed_request = parser.parse(payload.raw_text)
    recommendation = recommender.generate(parsed_request, get_rules(), get_calendar_blocks())
    draft_response = drafter.generate(recommendation)
    return ParseRequestResponse(
        parsed_request=parsed_request,
        recommendation=recommendation,
        draft_response=draft_response,
        next_steps=_next_steps(recommendation.safe_action, recommendation.rationale),
    )


@router.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatPayload):
    from app.core.settings import get_settings

    settings = get_settings()
    return AiBackendClient(settings.ai_backend_url, settings.ai_agent_timeout_seconds).chat(payload.message)


def _next_steps(safe_action: str, rationale: list[str]) -> list[str]:
    steps = [safe_action.replace("_", " ").strip().capitalize()]
    for item in rationale[:2]:
        if item not in steps:
            steps.append(item)
    return steps
