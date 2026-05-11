from app.agents.scheduling import AdkDraftAgentRunner, AgentRuntimeError, deterministic_draft_response
from app.core.errors import ServiceError
from app.llm.schemas import DraftResponse, Recommendation


class DraftService:
    def __init__(self, llm=None, agent_runner: AdkDraftAgentRunner | None = None) -> None:
        self.agent_runner = agent_runner

    def generate(self, recommendation: Recommendation) -> DraftResponse:
        if self.agent_runner:
            try:
                draft = self.agent_runner.generate(recommendation)
            except AgentRuntimeError as exc:
                raise ServiceError("ollama_unavailable", "Local Gemma4 ADK draft agent is unavailable.", status_code=502) from exc
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
        return deterministic_draft_response(recommendation, model_status)
