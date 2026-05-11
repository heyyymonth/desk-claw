from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.llm.schemas import (
    CalendarAnalysis,
    CalendarBlock,
    Decision,
    ExecutiveRules,
    ParsedMeetingRequest,
    ProposedSlot,
    Recommendation,
    Risk,
    RiskLevel,
    RuleViolation,
    TimeWindow,
)
from app.services.calendar_analyzer import CalendarAnalyzer
from app.services.risk_classifier import RiskClassifier
from app.services.rules_engine import RulesEngine


class AgentToolDefinition(BaseModel):
    name: str
    goal: str
    description: str


class AgentDefinition(BaseModel):
    name: str
    framework: str
    role: str
    objective: str
    planning_goal: str
    tools: list[AgentToolDefinition]


class ToolCallTrace(BaseModel):
    tool_name: str
    goal: str
    summary: str


class AgentPlanningResult(BaseModel):
    agent_name: str
    objective: str
    tool_calls: list[ToolCallTrace]
    decision: Decision
    confidence: float = Field(ge=0, le=1)
    rationale: list[str] = Field(min_length=1)
    risks: list[Risk]
    risk_level: RiskLevel
    safe_action: str = Field(min_length=1)
    proposed_slots: list[ProposedSlot]
    analysis: CalendarAnalysis


scheduling_agent_definition = AgentDefinition(
    name="meeting_resolution_agent",
    framework="google-adk-compatible",
    role="Resolve meeting clashes and scheduling tradeoffs for executive assistants.",
    objective=(
        "Plan a safe human-reviewed scheduling action by inspecting request intent, calendar conflicts, "
        "executive rules, urgency, sensitivity, and available alternatives."
    ),
    planning_goal=(
        "Prefer safe scheduling when an open slot exists, clarify missing context before action, defer sensitive "
        "or escalated requests, and preserve protected executive focus time."
    ),
    tools=[
        AgentToolDefinition(
            name="inspect_calendar_conflicts",
            goal="Identify busy blocks that overlap requested windows and produce candidate open slots.",
            description="Uses CalendarAnalyzer to compare preferred windows with busy calendar blocks.",
        ),
        AgentToolDefinition(
            name="validate_scheduling_rules",
            goal="Check executive policy constraints before any proposed calendar action.",
            description="Uses RulesEngine to surface protected-block and working-hours issues.",
        ),
        AgentToolDefinition(
            name="classify_priority_and_risk",
            goal="Classify risk from missing fields, conflicts, sensitivity, escalation, travel, and rules.",
            description="Combines RiskClassifier output with V0 guardrails.",
        ),
        AgentToolDefinition(
            name="select_resolution_strategy",
            goal="Choose schedule, clarify, defer, or decline with a safe action and rationale.",
            description="Applies deterministic V0 decision policy to the tool outputs.",
        ),
    ],
)


