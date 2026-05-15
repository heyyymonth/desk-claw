from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import audit, calendar, deps, drafts, evals, feedback, metrics, recommendations, requests, rules, telemetry
from app.core.errors import ServiceError, service_error_handler
from app.core.settings import get_settings
from app.db.audit import ActorContext
from app.llm.schemas import (
    CalendarBlock,
    DraftPayload,
    ExecutiveRules,
    ParsedMeetingRequest,
    Recommendation,
    RecommendationPayload,
)
from app.models import DraftResponse as ApiDraftResponse
from app.models import MeetingRequest as ApiMeetingRequest
from app.models import Recommendation as ApiRecommendation
from app.services.model_warmup import warm_ollama_model


def create_app() -> FastAPI:
    app = FastAPI(title="Executive Ops Scheduling Copilot API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(ServiceError, service_error_handler)
    app.include_router(requests.router)
    app.include_router(recommendations.router)
    app.include_router(drafts.router)
    app.include_router(rules.router)
    app.include_router(calendar.router)
    app.include_router(feedback.router)
    app.include_router(evals.router)
    app.include_router(audit.router)
    app.include_router(telemetry.router)
    app.include_router(metrics.router)
    _add_compat_routes(app)
    app.state.model_warmup = {"status": "not_started"}

    @app.on_event("startup")
    def warm_model_on_startup() -> None:
        app.state.model_warmup = warm_ollama_model(get_settings())

    @app.get("/api/health")
    def health():
        settings = get_settings()
        return {
            "status": "ok",
            "ollama": "configured" if settings.llm_mode == "ollama" else "not_configured",
            "model": settings.adk_model,
            "adk_model": settings.adk_model,
            "ollama_model": settings.ollama_model,
            "model_runtime": "google-adk" if settings.agent_runtime == "adk" else settings.agent_runtime,
            "model_warmup": app.state.model_warmup,
        }

    return app


def _add_compat_routes(app: FastAPI) -> None:
    @app.get("/api/default-rules", include_in_schema=False)
    def default_rules_alias():
        return rules.default_rules()

    @app.get("/api/mock-calendar", include_in_schema=False)
    def mock_calendar_alias():
        return calendar.mock_calendar()

    @app.post("/api/parse-request", response_model=ApiMeetingRequest, include_in_schema=False)
    def parse_request_alias(payload: requests.ParseRequestPayload, actor: ActorContext = Depends(deps.get_actor_context)):
        return requests._parse_request_with_audit(
            payload,
            deps.get_request_parser(),
            deps.get_audit_service(),
            actor,
            "/api/parse-request",
        )

    @app.post("/api/recommendation", response_model=ApiRecommendation, include_in_schema=False)
    def recommendation_alias(payload: dict, actor: ActorContext = Depends(deps.get_actor_context)):
        if "parsed_request" in payload:
            parsed = ParsedMeetingRequest.model_validate(payload["parsed_request"])
            rules_payload = payload["rules"]
            calendar_blocks = payload.get("calendar_blocks", [])
        else:
            parsed = ParsedMeetingRequest.model_validate(payload["meeting_request"])
            rules_payload = payload["rules"]
            calendar_blocks = []
        rules_model = ExecutiveRules.model_validate(rules_payload)
        block_models = [CalendarBlock.model_validate(block) for block in calendar_blocks]
        return recommendations._generate_recommendation_with_audit(
            RecommendationPayload(parsed_request=parsed, rules=rules_model, calendar_blocks=block_models),
            deps.get_recommendation_service(),
            deps.get_audit_service(),
            actor,
            "/api/recommendation",
        )

    @app.post("/api/draft-response", response_model=ApiDraftResponse, include_in_schema=False)
    def draft_alias(payload: dict, actor: ActorContext = Depends(deps.get_actor_context)):
        recommendation = Recommendation.model_validate(payload["recommendation"])
        return drafts._generate_draft_with_audit(
            DraftPayload(recommendation=recommendation),
            deps.get_draft_service(),
            deps.get_audit_service(),
            actor,
            "/api/draft-response",
        )


app = create_app()
