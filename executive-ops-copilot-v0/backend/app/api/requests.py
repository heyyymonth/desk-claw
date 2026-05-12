from time import perf_counter

from fastapi import APIRouter, Depends

from app.api.deps import get_actor_context, get_audit_service, get_request_parser
from app.core.errors import ServiceError
from app.core.settings import get_settings
from app.db.audit import ActorContext, AuditEvent
from app.llm.schemas import ParseRequestPayload, ParsedMeetingRequest
from app.services.audit_service import AuditService
from app.services.request_parser import RequestParser


router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.post("/parse", response_model=ParsedMeetingRequest)
def parse_request(
    payload: ParseRequestPayload,
    service: RequestParser = Depends(get_request_parser),
    audit: AuditService = Depends(get_audit_service),
    actor: ActorContext = Depends(get_actor_context),
):
    return _parse_request_with_audit(payload, service, audit, actor, "/api/requests/parse")


def _parse_request_with_audit(
    payload: ParseRequestPayload,
    service: RequestParser,
    audit: AuditService,
    actor: ActorContext,
    endpoint: str,
) -> ParsedMeetingRequest:
    settings = get_settings()
    started = perf_counter()
    try:
        response, trace = service.parse_with_trace(payload.raw_text)
    except ServiceError as exc:
        trace = exc.ai_trace
        audit.log_ai_event(
            AuditEvent(
                actor=actor,
                operation="parse_request",
                endpoint=endpoint,
                model_name=settings.adk_model,
                model_status=trace.get("model_status") or ("unavailable" if exc.code == "adk_model_unavailable" else "invalid_output"),
                status="error",
                latency_ms=_latency_ms(started),
                request_payload=payload,
                error_code=exc.code,
                error_message=exc.message,
                runtime=trace.get("runtime", "unknown"),
                agent_name=trace.get("agent_name"),
                tool_calls=trace.get("tool_calls", []),
            )
        )
        raise

    audit.log_ai_event(
        AuditEvent(
            actor=actor,
            operation="parse_request",
            endpoint=endpoint,
            model_name=settings.adk_model,
            model_status=trace.get("model_status", "not_configured"),
            status="success",
            latency_ms=_latency_ms(started),
            request_payload=payload,
            response_payload=response,
            runtime=trace.get("runtime", "unknown"),
            agent_name=trace.get("agent_name"),
            tool_calls=trace.get("tool_calls", []),
        )
    )
    return response


def _latency_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))
