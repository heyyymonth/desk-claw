from fastapi import FastAPI

from app.api import calendar, deps, drafts, evals, feedback, recommendations, requests, rules
from app.core.errors import ServiceError, service_error_handler
from app.llm.schemas import DraftPayload, RecommendationPayload, ParsedMeetingRequest, Recommendation, ExecutiveRules, CalendarBlock
from app.models import DraftResponse as ApiDraftResponse
from app.models import MeetingRequest as ApiMeetingRequest
from app.models import Recommendation as ApiRecommendation


def create_app() -> FastAPI:
    app = FastAPI(title="Executive Ops Scheduling Copilot API", version="0.1.0")
    app.add_exception_handler(ServiceError, service_error_handler)
    app.include_router(requests.router)
    app.include_router(recommendations.router)
    app.include_router(drafts.router)
    app.include_router(rules.router)
    app.include_router(calendar.router)
    app.include_router(feedback.router)
    app.include_router(evals.router)
    _add_compat_routes(app)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


def _add_compat_routes(app: FastAPI) -> None:
    @app.get("/api/default-rules", include_in_schema=False)
    def default_rules_alias():
        return rules.default_rules()

    @app.get("/api/mock-calendar", include_in_schema=False)
    def mock_calendar_alias():
        return calendar.mock_calendar()

    @app.post("/api/parse-request", response_model=ApiMeetingRequest, include_in_schema=False)
    def parse_request_alias(payload: requests.ParseRequestPayload):
        return deps.get_request_parser().parse(payload.raw_text)

    @app.post("/api/recommendation", response_model=ApiRecommendation, include_in_schema=False)
    def recommendation_alias(payload: dict):
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
        return deps.get_recommendation_service().generate(parsed, rules_model, block_models)

    @app.post("/api/draft-response", response_model=ApiDraftResponse, include_in_schema=False)
    def draft_alias(payload: dict):
        recommendation = Recommendation.model_validate(payload["recommendation"])
        return deps.get_draft_service().generate(recommendation)


app = create_app()
