from fastapi import APIRouter, Depends, Query

from app.api.deps import get_telemetry_service, require_admin_access
from app.services.telemetry_service import TelemetryService

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


@router.get("/ai/dashboard")
def ai_technical_dashboard(
    limit: int = Query(default=250, ge=1, le=1000),
    _: None = Depends(require_admin_access),
    service: TelemetryService = Depends(get_telemetry_service),
):
    return service.ai_dashboard(limit)
