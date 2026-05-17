from app.agents.scheduling import (
    NATIVE_AI_RUNTIME,
    AgentRuntimeError,
    NativeDraftAgentRunner,
    deterministic_draft_response,
)
from app.core.errors import ServiceError
from app.llm.schemas import DraftResponse, Recommendation


class DraftService:
    def __init__(self, agent_runner: NativeDraftAgentRunner | None = None) -> None:
        self.agent_runner = agent_runner

    def generate(self, recommendation: Recommendation) -> DraftResponse:
        draft, _trace = self.generate_with_trace(recommendation)
        return draft

    def generate_with_trace(self, recommendation: Recommendation) -> tuple[DraftResponse, dict]:
        if self.agent_runner:
            try:
                if hasattr(self.agent_runner, "generate_with_trace"):
                    draft, trace = self.agent_runner.generate_with_trace(recommendation)
                else:
                    draft = self.agent_runner.generate(recommendation)
                    trace = _native_trace("meeting_draft_agent")
            except AgentRuntimeError as exc:
                if exc.model_status == "invalid_output":
                    raise ServiceError(
                        "ai_model_invalid_output",
                        "Configured native draft model returned invalid schema output.",
                        status_code=502,
                        ai_trace=exc.ai_trace,
                    ) from exc
                trace = _native_trace("meeting_draft_agent", status="unavailable")
                raise ServiceError(
                    "ai_model_unavailable",
                    "Configured native draft model is unavailable.",
                    status_code=502,
                    ai_trace=trace,
                ) from exc
            return self._guard_draft(recommendation, draft), trace

        trace = _native_trace("meeting_draft_agent", status="not_configured")
        raise ServiceError(
            "ai_model_not_configured",
            "The model is offline. Check with your admin before running this request.",
            status_code=503,
            ai_trace=trace,
        )

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


def _native_trace(agent_name: str, status: str = "used") -> dict:
    return {"runtime": NATIVE_AI_RUNTIME, "agent_name": agent_name, "model_status": status, "tool_calls": []}
