from app.agents.scheduling import AdkSchedulingAgentRunner, AgentRuntimeError, SchedulingAgentPlanner, create_recommendation_from_plan
from app.core.errors import ServiceError
from app.llm.output_parser import InvalidLLMOutput, parse_llm_output
from app.llm.prompts import recommendation_prompt
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
        self.llm_client = llm_client
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

        if self.llm_client is None or self.agent_runner is not None:
            return deterministic

        output = self.llm_client.generate_structured(
            recommendation_prompt(
                {
                    "parsed_request": parsed_request.model_dump(mode="json"),
                    "rules": rules.model_dump(mode="json"),
                    "analysis": plan.analysis.model_dump(mode="json"),
                    "agent_plan": plan.model_dump(mode="json"),
                }
            ),
            Recommendation,
        )
        try:
            model_recommendation = parse_llm_output(output, Recommendation)
        except InvalidLLMOutput as exc:
            raise ServiceError(
                "ollama_invalid_output",
                "Gemma returned invalid recommendation output.",
                status_code=502,
            ) from exc
        return model_recommendation.model_copy(
            update={
                "decision": deterministic.decision,
                "rationale": deterministic.rationale,
                "risks": deterministic.risks or model_recommendation.risks,
                "risk_level": deterministic.risk_level,
                "safe_action": deterministic.safe_action,
                "proposed_slots": deterministic.proposed_slots,
                "model_status": "used",
            }
            )
