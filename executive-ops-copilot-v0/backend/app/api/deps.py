from app.core.settings import get_settings
from app.db.session import Database
from app.db.decision_log import DecisionLogRepository
from app.llm.ollama_client import OllamaClient
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
