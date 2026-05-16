import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
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

DEFAULT_MODEL_PROVIDER = "ai-backend"
DEFAULT_MODEL_NAME = "gateway-default"
NATIVE_AI_RUNTIME = "native-agent"


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


@dataclass(frozen=True)
class ModelResponse:
    output: dict[str, Any]
    model_name: str
    provider: str


class ModelClient:
    def complete_json(self, *, system_prompt: str, payload: dict[str, Any], timeout_seconds: float) -> ModelResponse:
        raise NotImplementedError


class AiBackendModelClient(ModelClient):
    def __init__(self, gateway_url: str = "http://localhost:9000") -> None:
        self.gateway_url = gateway_url.rstrip("/")

    def complete_json(self, *, system_prompt: str, payload: dict[str, Any], timeout_seconds: float) -> ModelResponse:
        request_payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, default=str)},
            ],
            "temperature": 0.2,
            "max_tokens": 2000,
            "stream": False,
            "metadata": {"source": "web-backend"},
        }
        try:
            response = httpx.post(f"{self.gateway_url}/v1/chat", json=request_payload, timeout=timeout_seconds)
            if response.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "AI Backend request failed",
                    request=httpx.Request("POST", f"{self.gateway_url}/v1/chat"),
                    response=response,
                )
            body = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise AgentRuntimeError(f"AI Backend model request failed: {exc}") from exc

        content = body.get("content")
        if not isinstance(content, str):
            raise AgentRuntimeError("AI Backend response did not include text content.")
        provider = body.get("provider") if isinstance(body.get("provider"), str) else DEFAULT_MODEL_PROVIDER
        model = body.get("model") if isinstance(body.get("model"), str) else DEFAULT_MODEL_NAME
        return ModelResponse(output=_loads_json_object(content), model_name=model, provider=provider)


class UnsupportedProviderModelClient(ModelClient):
    def __init__(self, provider: str, model: str) -> None:
        self.provider = provider
        self.model = model

    def complete_json(self, *, system_prompt: str, payload: dict[str, Any], timeout_seconds: float) -> ModelResponse:
        raise AgentRuntimeError(f"Provider {self.provider!r} is configured but not linked for model calls yet.")


def build_model_client(
    *,
    gateway_url: str = "http://localhost:9000",
) -> ModelClient:
    return AiBackendModelClient(gateway_url=gateway_url)


scheduling_agent_definition = AgentDefinition(
    name="meeting_resolution_agent",
    framework=NATIVE_AI_RUNTIME,
    role="Resolve meeting clashes and scheduling tradeoffs for executive assistants with repo-owned tool calls.",
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
            description="Applies backend V0 guardrail policy to the tool outputs.",
        ),
    ],
)


request_parser_agent_definition = AgentDefinition(
    name="meeting_request_parser_agent",
    framework=NATIVE_AI_RUNTIME,
    role="Extract structured meeting intent, entities, and time preferences from raw scheduling requests.",
    objective=(
        "Produce a strict ParsedMeetingRequest JSON object from raw intake text while preserving people, "
        "accounts, requester, priority, meeting type, preferred windows, sensitivity, missing fields, "
        "and scheduling constraints."
    ),
    planning_goal="Ground model parsing with backend entity and time-evidence tools before schema validation.",
    tools=[
        AgentToolDefinition(
            name="extract_meeting_entities",
            goal="Identify people, requester, account or company names, attendees, and meeting-type evidence.",
            description="Uses backend entity extraction before the parser commits to schema labels.",
        ),
        AgentToolDefinition(
            name="extract_time_preferences",
            goal="Identify weekday, relative-date, and day-part preferred windows.",
            description="Converts phrasing like Tuesday afternoon or next week morning into TimeWindow payloads.",
        ),
    ],
)


draft_agent_definition = AgentDefinition(
    name="meeting_draft_agent",
    framework=NATIVE_AI_RUNTIME,
    role="Draft human-reviewable meeting replies from scheduling recommendations using the configured model.",
    objective=(
        "Generate a concise DraftResponse JSON object that reflects the recommendation decision, "
        "safe action, risk posture, and available slots without leaking sensitive context."
    ),
    planning_goal="Start from the guarded backend draft, then only improve wording while preserving safety fields.",
    tools=[
        AgentToolDefinition(
            name="compose_guarded_draft",
            goal="Create a safe baseline draft that matches the recommendation decision.",
            description="Returns DraftResponse-shaped JSON for schedule, clarify, defer, and decline decisions.",
        )
    ],
)


