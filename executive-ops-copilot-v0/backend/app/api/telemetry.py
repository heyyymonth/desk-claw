from fastapi import APIRouter, Depends, Query

from app.api.deps import get_telemetry_service
from app.services.telemetry_service import TelemetryService


router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


@router.get("/ai/dashboard")
def ai_technical_dashboard(
    limit: int = Query(default=250, ge=1, le=1000),
    service: TelemetryService = Depends(get_telemetry_service),
):
    return service.ai_dashboard(limit)
