from app.agents.scheduling import AdkSchedulingAgentRunner, AgentRuntimeError, SchedulingAgentPlanner, create_recommendation_from_plan
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
        agent_runner: AdkSchedulingAgentRunner | None = None,
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
        self.last_ai_run: dict = _trace("deterministic", None, "not_configured", [])

    def generate(
        self,
        parsed_request: ParsedMeetingRequest,
        rules: ExecutiveRules,
        calendar_blocks: list[CalendarBlock],
    ) -> Recommendation:
        plan = self.agent_planner.plan(parsed_request, rules, calendar_blocks)
        model_status = "not_configured"
        self.last_ai_run = _trace("deterministic", plan.agent_name, model_status, [call.tool_name for call in plan.tool_calls])
        if self.agent_runner is not None:
            try:
                plan = self.agent_runner.plan(parsed_request, rules, calendar_blocks)
                model_status = "used"
                self.last_ai_run = getattr(self.agent_runner, "last_run", None) or _trace(
                    "google-adk",
                    plan.agent_name,
                    model_status,
                    [call.tool_name for call in plan.tool_calls],
                )
            except AgentRuntimeError:
                model_status = "unavailable"
                self.last_ai_run = _trace("google-adk", plan.agent_name, model_status, [call.tool_name for call in plan.tool_calls])

        deterministic = create_recommendation_from_plan(plan, model_status=model_status)

        return deterministic


def _trace(runtime: str, agent_name: str | None, model_status: str, tool_calls: list[str]) -> dict:
    return {
        "runtime": runtime,
        "agent_name": agent_name,
        "model_status": model_status,
        "tool_calls": tool_calls,
    }