PARSER_INSTRUCTION = (
    "Return only one minified JSON object matching ParsedMeetingRequest. Use the supplied entity_evidence and "
    "time_evidence. Do not invent attendees, times, authorization, or prose. Arrays must be arrays, never null. "
    "Valid priority values are low, normal, high, urgent. Valid meeting_type values are intro, internal, customer, "
    "investor, candidate, vendor, partner, board, legal_hr, personal, other. Valid sensitivity values are low, "
    "medium, high."
)

SCHEDULING_INSTRUCTION = (
    "Return only JSON matching the scheduling plan fields. You may improve confidence and rationale, but the backend "
    "will preserve backend decision, risk_level, safe_action, and slot guardrails. Do not write calendars, send "
    "email, or propose external actions."
)

DRAFT_INSTRUCTION = (
    "Return only JSON matching DraftResponse. Preserve draft_type and model_status from the guarded draft unless the "
    "body wording improves clarity without changing the scheduling decision. Do not expose sensitive details."
)


def local_model_name() -> str:
    return DEFAULT_MODEL_NAME


def default_model_name() -> str:
    return DEFAULT_MODEL_NAME


class NativeRequestParserAgentRunner:
    def __init__(
        self,
        gateway_url: str = "http://localhost:9000",
        timeout_seconds: float = 45.0,
        model_client: ModelClient | None = None,
    ) -> None:
        self.gateway_url = gateway_url
        self.timeout_seconds = timeout_seconds
        self.model_client = model_client or build_model_client(gateway_url=gateway_url)

    def parse(self, raw_text: str) -> ParsedMeetingRequest:
        parsed, _trace = self.parse_with_trace(raw_text)
        return parsed

    def parse_with_trace(self, raw_text: str) -> tuple[ParsedMeetingRequest, dict]:
        entity_evidence = extract_meeting_entities(raw_text)
        time_evidence = extract_time_preferences(raw_text)
        tool_calls = ["extract_meeting_entities", "extract_time_preferences"]
        try:
            response = self.model_client.complete_json(
                system_prompt=PARSER_INSTRUCTION,
                payload={
                    "task": "Parse this raw scheduling request.",
                    "raw_text": raw_text,
                    "entity_evidence": entity_evidence,
                    "time_evidence": time_evidence,
                },
                timeout_seconds=self.timeout_seconds,
            )
            parsed = ParsedMeetingRequest.model_validate(_coerce_parsed_request_output(raw_text, response.output))
            trace = _native_trace(
                request_parser_agent_definition.name,
                "used",
                tool_calls,
                model=response.model_name,
                provider=response.provider,
            )
            return parsed, trace
        except (AgentRuntimeError, ValidationError) as exc:
            raise AgentRuntimeError("Native request parser could not complete.") from exc


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


class NativeSchedulingAgentRunner:
    def __init__(
        self,
        gateway_url: str = "http://localhost:9000",
        timeout_seconds: float = 45.0,
        model_client: ModelClient | None = None,
    ) -> None:
        self.gateway_url = gateway_url
        self.timeout_seconds = timeout_seconds
        self.model_client = model_client or build_model_client(gateway_url=gateway_url)

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
            response = self.model_client.complete_json(
                system_prompt=SCHEDULING_INSTRUCTION,
                payload={
                    "task": "Improve the explanation for this guarded scheduling plan.",
                    "parsed_request": parsed_request.model_dump(mode="json"),
                    "rules": rules.model_dump(mode="json"),
                    "calendar_blocks": [block.model_dump(mode="json") for block in calendar_blocks],
                    "tool_plan": deterministic_plan.model_dump(mode="json"),
                },
                timeout_seconds=self.timeout_seconds,
            )
            plan = self._merge_model_output(response.output, deterministic_plan)
            return plan, _native_trace(
                scheduling_agent_definition.name,
                "used",
                [call.tool_name for call in deterministic_plan.tool_calls],
                model=response.model_name,
                provider=response.provider,
            )
        except (AgentRuntimeError, ValidationError) as exc:
            raise AgentRuntimeError("Native scheduling agent could not complete.") from exc

    def _merge_model_output(self, output: dict, deterministic_plan: AgentPlanningResult) -> AgentPlanningResult:
        decision = output.get("decision") if output.get("decision") == deterministic_plan.decision else deterministic_plan.decision
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


