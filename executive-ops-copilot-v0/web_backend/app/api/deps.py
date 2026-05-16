from app.agents.scheduling import NativeDraftAgentRunner, NativeRequestParserAgentRunner, NativeSchedulingAgentRunner
from app.core.settings import get_settings
from app.llm.schemas import CalendarBlock, ExecutiveRules
from app.services.ai_config_service import current_model_client_kwargs
from app.services.draft_service import DraftService
from app.services.recommendation_service import RecommendationService
from app.services.request_parser import RequestParser
from app.services.rules_engine import RulesEngine


def get_native_agent_runner(runner_class):
    settings = get_settings()
    model_config = current_model_client_kwargs(settings)
    if settings.agent_runtime != "native":
        return None
    return runner_class(**model_config, timeout_seconds=settings.ai_agent_timeout_seconds)


def get_request_parser() -> RequestParser:
    return RequestParser(agent_runner=get_native_agent_runner(NativeRequestParserAgentRunner))


def get_recommendation_service() -> RecommendationService:
    return RecommendationService(agent_runner=get_native_agent_runner(NativeSchedulingAgentRunner))


def get_draft_service() -> DraftService:
    return DraftService(agent_runner=get_native_agent_runner(NativeDraftAgentRunner))


def get_rules() -> ExecutiveRules:
    return RulesEngine().default_rules()


def get_calendar_blocks() -> list[CalendarBlock]:
    return []
