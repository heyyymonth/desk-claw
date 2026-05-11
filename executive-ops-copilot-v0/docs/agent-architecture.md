# Scheduling Agent Architecture

## Goal

Improve meeting-conflict reasoning by separating agent planning from response generation. The scheduling agent should decide which tools to call, why each step exists, and what safe human-reviewed action should happen next.

## ADK-Inspired Structure

Google ADK models an agent as a worker with instructions and tools. This repo mirrors that shape in `backend/app/agents/scheduling.py`:

- `meeting_resolution_agent`: root scheduling agent definition.
- `inspect_calendar_conflicts`: finds busy-block conflicts and candidate slots.
- `validate_scheduling_rules`: checks executive rules before action.
- `classify_priority_and_risk`: makes missing-context, sensitivity, escalation, and conflict risk explicit.
- `select_resolution_strategy`: chooses `schedule`, `clarify`, `defer`, or `decline`.

The implementation is deterministic today so V0 remains local and testable. `create_adk_root_agent()` can instantiate a real ADK `Agent` when `google-adk` is installed and model authentication is configured.

## Agent Responsibilities

The scheduling agent does not send email, write to a calendar, or bypass the human decision step. It produces a recommendation plan that is safe for an executive assistant to review.

Planning priorities:

1. Schedule only when a viable slot exists and context is sufficient.
2. Clarify when required context or authorization is missing.
3. Defer sensitive or escalated requests for human review.
4. Decline meetings that can be handled asynchronously.
5. Preserve protected focus blocks and working-hour constraints.

## Repo Integration

`RecommendationService` now calls `SchedulingAgentPlanner.plan()` before optional LLM generation. The deterministic plan supplies:

- decision
- confidence
- rationale
- risks
- risk level
- safe action
- proposed slots
- tool-call trace

The optional LLM still receives calendar analysis, and now also receives the agent plan as context. Deterministic guardrails continue to override model output for decision, rationale, risks, safe action, and slots.

## Next Implementation Steps

1. Add `google-adk` to an optional backend extra once model credentials are ready.
2. Add an `/api/agent-plan` endpoint if the frontend should display tool-call traces directly.
3. Persist the agent plan in audit logs for compliance review.
4. Add eval cases for rescheduling, split-priority conflicts, and protected-block preservation.
