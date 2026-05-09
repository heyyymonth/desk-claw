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
                return parse_llm_output(output, DraftResponse)
            except InvalidLLMOutput as exc:
                raise ServiceError("ollama_invalid_output", "Gemma returned invalid draft output.", status_code=502) from exc

        if recommendation.decision == "schedule" and recommendation.proposed_slots:
            slot = recommendation.proposed_slots[0]
            return DraftResponse(
                subject="Meeting time available",
                body=f"We can meet at {slot.start.strftime('%A at %I:%M %p')}. Please confirm whether that works.",
                tone="warm",
                draft_type="accept",
                model_status="not_configured",
            )
        if recommendation.decision == "decline":
            return DraftResponse(
                subject="Meeting request",
                body="Thanks for reaching out. We are not able to prioritize this meeting right now.",
                tone="firm",
                draft_type="decline",
                model_status="not_configured",
            )
        if recommendation.decision == "defer":
            return DraftResponse(
                subject="Meeting request",
                body="Thanks for reaching out. We need to review availability and priority before proposing a time.",
                tone="concise",
                draft_type="defer",
                model_status="not_configured",
            )
        return DraftResponse(
            subject="Meeting request",
            body="Thanks for reaching out. We need a bit more information before proposing a time.",
            tone="concise",
            draft_type="clarify",
            model_status="not_configured",
        )