class NativeDraftAgentRunner:
    def __init__(
        self,
        gateway_url: str = "http://localhost:9000",
        timeout_seconds: float = 45.0,
        model_client: ModelClient | None = None,
    ) -> None:
        self.gateway_url = gateway_url
        self.timeout_seconds = timeout_seconds
        self.model_client = model_client or build_model_client(gateway_url=gateway_url)

    def generate(self, recommendation: Recommendation) -> DraftResponse:
        draft, _trace = self.generate_with_trace(recommendation)
        return draft

    def generate_with_trace(self, recommendation: Recommendation) -> tuple[DraftResponse, dict]:
        guarded = deterministic_draft_response(recommendation, "used")
        try:
            response = self.model_client.complete_json(
                system_prompt=DRAFT_INSTRUCTION,
                payload={
                    "task": "Improve this safe draft response without changing its decision semantics.",
                    "recommendation": recommendation.model_dump(mode="json"),
                    "guarded_draft": guarded.model_dump(mode="json"),
                },
                timeout_seconds=self.timeout_seconds,
            )
            draft = DraftResponse.model_validate(response.output)
            return draft, _native_trace(
                draft_agent_definition.name,
                "used",
                ["compose_guarded_draft"],
                model=response.model_name,
                provider=response.provider,
            )
        except (AgentRuntimeError, ValidationError) as exc:
            raise AgentRuntimeError("Native draft agent could not complete.") from exc


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


def resolve_scheduling_plan(payload_id_or_json: str) -> dict:
    payload = _loads_json_object(payload_id_or_json)
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
    analysis = CalendarAnalyzer().analyze(request_windows, calendar_blocks, duration_minutes)
    return analysis.model_dump(mode="json")


def inspect_calendar_conflicts(
    request_windows_json: str,
    calendar_blocks_json: str,
    duration_minutes: int,
) -> dict:
    windows = [TimeWindow.model_validate(window) for window in _loads_json_array(request_windows_json)]
    blocks = [CalendarBlock.model_validate(block) for block in _loads_json_array(calendar_blocks_json)]
    return inspect_calendar_conflicts_tool(windows, blocks, duration_minutes)


def validate_scheduling_rules_tool(rules: ExecutiveRules) -> dict:
    violations = RulesEngine().validate(rules)
    return {"violations": [violation.model_dump(mode="json") for violation in violations]}


def validate_scheduling_rules(rules_json: str) -> dict:
    return validate_scheduling_rules_tool(ExecutiveRules.model_validate(_loads_json_object(rules_json)))


def classify_priority_and_risk_tool(parsed_request: ParsedMeetingRequest, analysis: CalendarAnalysis) -> dict:
    risks = RiskClassifier().classify(parsed_request, analysis)
    return {"risks": [risk.model_dump(mode="json") for risk in risks]}


def classify_priority_and_risk(parsed_request_json: str, analysis_json: str, rule_violations_json: str) -> dict:
    request = ParsedMeetingRequest.model_validate(_loads_json_object(parsed_request_json))
    calendar_analysis = CalendarAnalysis.model_validate(_loads_json_object(analysis_json))
    rule_violations = _loads_json_array(rule_violations_json)
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
    return {"risks": [risk.model_dump(mode="json") for risk in risks], "risk_level": _risk_level(risks, request)}


def select_resolution_strategy_tool(parsed_request: ParsedMeetingRequest, analysis: CalendarAnalysis) -> dict:
    decision = _decision(parsed_request, analysis)
    return {
        "decision": decision,
        "confidence": _confidence(decision, analysis),
        "rationale": _rationale(parsed_request, analysis),
        "safe_action": _safe_action(parsed_request, decision),
    }


