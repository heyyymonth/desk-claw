import contextlib
import io
import json
import multiprocessing
import os
import queue
import threading
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, ValidationError

from app.llm.schemas import (
    CalendarAnalysis,
    CalendarBlock,
    Decision,
    DraftResponse,
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

DEFAULT_OLLAMA_MODEL = "gemma4:latest"
DEFAULT_ADK_MODEL = f"ollama_chat/{DEFAULT_OLLAMA_MODEL}"
_SCHEDULING_TOOL_PAYLOADS: dict[str, dict] = {}


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


class AgentRuntimeError(RuntimeError):
    pass


scheduling_agent_definition = AgentDefinition(
    name="meeting_resolution_agent",
    framework="google-adk",
    role="Resolve meeting clashes and scheduling tradeoffs for executive assistants by reasoning through tool calls.",
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


request_parser_agent_definition = AgentDefinition(
    name="meeting_request_parser_agent",
    framework="google-adk",
    role="Extract structured meeting intent from raw scheduling requests using the configured ADK model.",
    objective=(
        "Produce a strict ParsedMeetingRequest JSON object from raw intake text while preserving "
        "requester, priority, meeting type, sensitivity, missing fields, and scheduling constraints."
    ),
    planning_goal=(
        "Use the extraction tool for grounded V0 labels, then reason only within the schema and return valid JSON."
    ),
    tools=[
        AgentToolDefinition(
            name="extract_meeting_intent",
            goal="Ground parse labels and missing fields from raw request text.",
            description="Returns ParsedMeetingRequest-shaped JSON using local V0 parsing guardrails.",
        )
    ],
)


draft_agent_definition = AgentDefinition(
    name="meeting_draft_agent",
    framework="google-adk",
    role="Draft human-reviewable meeting replies from scheduling recommendations using the configured ADK model.",
    objective=(
        "Generate a concise DraftResponse JSON object that reflects the recommendation decision, "
        "safe action, risk posture, and available slots without leaking sensitive context."
    ),
    planning_goal=(
        "Use the guarded draft tool first, then only improve wording while preserving draft_type and safety constraints."
    ),
    tools=[
        AgentToolDefinition(
            name="compose_guarded_draft",
            goal="Create a safe baseline draft that matches the recommendation decision.",
            description="Returns DraftResponse-shaped JSON for schedule, clarify, defer, and decline decisions.",
        )
    ],
)


ADK_AGENT_INSTRUCTION = (
    "You are meeting_resolution_agent. Call resolve_scheduling_plan exactly once with payload_id copied exactly "
    "from the user JSON. Return only the tool response JSON. Do not write calendars or send email."
)


REQUEST_PARSER_AGENT_INSTRUCTION = (
    f"{request_parser_agent_definition.objective}\n"
    f"{request_parser_agent_definition.planning_goal}\n\n"
    "You must call extract_meeting_intent with the raw request text. Return only a JSON object matching "
    "ParsedMeetingRequest. Do not invent attendees, times, or authorization. Use local context only."
)


DRAFT_AGENT_INSTRUCTION = (
    f"{draft_agent_definition.objective}\n"
    f"{draft_agent_definition.planning_goal}\n\n"
    "You must call compose_guarded_draft with the recommendation JSON before returning. Return only a JSON object "
    "matching DraftResponse. Do not expose hidden sensitive details and do not propose slots unless present."
)


def local_adk_model_name() -> str:
    return DEFAULT_ADK_MODEL


def default_adk_model_name() -> str:
    return DEFAULT_ADK_MODEL


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


class AdkSchedulingAgentRunner:
    def __init__(
        self,
        model: str,
        ollama_base_url: str | None = None,
        app_name: str = "desk_ai_scheduling",
        timeout_seconds: float = 45.0,
    ) -> None:
        self.model = model
        self.ollama_base_url = ollama_base_url
        self.app_name = app_name
        self.timeout_seconds = timeout_seconds

    def plan(
        self,
        parsed_request: ParsedMeetingRequest,
        rules: ExecutiveRules,
        calendar_blocks: list[CalendarBlock],
    ) -> AgentPlanningResult:
        plan, _trace = self.plan_with_trace(parsed_request, rules, calendar_blocks)
        return plan

    def plan_with_trace(
        self,
        parsed_request: ParsedMeetingRequest,
        rules: ExecutiveRules,
        calendar_blocks: list[CalendarBlock],
    ) -> tuple[AgentPlanningResult, dict]:
        deterministic_plan = SchedulingAgentPlanner().plan(parsed_request, rules, calendar_blocks)
        try:
            result = _run_agent_process(
                "schedule",
                {
                    "model": self.model,
                    "ollama_base_url": self.ollama_base_url,
                    "app_name": self.app_name,
                    "parsed_request": parsed_request.model_dump(mode="json"),
                    "rules": rules.model_dump(mode="json"),
                    "calendar_blocks": [block.model_dump(mode="json") for block in calendar_blocks],
                },
                self.timeout_seconds,
                "ADK scheduling agent timed out.",
                "ADK scheduling agent could not complete a planning run.",
            )
            output = result["output"]
            plan = self._merge_model_output(output, deterministic_plan)
            trace = _agent_run_trace(
                agent_name=scheduling_agent_definition.name,
                app_name=self.app_name,
                model=self.model,
                tool_calls=result["tool_calls"],
            )
            return plan, trace
        except AgentRuntimeError:
            raise

    def _run_agent(
        self,
        agent,
        parsed_request: ParsedMeetingRequest,
        rules: ExecutiveRules,
        calendar_blocks: list[CalendarBlock],
    ) -> dict:
        planner_payload = {
            "parsed_request": parsed_request.model_dump(mode="json"),
            "rules": rules.model_dump(mode="json"),
            "calendar_blocks": [block.model_dump(mode="json") for block in calendar_blocks],
        }
        payload_id = uuid4().hex
        _SCHEDULING_TOOL_PAYLOADS[payload_id] = planner_payload
        try:
            output, _tool_calls = _run_adk_json_with_tool_calls(
                agent=agent,
                app_name=self.app_name,
                session_prefix="scheduling",
                payload={
                    "task": "Resolve this meeting request with tool-backed reasoning.",
                    "payload_id": payload_id,
                },
                max_llm_calls=4,
                return_on_tool_response=True,
            )
            return output
        finally:
            _SCHEDULING_TOOL_PAYLOADS.pop(payload_id, None)

    def _merge_model_output(self, output: dict, deterministic_plan: AgentPlanningResult) -> AgentPlanningResult:
        model_decision = output.get("decision", deterministic_plan.decision)
        decision = model_decision if model_decision == deterministic_plan.decision else deterministic_plan.decision
        proposed_slots = output.get("proposed_slots", deterministic_plan.proposed_slots)
        if decision != "schedule":
            proposed_slots = []
        elif not proposed_slots:
            proposed_slots = deterministic_plan.proposed_slots

        try:
            return AgentPlanningResult.model_validate(
                {
                    "agent_name": scheduling_agent_definition.name,
                    "objective": scheduling_agent_definition.objective,
                    "tool_calls": deterministic_plan.tool_calls,
                    "decision": decision,
                    "confidence": output.get("confidence", deterministic_plan.confidence),
                    "rationale": output.get("rationale") or deterministic_plan.rationale,
                    "risks": output.get("risks", deterministic_plan.risks),
                    "risk_level": deterministic_plan.risk_level,
                    "safe_action": deterministic_plan.safe_action,
                    "proposed_slots": proposed_slots,
                    "analysis": deterministic_plan.analysis,
                }
            )
        except ValidationError:
            return deterministic_plan


class AdkRequestParserAgentRunner:
    def __init__(
        self,
        model: str = DEFAULT_ADK_MODEL,
        ollama_base_url: str | None = None,
        app_name: str = "desk_ai_request_parser",
        timeout_seconds: float = 45.0,
    ) -> None:
        self.model = model
        self.ollama_base_url = ollama_base_url
        self.app_name = app_name
        self.timeout_seconds = timeout_seconds

    def parse(self, raw_text: str) -> ParsedMeetingRequest:
        parsed, _trace = self.parse_with_trace(raw_text)
        return parsed

    def parse_with_trace(self, raw_text: str) -> tuple[ParsedMeetingRequest, dict]:
        try:
            result = _run_agent_process(
                "parse",
                {
                    "model": self.model,
                    "ollama_base_url": self.ollama_base_url,
                    "app_name": self.app_name,
                    "raw_text": raw_text,
                },
                self.timeout_seconds,
                "ADK request parser timed out.",
                "ADK request parser could not complete.",
            )
            output = result["output"]
            parsed = ParsedMeetingRequest.model_validate(output)
            trace = _agent_run_trace(
                agent_name=request_parser_agent_definition.name,
                app_name=self.app_name,
                model=self.model,
                tool_calls=result["tool_calls"],
            )
            return parsed, trace
        except AgentRuntimeError:
            raise
        except Exception as exc:
            raise AgentRuntimeError("ADK request parser could not complete.") from exc

    def _run_parse(self, raw_text: str) -> dict:
        agent = create_adk_request_parser_agent(self.model, self.ollama_base_url)
        return _run_adk_json(
            agent=agent,
            app_name=self.app_name,
            session_prefix="parse",
            payload={"task": "Parse this raw scheduling request.", "raw_text": raw_text},
            max_llm_calls=4,
        )


class AdkDraftAgentRunner:
    def __init__(
        self,
        model: str = DEFAULT_ADK_MODEL,
        ollama_base_url: str | None = None,
        app_name: str = "desk_ai_draft",
        timeout_seconds: float = 45.0,
    ) -> None:
        self.model = model
        self.ollama_base_url = ollama_base_url
        self.app_name = app_name
        self.timeout_seconds = timeout_seconds

    def generate(self, recommendation: Recommendation) -> DraftResponse:
        draft, _trace = self.generate_with_trace(recommendation)
        return draft

    def generate_with_trace(self, recommendation: Recommendation) -> tuple[DraftResponse, dict]:
        try:
            result = _run_agent_process(
                "draft",
                {
                    "model": self.model,
                    "ollama_base_url": self.ollama_base_url,
                    "app_name": self.app_name,
                    "recommendation": recommendation.model_dump(mode="json"),
                },
                self.timeout_seconds,
                "ADK draft agent timed out.",
                "ADK draft agent could not complete.",
            )
            output = result["output"]
            draft = DraftResponse.model_validate(output)
            trace = _agent_run_trace(
                agent_name=draft_agent_definition.name,
                app_name=self.app_name,
                model=self.model,
                tool_calls=result["tool_calls"],
            )
            return draft, trace
        except AgentRuntimeError:
            raise
        except Exception as exc:
            raise AgentRuntimeError("ADK draft agent could not complete.") from exc

    def _run_generate(self, recommendation: Recommendation) -> dict:
        agent = create_adk_draft_agent(self.model, self.ollama_base_url)
        return _run_adk_json(
            agent=agent,
            app_name=self.app_name,
            session_prefix="draft",
            payload={
                "task": "Generate a safe human-reviewable draft response.",
                "recommendation": recommendation.model_dump(mode="json"),
            },
            max_llm_calls=4,
        )


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


def resolve_scheduling_plan(payload_id: str) -> dict:
    """Resolve a scheduling request using the deterministic planner as an ADK tool boundary.

    Args:
        payload_id: Short id for the request payload registered by the backend before the ADK run.
    """
    payload = _SCHEDULING_TOOL_PAYLOADS.get(payload_id)
    if payload is None:
        payload = _loads_json_object(payload_id)
    parsed_request = ParsedMeetingRequest.model_validate(payload["parsed_request"])
    rules = ExecutiveRules.model_validate(payload["rules"])
    calendar_blocks = [CalendarBlock.model_validate(block) for block in payload.get("calendar_blocks", [])]
    plan = SchedulingAgentPlanner().plan(parsed_request, rules, calendar_blocks)
    return create_recommendation_from_plan(plan, model_status="used").model_dump(mode="json")


def inspect_calendar_conflicts_tool(
    request_windows: list[TimeWindow],
    calendar_blocks: list[CalendarBlock],
    duration_minutes: int,
) -> dict:
    """Identify overlapping busy blocks and candidate open slots for a meeting request."""
    analysis = CalendarAnalyzer().analyze(request_windows, calendar_blocks, duration_minutes)
    return analysis.model_dump(mode="json")


def inspect_calendar_conflicts(
    request_windows_json: str,
    calendar_blocks_json: str,
    duration_minutes: int,
) -> dict:
    """Inspect requested meeting windows against busy calendar blocks and return conflicts plus open slots.

    Args:
        request_windows_json: JSON array of requested time windows with start and end datetimes.
        calendar_blocks_json: JSON array of calendar blocks with title, start, end, and busy fields.
        duration_minutes: Requested meeting duration in minutes.
    """
    request_windows = _loads_json_array(request_windows_json)
    calendar_blocks = _loads_json_array(calendar_blocks_json)
    windows = [TimeWindow.model_validate(window) for window in request_windows]
    blocks = [CalendarBlock.model_validate(block) for block in calendar_blocks]
    return inspect_calendar_conflicts_tool(windows, blocks, duration_minutes)


def validate_scheduling_rules_tool(rules: ExecutiveRules) -> dict:
    """Validate executive scheduling rules before proposing a calendar action."""
    violations = RulesEngine().validate(rules)
    return {"violations": [violation.model_dump(mode="json") for violation in violations]}


def validate_scheduling_rules(rules_json: str) -> dict:
    """Validate executive working hours, protected blocks, and scheduling preferences before action.

    Args:
        rules_json: JSON object containing executive scheduling rules.
    """
    rules = _loads_json_object(rules_json)
    return validate_scheduling_rules_tool(ExecutiveRules.model_validate(rules))


def classify_priority_and_risk_tool(parsed_request: ParsedMeetingRequest, analysis: CalendarAnalysis) -> dict:
    """Classify missing-context, calendar-conflict, and priority risks."""
    risks = RiskClassifier().classify(parsed_request, analysis)
    return {"risks": [risk.model_dump(mode="json") for risk in risks]}


def classify_priority_and_risk(
    parsed_request_json: str,
    analysis_json: str,
    rule_violations_json: str,
) -> dict:
    """Classify meeting risk using request intent, calendar analysis, and rule violations.

    Args:
        parsed_request_json: JSON object containing the parsed meeting request.
        analysis_json: JSON object returned by inspect_calendar_conflicts.
        rule_violations_json: JSON array from validate_scheduling_rules violations.
    """
    parsed_request = _loads_json_object(parsed_request_json)
    analysis = _loads_json_object(analysis_json)
    rule_violations = _loads_json_array(rule_violations_json)
    request = ParsedMeetingRequest.model_validate(parsed_request)
    calendar_analysis = CalendarAnalysis.model_validate(analysis)
    risks = RiskClassifier().classify(request, calendar_analysis)
    for violation in rule_violations or []:
        message = violation.get("message")
        if message:
            risks.append(Risk(level="medium", message=message))
    if request.intent.async_candidate:
        risks = []
    if request.intent.escalation_required:
        risks.append(Risk(level="high", message="Request requires human escalation before any external action."))
    if request.intent.sensitivity == "high":
        risks.append(Risk(level="high", message="Sensitive request should be reviewed without exposing private details."))
    elif request.intent.sensitivity == "medium":
        risks.append(Risk(level="medium", message="Request has moderate sensitivity and should be reviewed."))
    if "travel" in request.intent.constraints:
        risks.append(Risk(level="medium", message="Travel context can affect availability and timezone assumptions."))
    return {
        "risks": [risk.model_dump(mode="json") for risk in risks],
        "risk_level": _risk_level(risks, request),
    }


def select_resolution_strategy_tool(parsed_request: ParsedMeetingRequest, analysis: CalendarAnalysis) -> dict:
    """Select schedule, clarify, defer, or decline for a human-reviewed scheduling workflow."""
    decision = _decision(parsed_request, analysis)
    return {
        "decision": decision,
        "confidence": _confidence(decision, analysis),
        "rationale": _rationale(parsed_request, analysis),
        "safe_action": _safe_action(parsed_request, decision),
    }


def select_resolution_strategy(parsed_request_json: str, analysis_json: str, risks_json: str) -> dict:
    """Choose schedule, clarify, defer, or decline with human-review guardrails.

    Args:
        parsed_request_json: JSON object containing the parsed meeting request.
        analysis_json: JSON object returned by inspect_calendar_conflicts.
        risks_json: JSON array returned by classify_priority_and_risk.
    """
    parsed_request = _loads_json_object(parsed_request_json)
    analysis = _loads_json_object(analysis_json)
    risks = _loads_json_array(risks_json)
    request = ParsedMeetingRequest.model_validate(parsed_request)
    calendar_analysis = CalendarAnalysis.model_validate(analysis)
    risk_models = [Risk.model_validate(risk) for risk in risks]
    decision = _decision(request, calendar_analysis)
    return {
        "decision": decision,
        "confidence": _confidence(decision, calendar_analysis),
        "rationale": _rationale(request, calendar_analysis),
        "risks": [risk.model_dump(mode="json") for risk in risk_models],
        "risk_level": _risk_level(risk_models, request),
        "safe_action": _safe_action(request, decision),
        "proposed_slots": [
            slot.model_dump(mode="json") for slot in calendar_analysis.open_slots[:3]
        ]
        if decision == "schedule"
        else [],
    }


def extract_meeting_intent(raw_text: str) -> dict:
    """Extract a strict ParsedMeetingRequest from raw scheduling text.

    Args:
        raw_text: Raw inbound meeting request text.
    """
    from app.services.request_parser import fallback_parse

    return fallback_parse(raw_text).model_dump(mode="json")


def compose_guarded_draft(recommendation_json: str) -> dict:
    """Compose a safe draft response from a scheduling recommendation.

    Args:
        recommendation_json: JSON object matching the Recommendation schema.
    """
    recommendation = Recommendation.model_validate(_loads_json_object(recommendation_json))
    return deterministic_draft_response(recommendation, "used").model_dump(mode="json")


def deterministic_draft_response(recommendation: Recommendation, model_status: str) -> DraftResponse:
    if recommendation.decision == "schedule" and recommendation.proposed_slots:
        slot = recommendation.proposed_slots[0]
        return DraftResponse(
            subject="Meeting time available",
            body=f"We can meet at {slot.start.strftime('%A at %I:%M %p')}. Please confirm whether that works.",
            tone="warm",
            draft_type="accept",
            model_status=model_status,
        )
    if recommendation.decision == "decline":
        return DraftResponse(
            subject="Meeting request",
            body="Thanks for reaching out. We are not able to prioritize this meeting right now.",
            tone="firm",
            draft_type="decline",
            model_status=model_status,
        )
    if recommendation.decision == "defer":
        return DraftResponse(
            subject="Meeting request",
            body="Thanks for reaching out. We need to review the request, priority, and availability before proposing a time.",
            tone="concise",
            draft_type="defer",
            model_status=model_status,
        )
    return DraftResponse(
        subject="Meeting request",
        body="Thanks for reaching out. We need a bit more information before proposing a time.",
        tone="concise",
        draft_type="clarify",
        model_status=model_status,
    )


def create_adk_root_agent(model: str = DEFAULT_ADK_MODEL, ollama_base_url: str | None = None):
    try:
        from google.adk.agents import Agent
    except ImportError as exc:
        raise RuntimeError("Install google-adk to instantiate the ADK root agent.") from exc

    agent_model = _adk_model(model, ollama_base_url)
    return Agent(
        model=agent_model,
        name=scheduling_agent_definition.name,
        description=scheduling_agent_definition.role,
        instruction=ADK_AGENT_INSTRUCTION,
        tools=[resolve_scheduling_plan],
    )


def create_adk_request_parser_agent(model: str = DEFAULT_ADK_MODEL, ollama_base_url: str | None = None):
    try:
        from google.adk.agents import Agent
    except ImportError as exc:
        raise RuntimeError("Install google-adk to instantiate the ADK request parser agent.") from exc

    return Agent(
        model=_adk_model(model, ollama_base_url),
        name=request_parser_agent_definition.name,
        description=request_parser_agent_definition.role,
        instruction=REQUEST_PARSER_AGENT_INSTRUCTION,
        tools=[extract_meeting_intent],
    )


def create_adk_draft_agent(model: str = DEFAULT_ADK_MODEL, ollama_base_url: str | None = None):
    try:
        from google.adk.agents import Agent
    except ImportError as exc:
        raise RuntimeError("Install google-adk to instantiate the ADK draft agent.") from exc

    return Agent(
        model=_adk_model(model, ollama_base_url),
        name=draft_agent_definition.name,
        description=draft_agent_definition.role,
        instruction=DRAFT_AGENT_INSTRUCTION,
        tools=[compose_guarded_draft],
    )


def _adk_model(model: str, ollama_base_url: str | None = None):
    if model.startswith("ollama_chat/"):
        if ollama_base_url:
            os.environ["OLLAMA_API_BASE"] = ollama_base_url
        try:
            from google.adk.models.lite_llm import LiteLlm
        except ImportError as exc:
            raise RuntimeError("Install google-adk with litellm support to use Ollama-hosted ADK models.") from exc
        return LiteLlm(model=model)
    return model


def _agent_run_trace(agent_name: str, app_name: str, model: str, tool_calls: list[str]) -> dict:
    return {
        "runtime": "google-adk",
        "agent_name": agent_name,
        "app_name": app_name,
        "model": model,
        "model_status": "used",
        "tool_calls": tool_calls,
    }


def _run_agent_process(
    operation: str,
    payload: dict,
    timeout_seconds: float,
    timeout_message: str,
    failure_message: str,
) -> dict:
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue(maxsize=1)
    process = context.Process(target=_agent_process_entrypoint, args=(operation, payload, result_queue))
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join()
        raise AgentRuntimeError(timeout_message)

    try:
        status, result = result_queue.get(timeout=1)
    except queue.Empty as exc:
        if process.exitcode == 0:
            raise AgentRuntimeError(failure_message) from exc
        raise AgentRuntimeError(f"{failure_message} Exit code: {process.exitcode}.") from exc

    if status == "ok":
        return result
    raise AgentRuntimeError(f"{failure_message} {result}")


def _agent_process_entrypoint(operation: str, payload: dict, result_queue) -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    threading.excepthook = lambda args: None
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result_queue.put(("ok", _run_agent_operation(operation, payload)))
    except Exception as exc:
        detail = str(exc)
        captured_stderr = stderr.getvalue().strip()
        if captured_stderr:
            detail = f"{detail} {captured_stderr}"
        result_queue.put(("error", detail))


def _run_agent_operation(operation: str, payload: dict) -> dict:
    model = payload["model"]
    ollama_base_url = payload.get("ollama_base_url")
    app_name = payload["app_name"]
    if operation == "schedule":
        agent = create_adk_root_agent(model=model, ollama_base_url=ollama_base_url)
        parsed_request = ParsedMeetingRequest.model_validate(payload["parsed_request"])
        rules = ExecutiveRules.model_validate(payload["rules"])
        calendar_blocks = [CalendarBlock.model_validate(block) for block in payload["calendar_blocks"]]
        planner_payload = {
            "parsed_request": parsed_request.model_dump(mode="json"),
            "rules": rules.model_dump(mode="json"),
            "calendar_blocks": [block.model_dump(mode="json") for block in calendar_blocks],
        }
        payload_id = uuid4().hex
        _SCHEDULING_TOOL_PAYLOADS[payload_id] = planner_payload
        try:
            output, tool_calls = _run_adk_json_with_tool_calls(
                agent=agent,
                app_name=app_name,
                session_prefix="scheduling",
                payload={
                    "task": "Resolve this meeting request with tool-backed reasoning.",
                    "payload_id": payload_id,
                },
                max_llm_calls=4,
                return_on_tool_response=True,
            )
            return {"output": output, "tool_calls": tool_calls}
        finally:
            _SCHEDULING_TOOL_PAYLOADS.pop(payload_id, None)
    if operation == "parse":
        agent = create_adk_request_parser_agent(model, ollama_base_url)
        output, tool_calls = _run_adk_json_with_tool_calls(
            agent=agent,
            app_name=app_name,
            session_prefix="parse",
            payload={"task": "Parse this raw scheduling request.", "raw_text": payload["raw_text"]},
            max_llm_calls=4,
            return_on_tool_response=True,
        )
        return {"output": output, "tool_calls": tool_calls}
    if operation == "draft":
        agent = create_adk_draft_agent(model, ollama_base_url)
        recommendation = Recommendation.model_validate(payload["recommendation"])
        output, tool_calls = _run_adk_json_with_tool_calls(
            agent=agent,
            app_name=app_name,
            session_prefix="draft",
            payload={
                "task": "Generate a safe human-reviewable draft response.",
                "recommendation": recommendation.model_dump(mode="json"),
            },
            max_llm_calls=4,
            return_on_tool_response=True,
        )
        return {"output": output, "tool_calls": tool_calls}
    raise AgentRuntimeError(f"Unsupported ADK operation: {operation}")


def _run_adk_json(agent, app_name: str, session_prefix: str, payload: dict, max_llm_calls: int) -> dict:
    output, _tool_calls = _run_adk_json_with_tool_calls(agent, app_name, session_prefix, payload, max_llm_calls)
    return output


def _run_adk_json_with_tool_calls(
    agent,
    app_name: str,
    session_prefix: str,
    payload: dict,
    max_llm_calls: int,
    return_on_tool_response: bool = False,
) -> tuple[dict, list[str]]:
    try:
        from google.adk.runners import RunConfig, Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
    except ImportError as exc:
        raise AgentRuntimeError("Install google-adk to run the local agent.") from exc

    session_service = InMemorySessionService()
    user_id = "desk-ai-local-user"
    session_id = f"{session_prefix}-{uuid4()}"
    session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
    runner = Runner(app_name=app_name, agent=agent, session_service=session_service)
    message = types.Content(role="user", parts=[types.Part.from_text(text=json.dumps(payload))])

    final_text = ""
    tool_calls: list[str] = []
    tool_responses: list[dict] = []
    events = runner.run(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
        run_config=RunConfig(max_llm_calls=max_llm_calls),
    )
    for event in events:
        tool_calls.extend(_tool_call_names_from_event(event))
        tool_responses.extend(_tool_response_objects_from_event(event))
        if return_on_tool_response and tool_responses:
            close = getattr(events, "close", None)
            if close:
                close()
            return tool_responses[-1], _dedupe(tool_calls)
        if event.content is None:
            continue
        for part in event.content.parts or []:
            if part.text:
                final_text = part.text

    if not final_text:
        if tool_responses:
            return tool_responses[-1], _dedupe(tool_calls)
        raise AgentRuntimeError("ADK agent returned no final text.")
    return _loads_json_object(final_text), _dedupe(tool_calls)


def _tool_call_names_from_event(event) -> list[str]:
    names: list[str] = []
    content = getattr(event, "content", None)
    if content is None:
        return names
    for part in getattr(content, "parts", None) or []:
        function_call = getattr(part, "function_call", None)
        name = getattr(function_call, "name", None)
        if name:
            names.append(name)
    return names


def _tool_response_objects_from_event(event) -> list[dict]:
    responses: list[dict] = []
    content = getattr(event, "content", None)
    if content is None:
        return responses
    for part in getattr(content, "parts", None) or []:
        function_response = getattr(part, "function_response", None)
        if function_response is None:
            continue
        payload = getattr(function_response, "response", None)
        if isinstance(payload, dict):
            responses.append(payload)
    return responses


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _loads_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError as exc:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise AgentRuntimeError("ADK scheduling agent returned non-JSON output.") from exc
        value = json.loads(stripped[start : end + 1])
    if not isinstance(value, dict):
        raise AgentRuntimeError("ADK scheduling agent returned a non-object JSON payload.")
    return value


def _loads_json_array(text: str) -> list:
    value = json.loads(text)
    if not isinstance(value, list):
        raise AgentRuntimeError("ADK tool expected a JSON array payload.")
    return value


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
