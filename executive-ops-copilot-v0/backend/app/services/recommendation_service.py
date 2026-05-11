from app.agents.scheduling import AdkSchedulingAgentRunner, AgentRuntimeError, SchedulingAgentPlanner, create_recommendation_from_plan
from app.llm.schemas import CalendarBlock, ExecutiveRules, ParsedMeetingRequest, Recommendation
from app.services.calendar_analyzer import CalendarAnalyzer
from app.services.risk_classifier import RiskClassifier
from app.services.rules_engine import RulesEngine


class RecommendationService:
    def __init__(
        self,
        llm_client=None,
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

    def generate(
        self,
        parsed_request: ParsedMeetingRequest,
        rules: ExecutiveRules,
        calendar_blocks: list[CalendarBlock],
    ) -> Recommendation:
        plan = self.agent_planner.plan(parsed_request, rules, calendar_blocks)
        model_status = "not_configured"
        if self.agent_runner is not None:
            try:
                plan = self.agent_runner.plan(parsed_request, rules, calendar_blocks)
                model_status = "used"
            except AgentRuntimeError:
                model_status = "unavailable"

        deterministic = create_recommendation_from_plan(plan, model_status=model_status)

        return deterministic
