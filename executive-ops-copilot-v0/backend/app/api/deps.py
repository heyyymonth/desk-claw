from fastapi import Header

from app.core.settings import get_settings
from app.db.audit import ActorContext, AuditRepository
from app.db.session import Database
from app.db.decision_log import DecisionLogRepository
from app.llm.ollama_client import OllamaClient
from app.services.audit_service import AuditService
from app.services.decision_log import DecisionLogService
from app.services.draft_service import DraftService
from app.services.recommendation_service import RecommendationService
from app.services.request_parser import RequestParser
from app.services.workflow_decision_log import WorkflowDecisionLogService


def get_llm_client():
    settings = get_settings()
    if settings.llm_mode == "mock":
        return None
    return OllamaClient(settings.ollama_base_url, settings.ollama_model)


def get_database() -> Database:
    return Database(get_settings().database_url)


def get_actor_context(
    x_actor_id: str | None = Header(default=None),
    x_actor_email: str | None = Header(default=None),
    x_actor_name: str | None = Header(default=None),
) -> ActorContext:
    return ActorContext(
        actor_id=x_actor_id or "local-user",
        email=x_actor_email,
        display_name=x_actor_name or "Local User",
    )


def get_audit_service() -> AuditService:
    return AuditService(AuditRepository(get_database()))


def get_request_parser() -> RequestParser:
    return RequestParser(get_llm_client())


def get_recommendation_service() -> RecommendationService:
    return RecommendationService(get_llm_client())


def get_draft_service() -> DraftService:
    return DraftService(get_llm_client())


def get_decision_log_service() -> DecisionLogService:
    return DecisionLogService(get_database())


def get_workflow_decision_log_service() -> WorkflowDecisionLogService:
    return WorkflowDecisionLogService(DecisionLogRepository(get_settings().sqlite_path))
