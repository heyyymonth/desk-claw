from time import perf_counter

from fastapi import APIRouter, Depends

from app.api.deps import get_actor_context, get_audit_service, get_recommendation_service
from app.core.errors import ServiceError
from app.core.settings import get_settings
from app.db.audit import ActorContext, AuditEvent
from app.llm.schemas import Recommendation, RecommendationPayload
from app.services.audit_service import AuditService
from app.services.recommendation_service import RecommendationService


router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.post("/generate", response_model=Recommendation)
def generate_recommendation(
    payload: RecommendationPayload,
    service: RecommendationService = Depends(get_recommendation_service),
    audit: AuditService = Depends(get_audit_service),
    actor: ActorContext = Depends(get_actor_context),
):
    return _generate_recommendation_with_audit(payload, service, audit, actor, "/api/recommendations/generate")


def _generate_recommendation_with_audit(
    payload: RecommendationPayload,
    service: RecommendationService,
    audit: AuditService,
    actor: ActorContext,
    endpoint: str,
) -> Recommendation:
    settings = get_settings()
    started = perf_counter()
    try:
        response = service.generate(payload.parsed_request, payload.rules, payload.calendar_blocks)
    except ServiceError as exc:
        audit.log_ai_event(
            AuditEvent(
                actor=actor,
                operation="generate_recommendation",
                endpoint=endpoint,
                model_name=settings.ollama_model,
                model_status="unavailable" if exc.code == "ollama_unavailable" else "invalid_output",
                status="error",
                latency_ms=_latency_ms(started),
                request_payload=payload,
                error_code=exc.code,
                error_message=exc.message,
            )
        )
        raise

    audit.log_ai_event(
        AuditEvent(
            actor=actor,
            operation="generate_recommendation",
            endpoint=endpoint,
            model_name=settings.ollama_model,
            model_status=response.model_status,
            status="success",
            latency_ms=_latency_ms(started),
            request_payload=payload,
            response_payload=response,
        )
    )
    return response


def _latency_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))
