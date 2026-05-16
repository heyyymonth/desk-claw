from app.agents.scheduling import (
    NATIVE_AI_RUNTIME,
    AgentRuntimeError,
    NativeSchedulingAgentRunner,
    SchedulingAgentPlanner,
    create_recommendation_from_plan,
)
from app.core.errors import ServiceError
from app.llm.schemas import CalendarBlock, ExecutiveRules, ParsedMeetingRequest, Recommendation
from app.services.calendar_analyzer import CalendarAnalyzer
from app.services.risk_classifier import RiskClassifier
from app.services.rules_engine import RulesEngine


class RecommendationService:
    def __init__(
        self,
        calendar_analyzer: CalendarAnalyzer | None = None,
        risk_classifier: RiskClassifier | None = None,
        rules_engine: RulesEngine | None = None,
        agent_planner: SchedulingAgentPlanner | None = None,
        agent_runner: NativeSchedulingAgentRunner | None = None,
    ) -> None:
        self.agent_runner = agent_runner
        self.calendar_analyzer = calendar_analyzer or CalendarAnalyzer()
        self.risk_classifier = risk_classifier or RiskClassifier()
        self.rules_engine = rules_engine or RulesEngine()
        self.agent_planner = agent_planner or SchedulingAgentPlanner(
            calendar_analyzer=self.calendar_analyzer,
            risk_classifier=self.risk_classifier,
            rules_engine=self.rules_engine,
        )

    def generate(
        self,
        parsed_request: ParsedMeetingRequest,
        rules: ExecutiveRules,
        calendar_blocks: list[CalendarBlock],
    ) -> Recommendation:
        recommendation, _trace = self.generate_with_trace(parsed_request, rules, calendar_blocks)
        return recommendation

    def generate_with_trace(
        self,
        parsed_request: ParsedMeetingRequest,
        rules: ExecutiveRules,
        calendar_blocks: list[CalendarBlock],
    ) -> tuple[Recommendation, dict]:
        if self.agent_runner is None:
            trace = _trace(NATIVE_AI_RUNTIME, "meeting_resolution_agent", "not_configured", [])
            raise ServiceError(
                "ai_model_not_configured",
                "OpenAI model configuration is required before generating recommendations.",
                status_code=503,
                ai_trace=trace,
            )

        try:
            if hasattr(self.agent_runner, "plan_with_trace"):
                plan, trace = self.agent_runner.plan_with_trace(parsed_request, rules, calendar_blocks)
            else:
                plan = self.agent_runner.plan(parsed_request, rules, calendar_blocks)
                trace = _trace(NATIVE_AI_RUNTIME, plan.agent_name, "used", [])
            model_status = "used"
        except AgentRuntimeError as exc:
            trace = _trace(NATIVE_AI_RUNTIME, "meeting_resolution_agent", "unavailable", [])
            raise ServiceError(
                "ai_model_unavailable",
                "Configured native recommendation model is unavailable.",
                status_code=502,
                ai_trace=trace,
            ) from exc

        recommendation = create_recommendation_from_plan(plan, model_status=model_status)

        return recommendation, trace


def _trace(runtime: str, agent_name: str | None, model_status: str, tool_calls: list[str]) -> dict:
    return {
        "runtime": runtime,
        "agent_name": agent_name,
        "model_status": model_status,
        "tool_calls": tool_calls,
    }