class SchedulingAgentPlanner:
    def __init__(
        self,
        calendar_analyzer: CalendarAnalyzer | None = None,
        risk_classifier: RiskClassifier | None = None,
        rules_engine: RulesEngine | None = None,
    ) -> None:
        self.calendar_analyzer = calendar_analyzer or CalendarAnalyzer()
        self.risk_classifier = risk_classifier or RiskClassifier()
        self.rules_engine = rules_engine or RulesEngine()

    def plan(
        self,
        parsed_request: ParsedMeetingRequest,
        rules: ExecutiveRules,
        calendar_blocks: list[CalendarBlock],
    ) -> AgentPlanningResult:
        windows = parsed_request.intent.preferred_windows or [_default_window(rules)]
        analysis = self.calendar_analyzer.analyze(windows, calendar_blocks, parsed_request.intent.duration_minutes)
        tool_calls = [
            ToolCallTrace(
                tool_name="inspect_calendar_conflicts",
                goal="Identify conflicts and candidate replacement slots.",
                summary=f"Found {len(analysis.conflicts)} conflict(s) and {len(analysis.open_slots)} candidate open slot(s).",
            )
        ]

        rule_violations = self.rules_engine.validate(rules)
        tool_calls.append(
            ToolCallTrace(
                tool_name="validate_scheduling_rules",
                goal="Apply executive scheduling policy before proposing action.",
                summary=f"Found {len(rule_violations)} rule violation(s).",
            )
        )

        risks = self._risks(parsed_request, analysis, rule_violations)
        tool_calls.append(
            ToolCallTrace(
                tool_name="classify_priority_and_risk",
                goal="Make risk explicit before selecting a resolution strategy.",
                summary=f"Classified overall risk as {_risk_level(risks, parsed_request)}.",
            )
        )

        decision = _decision(parsed_request, analysis)
        tool_calls.append(
            ToolCallTrace(
                tool_name="select_resolution_strategy",
                goal="Choose the safest next action for a human-reviewed workflow.",
                summary=f"Selected '{decision}' with safe action '{_safe_action(parsed_request, decision)}'.",
            )
        )

        return AgentPlanningResult(
            agent_name=scheduling_agent_definition.name,
            objective=scheduling_agent_definition.objective,
            tool_calls=tool_calls,
            decision=decision,
            confidence=_confidence(decision, analysis),
            rationale=_rationale(parsed_request, analysis),
            risks=risks,
            risk_level=_risk_level(risks, parsed_request),
            safe_action=_safe_action(parsed_request, decision),
            proposed_slots=analysis.open_slots[:3] if decision == "schedule" else [],
            analysis=analysis,
        )

    def _risks(
        self,
        parsed_request: ParsedMeetingRequest,
        analysis: CalendarAnalysis,
        rule_violations: list[RuleViolation],
    ) -> list[Risk]:
        risks = self.risk_classifier.classify(parsed_request, analysis)
        for violation in rule_violations:
            risks.append(Risk(level="medium", message=violation.message))
        if parsed_request.intent.async_candidate:
            return []
        if parsed_request.intent.escalation_required:
            risks.append(Risk(level="high", message="Request requires human escalation before any external action."))
        if parsed_request.intent.sensitivity == "high":
            risks.append(Risk(level="high", message="Sensitive request should be reviewed without exposing private details."))
        elif parsed_request.intent.sensitivity == "medium":
            risks.append(Risk(level="medium", message="Request has moderate sensitivity and should be reviewed."))
        if "travel" in parsed_request.intent.constraints:
            risks.append(Risk(level="medium", message="Travel context can affect availability and timezone assumptions."))
        return risks


def create_recommendation_from_plan(plan: AgentPlanningResult, model_status: str = "not_configured") -> Recommendation:
    return Recommendation(
        decision=plan.decision,
        confidence=plan.confidence,
        rationale=plan.rationale,
        risks=plan.risks,
        risk_level=plan.risk_level,
        safe_action=plan.safe_action,
        proposed_slots=plan.proposed_slots,
        model_status=model_status,
    )


def inspect_calendar_conflicts_tool(
    request_windows: list[TimeWindow],
    calendar_blocks: list[CalendarBlock],
    duration_minutes: int,
) -> dict:
    """Identify overlapping busy blocks and candidate open slots for a meeting request."""
    analysis = CalendarAnalyzer().analyze(request_windows, calendar_blocks, duration_minutes)
    return analysis.model_dump(mode="json")


def validate_scheduling_rules_tool(rules: ExecutiveRules) -> dict:
    """Validate executive scheduling rules before proposing a calendar action."""
    violations = RulesEngine().validate(rules)
    return {"violations": [violation.model_dump(mode="json") for violation in violations]}


def classify_priority_and_risk_tool(parsed_request: ParsedMeetingRequest, analysis: CalendarAnalysis) -> dict:
    """Classify missing-context, calendar-conflict, and priority risks."""
    risks = RiskClassifier().classify(parsed_request, analysis)
    return {"risks": [risk.model_dump(mode="json") for risk in risks]}


def select_resolution_strategy_tool(parsed_request: ParsedMeetingRequest, analysis: CalendarAnalysis) -> dict:
    """Select schedule, clarify, defer, or decline for a human-reviewed scheduling workflow."""
    decision = _decision(parsed_request, analysis)
    return {
        "decision": decision,
        "confidence": _confidence(decision, analysis),
        "rationale": _rationale(parsed_request, analysis),
        "safe_action": _safe_action(parsed_request, decision),
    }


def create_adk_root_agent(model: str = "gemini-2.0-flash"):
    try:
        from google.adk.agents import Agent
    except ImportError as exc:
        raise RuntimeError("Install google-adk to instantiate the ADK root agent.") from exc

    return Agent(
        model=model,
        name=scheduling_agent_definition.name,
        description=scheduling_agent_definition.role,
        instruction=(
            f"{scheduling_agent_definition.objective}\n"
            f"{scheduling_agent_definition.planning_goal}\n"
            "Use the tools in order when resolving scheduling clashes: inspect calendar conflicts, "
            "validate rules, classify risk, then select a resolution strategy. Never perform external "
            "calendar writes; return a human-reviewable recommendation."
        ),
        tools=[
            inspect_calendar_conflicts_tool,
            validate_scheduling_rules_tool,
            classify_priority_and_risk_tool,
            select_resolution_strategy_tool,
        ],
    )


