# Scheduling Agent Architecture

## Goal

Improve meeting-conflict reasoning by separating agent planning from response generation. The scheduling agent should decide which tools to call, why each step exists, and what safe human-reviewed action should happen next.

## ADK Runtime Structure

Google ADK models an agent as a worker with instructions and tools. This repo now uses that shape as the primary agentic path in `backend/app/agents/scheduling.py`:

- `meeting_resolution_agent`: root scheduling agent definition.
- `inspect_calendar_conflicts`: finds busy-block conflicts and candidate slots.
- `validate_scheduling_rules`: checks executive rules before action.
- `classify_priority_and_risk`: makes missing-context, sensitivity, escalation, and conflict risk explicit.
- `select_resolution_strategy`: chooses `schedule`, `clarify`, `defer`, or `decline`.

`create_adk_root_agent()` returns a real ADK `Agent` with Python function tools. ADK auto-wraps those functions as tool definitions, and `AdkSchedulingAgentRunner` runs the agent through ADK `Runner` and an in-memory session. The backend is pinned to local Ollama `gemma4:latest` through `ADK_MODEL=ollama_chat/gemma4:latest`; other model names are rejected by the agent factory.

The same ADK pattern now covers all AI-facing app workflows:

- `meeting_request_parser_agent` calls `extract_meeting_intent`.
- `meeting_resolution_agent` calls calendar, rules, risk, and strategy tools.
- `meeting_draft_agent` calls `compose_guarded_draft`.

The deterministic `SchedulingAgentPlanner` remains as a fallback. It preserves local tests, protects the API when ADK/model dependencies are unavailable, and supplies guardrails that the ADK result must respect.

ADK runs are bounded to avoid request hangs from local models that loop on tool calls or take too long to respond. If the ADK runner errors or times out, the API returns deterministic local fallback behavior with `model_status="unavailable"` where the API contract has that field.

## Agent Responsibilities

The scheduling agent does not send email, write to a calendar, or bypass the human decision step. It produces a recommendation plan that is safe for an executive assistant to review.

Planning priorities:

1. Schedule only when a viable slot exists and context is sufficient.
2. Clarify when required context or authorization is missing.
3. Defer sensitive or escalated requests for human review.
4. Decline meetings that can be handled asynchronously.
5. Preserve protected focus blocks and working-hour constraints.

## Repo Integration

`RequestParser`, `RecommendationService`, and `DraftService` now attempt their ADK agent runners first when configured. The scheduling ADK agent receives:

- parsed meeting request
- executive rules
- calendar blocks
- tool instructions and output schema requirements

The service returns the ADK plan when it completes. If ADK is unavailable, the service returns the deterministic fallback plan with `model_status="unavailable"` instead of failing the workflow.

Both ADK and fallback plans supply:

- decision
- confidence
- rationale
- risks
- risk level
- safe action
- proposed slots
- tool-call trace

Guardrails continue to override unsafe model output for the final decision, risk level, safe action, and slots. This keeps model reasoning useful without letting it bypass the human-reviewed scheduling contract.

## Next Implementation Steps

1. Add an `/api/agent-plan` endpoint if the frontend should display tool-call traces directly.
2. Persist the agent plan in audit logs for compliance review.
3. Add eval cases for rescheduling, split-priority conflicts, and protected-block preservation.
4. Improve the local Gemma4 prompt/tool payloads if live tool-call latency remains high.
