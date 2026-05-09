from fastapi import APIRouter, Depends

from app.api.deps import get_draft_service
from app.llm.schemas import DraftPayload, DraftResponse
from app.services.draft_service import DraftService


router = APIRouter(prefix="/api/drafts", tags=["drafts"])


@router.post("/generate", response_model=DraftResponse)
def generate_draft(payload: DraftPayload, service: DraftService = Depends(get_draft_service)):
    return service.generate(payload.recommendation)
