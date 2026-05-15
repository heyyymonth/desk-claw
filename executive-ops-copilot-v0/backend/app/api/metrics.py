from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.deps import get_telemetry_service
from app.core.settings import get_settings
from app.services.telemetry_service import TelemetryService
from app.telemetry.prometheus import PROMETHEUS_TEXT_CONTENT_TYPE

router = APIRouter(tags=["metrics"])


@router.get("/metrics", include_in_schema=False)
def prometheus_metrics(
    request: Request,
    limit: int = Query(default=250, ge=1, le=1000),
    service: TelemetryService = Depends(get_telemetry_service),
) -> Response:
    settings = get_settings()
    health = {
        "status": "ok",
        "ollama": "configured" if settings.llm_mode == "ollama" else "not_configured",
        "model": settings.adk_model,
        "model_runtime": "google-adk" if settings.agent_runtime == "adk" else settings.agent_runtime,
        "model_warmup": getattr(request.app.state, "model_warmup", {"status": "unknown"}),
    }
    return Response(
        content=service.prometheus_metrics(health=health, limit=limit),
        media_type=PROMETHEUS_TEXT_CONTENT_TYPE,
    )
