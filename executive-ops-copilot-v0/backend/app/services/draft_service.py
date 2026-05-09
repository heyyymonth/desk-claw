from app.core.errors import ServiceError
from app.llm.output_parser import InvalidLLMOutput, parse_llm_output
from app.llm.prompts import draft_prompt
from app.llm.schemas import DraftResponse, Recommendation


class DraftService:
    def __init__(self, llm) -> None:
        self.llm = llm

    def generate(self, recommendation: Recommendation) -> DraftResponse:
        if self.llm:
            output = self.llm.generate_structured(draft_prompt(recommendation.model_dump(mode="json")), DraftResponse)
            try:
                draft = parse_llm_output(output, DraftResponse)
            except InvalidLLMOutput as exc:
                raise ServiceError("ollama_invalid_output", "Gemma returned invalid draft output.", status_code=502) from exc
            return self._guard_draft(recommendation, draft)

        return self._deterministic_draft(recommendation, "not_configured")

    def _guard_draft(self, recommendation: Recommendation, draft: DraftResponse) -> DraftResponse:
        if recommendation.decision != "schedule":
            return self._deterministic_draft(recommendation, "used")
        if not recommendation.proposed_slots:
            return DraftResponse(
                subject="Meeting request",
                body="Thanks for reaching out. We need to review the request before proposing a time.",
                tone="concise",
                draft_type="defer",
                model_status="used",
            )
        if draft.draft_type != "accept":
            return draft.model_copy(update={"draft_type": "accept"})
        return draft

    def _deterministic_draft(self, recommendation: Recommendation, model_status: str) -> DraftResponse:
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
