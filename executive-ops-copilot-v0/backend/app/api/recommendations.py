from fastapi import APIRouter, Depends

from app.api.deps import get_recommendation_service
from app.llm.schemas import Recommendation, RecommendationPayload
from app.services.recommendation_service import RecommendationService


router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.post("/generate", response_model=Recommendation)
def generate_recommendation(
    payload: RecommendationPayload,
    service: RecommendationService = Depends(get_recommendation_service),
):
    return service.generate(payload.parsed_request, payload.rules, payload.calendar_blocks)
