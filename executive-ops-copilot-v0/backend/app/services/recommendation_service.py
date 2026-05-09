from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.errors import ServiceError
from app.llm.output_parser import InvalidLLMOutput, parse_llm_output
from app.llm.prompts import recommendation_prompt
from app.llm.schemas import CalendarBlock, ExecutiveRules, ParsedMeetingRequest, Recommendation, Risk, TimeWindow
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
    ) -> None:
        self.llm_client = llm_client
        self.calendar_analyzer = calendar_analyzer or CalendarAnalyzer()
        self.risk_classifier = risk_classifier or RiskClassifier()
        self.rules_engine = rules_engine or RulesEngine()

    def generate(
        self,
        parsed_request: ParsedMeetingRequest,
        rules: ExecutiveRules,
        calendar_blocks: list[CalendarBlock],
    ) -> Recommendation:
        windows = parsed_request.intent.preferred_windows or [self._default_window(rules)]
        analysis = self.calendar_analyzer.analyze(windows, calendar_blocks, parsed_request.intent.duration_minutes)
        risks = self.risk_classifier.classify(parsed_request, analysis)
        for violation in self.rules_engine.validate(rules):
            risks.append(Risk(level="medium", message=violation.message))
        if parsed_request.intent.async_candidate:
            risks = []
        if parsed_request.intent.escalation_required:
            risks.append(Risk(level="high", message="Request requires human escalation before any external action."))
        if parsed_request.intent.sensitivity == "high":
            risks.append(Risk(level="high", message="Sensitive request should be reviewed without exposing private details."))
        elif parsed_request.intent.sensitivity == "medium":
            risks.append(Risk(level="medium", message="Request has moderate sensitivity and should be reviewed."))
        if "travel" in parsed_request.intent.constraints:
            risks.append(Risk(level="medium", message="Travel context can affect availability and timezone assumptions."))

        decision = self._decision(parsed_request, analysis)
        deterministic = Recommendation(
            decision=decision,
            confidence=self._confidence(decision, analysis),
            rationale=self._rationale(parsed_request, analysis),
            risks=risks,
            risk_level=self._risk_level(risks, parsed_request),
            safe_action=self._safe_action(parsed_request, decision),
            proposed_slots=analysis.open_slots[:3] if decision == "schedule" else [],
            model_status="not_configured",
        )

        if self.llm_client is None:
            return deterministic

        try:
            output = self.llm_client.generate_structured(
                recommendation_prompt(
                    {
                        "parsed_request": parsed_request.model_dump(mode="json"),
                        "rules": rules.model_dump(mode="json"),
                        "analysis": analysis.model_dump(mode="json"),
                    }
                ),
                Recommendation,
            )
            model_recommendation = parse_llm_output(output, Recommendation)
            return model_recommendation.model_copy(
                update={
                    "decision": deterministic.decision,
                    "risks": deterministic.risks or model_recommendation.risks,
                    "risk_level": deterministic.risk_level,
                    "safe_action": deterministic.safe_action,
                    "proposed_slots": deterministic.proposed_slots,
                    "model_status": "used",
                }
            )
        except InvalidLLMOutput:
            return deterministic.model_copy(update={"model_status": "invalid_output"})
        except ServiceError:
            return deterministic.model_copy(update={"model_status": "unavailable"})

    @staticmethod
    def _decision(parsed_request: ParsedMeetingRequest, analysis) -> str:
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

    @staticmethod
    def _rationale(parsed_request: ParsedMeetingRequest, analysis) -> list[str]:
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

    @staticmethod
    def _confidence(decision: str, analysis) -> float:
        if decision == "schedule":
            return 0.74 if analysis.open_slots else 0.55
        if decision == "clarify":
            return 0.7
        if decision == "decline":
            return 0.68
        return 0.62

    @staticmethod
    def _risk_level(risks: list[Risk], parsed_request: ParsedMeetingRequest | None = None) -> str:
        if parsed_request and parsed_request.intent.async_candidate:
            return "low"
        if any(risk.level == "high" for risk in risks):
            return "high"
        if any(risk.level == "medium" for risk in risks):
            return "medium"
        return "low"

    @staticmethod
    def _safe_action(parsed_request: ParsedMeetingRequest, decision: str) -> str:
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

    @staticmethod
    def _default_window(rules: ExecutiveRules) -> TimeWindow:
        tz = ZoneInfo(rules.timezone)
        tomorrow = datetime.now(tz).date() + timedelta(days=1)
        start = datetime.combine(tomorrow, rules.working_hours.start, tzinfo=tz)
        end = datetime.combine(tomorrow, rules.working_hours.end, tzinfo=tz)
        return TimeWindow(start=start, end=end)