def select_resolution_strategy(parsed_request_json: str, analysis_json: str, risks_json: str) -> dict:
    request = ParsedMeetingRequest.model_validate(_loads_json_object(parsed_request_json))
    calendar_analysis = CalendarAnalysis.model_validate(_loads_json_object(analysis_json))
    risks = [Risk.model_validate(risk) for risk in _loads_json_array(risks_json)]
    decision = _decision(request, calendar_analysis)
    return {
        "decision": decision,
        "confidence": _confidence(decision, calendar_analysis),
        "rationale": _rationale(request, calendar_analysis),
        "risks": [risk.model_dump(mode="json") for risk in risks],
        "risk_level": _risk_level(risks, request),
        "safe_action": _safe_action(request, decision),
        "proposed_slots": [slot.model_dump(mode="json") for slot in calendar_analysis.open_slots[:3]]
        if decision == "schedule"
        else [],
    }


def extract_meeting_entities(raw_text: str) -> dict:
    from app.services.request_parser import extract_entity_evidence

    return extract_entity_evidence(raw_text)


def extract_time_preferences(raw_text: str) -> dict:
    from app.services.request_parser import extract_time_preference_evidence

    return extract_time_preference_evidence(raw_text)


def compose_guarded_draft(recommendation_json: str) -> dict:
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


def _native_trace(
    agent_name: str,
    status: str,
    tool_calls: list[str],
    model: str | None = None,
    provider: str | None = None,
) -> dict:
    return {
        "runtime": NATIVE_AI_RUNTIME,
        "agent_name": agent_name,
        "model_status": status,
        "model": model,
        "provider": provider,
        "tool_calls": tool_calls,
    }


def _coerce_parsed_request_output(raw_text: str, output: dict) -> dict:
    if not isinstance(output, dict):
        return output

    intent = output.get("intent") if isinstance(output.get("intent"), dict) else {}
    meeting_request = output.get("meeting_request") if isinstance(output.get("meeting_request"), dict) else {}

    if not intent and not meeting_request:
        return output

    missing_fields = _string_list(intent.get("missing_fields"))
    requester = _string_value(intent.get("requester") or meeting_request.get("requester"), "Unknown requester")
    if requester == "Unknown requester" and "requester" not in missing_fields:
        missing_fields.append("requester")

    coerced_intent = {
        "title": _string_value(intent.get("title") or meeting_request.get("subject"), "Meeting request"),
        "requester": requester,
        "duration_minutes": _duration_minutes_value(intent.get("duration_minutes") or meeting_request.get("duration"), 30),
        "priority": _enum_value(intent.get("priority"), {"low", "normal", "high", "urgent"}, "normal"),
        "meeting_type": _enum_value(
            intent.get("meeting_type"),
            {"intro", "internal", "customer", "investor", "candidate", "vendor", "partner", "board", "legal_hr", "personal", "other"},
            "other",
        ),
        "attendees": _string_list(intent.get("attendees") or meeting_request.get("attendees")),
        "preferred_windows": _time_window_list(intent.get("preferred_windows")),
        "constraints": _string_list(intent.get("constraints")),
        "missing_fields": missing_fields,
        "sensitivity": _enum_value(intent.get("sensitivity"), {"low", "medium", "high"}, "low"),
    }
    for key in ("async_candidate", "escalation_required"):
        if isinstance(intent.get(key), bool):
            coerced_intent[key] = intent[key]
    return {"raw_text": _string_value(output.get("raw_text"), raw_text), "intent": coerced_intent}


def _string_value(value, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _enum_value(value, allowed: set[str], default: str) -> str:
    if not isinstance(value, str):
        return default
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    if normalized == "medium" and default == "normal":
        return "normal"
    return normalized if normalized in allowed else default


def _duration_minutes_value(value, default: int) -> int:
    if isinstance(value, int):
        return max(15, min(240, value))
    if isinstance(value, str):
        match = re.search(r"\d{1,3}", value)
        if match:
            return max(15, min(240, int(match.group(0))))
    return default


def _time_window_list(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    windows = []
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("start"), str) and isinstance(item.get("end"), str):
            windows.append({"start": item["start"], "end": item["end"]})
    return windows


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
            raise AgentRuntimeError("Native agent returned non-JSON output.") from exc
        value = json.loads(stripped[start : end + 1])
    if not isinstance(value, dict):
        raise AgentRuntimeError("Native agent returned a non-object JSON payload.")
    return value


def _loads_json_array(text: str) -> list:
    value = json.loads(text)
    if not isinstance(value, list):
        raise AgentRuntimeError("Native tool expected a JSON array payload.")
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
        return [f"Found {len(analysis.open_slots)} viable slot(s) for a {parsed_request.intent.duration_minutes}-minute meeting."]
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