def _decision(parsed_request: ParsedMeetingRequest, analysis: CalendarAnalysis) -> Decision:
    if parsed_request.intent.async_candidate:
        return "decline"
    if "authorization" in parsed_request.intent.missing_fields:
        return "clarify"
    if parsed_request.intent.escalation_required or parsed_request.intent.sensitivity == "high":
        return "defer"
    if parsed_request.intent.missing_fields:
        return "clarify"
    if analysis.open_slots:
        return "schedule"
    return "defer"


def _rationale(parsed_request: ParsedMeetingRequest, analysis: CalendarAnalysis) -> list[str]:
    if parsed_request.intent.async_candidate:
        return ["The request appears informational and can be handled asynchronously."]
    if parsed_request.intent.escalation_required:
        return ["Human escalation is required before replying or scheduling."]
    if parsed_request.intent.sensitivity == "high":
        return ["Sensitive context requires human review before proposing a time."]
    if parsed_request.intent.missing_fields:
        return ["Clarification is needed before proposing a time."]
    if analysis.open_slots:
        return [
            f"Found {len(analysis.open_slots)} viable slot(s) for a {parsed_request.intent.duration_minutes}-minute meeting."
        ]
    return ["No viable slot was found in the preferred windows."]


def _confidence(decision: Decision, analysis: CalendarAnalysis) -> float:
    if decision == "schedule":
        return 0.74 if analysis.open_slots else 0.55
    if decision == "clarify":
        return 0.7
    if decision == "decline":
        return 0.68
    return 0.62


def _risk_level(risks: list[Risk], parsed_request: ParsedMeetingRequest | None = None) -> RiskLevel:
    if parsed_request and parsed_request.intent.async_candidate:
        return "low"
    if any(risk.level == "high" for risk in risks):
        return "high"
    if any(risk.level == "medium" for risk in risks):
        return "medium"
    return "low"


def _safe_action(parsed_request: ParsedMeetingRequest, decision: Decision) -> str:
    if "authorization" in parsed_request.intent.missing_fields:
        return "block_action_until_requester_authorization_and_meeting_context_are_verified"
    if parsed_request.intent.escalation_required and parsed_request.intent.meeting_type == "customer":
        return "propose_or_escalate_with_ea_review_before_final_send"
    if parsed_request.intent.escalation_required:
        return "escalate_to_ea_or_executive_owner_before_reply"
    if parsed_request.intent.sensitivity == "high":
        return "route_for_ea_or_legal_hr_review_without_exposing_sensitive_details"
    if parsed_request.intent.async_candidate:
        return "recommend_async_update_instead_of_meeting"
    if parsed_request.intent.missing_fields:
        if {"requester", "purpose"}.issubset(set(parsed_request.intent.missing_fields)):
            return "ask_for_requester_purpose_and_duration_before_scheduling"
        if "duration" in parsed_request.intent.missing_fields:
            return "ask_for_duration_before_proposing_slots"
        if "recurrence_end_or_owner_confirmation" in parsed_request.intent.missing_fields:
            return "clarify_recurring_series_details_before_calendar_action"
        return "verify_identity_and_purpose_before_scheduling"
    if "travel" in parsed_request.intent.constraints:
        return "avoid_travel_blocks_and_flag_timezone_or_travel_risk"
    if "board prep" in parsed_request.intent.constraints:
        return "avoid_board_prep_protected_blocks_and_note_review_needed"
    if parsed_request.intent.meeting_type == "candidate":
        return "propose_slot_only_after_panel_context_is_sufficient"
    if decision == "schedule":
        return "propose_slot_for_human_review_before_final_send"
    return "defer_for_human_review_without_external_action"


def _default_window(rules: ExecutiveRules) -> TimeWindow:
    tz = ZoneInfo(rules.timezone)
    tomorrow = datetime.now(tz).date() + timedelta(days=1)
    start = datetime.combine(tomorrow, rules.working_hours.start, tzinfo=tz)
    end = datetime.combine(tomorrow, rules.working_hours.end, tzinfo=tz)
    return TimeWindow(start=start, end=end)
