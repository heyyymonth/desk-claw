# Architecture

## System Shape

- Frontend: local React, TypeScript, Vite web app.
- Backend: local FastAPI service with Pydantic models aligned to `/contracts`.
- Model runtime: optional local Ollama model accessed only by the backend.
- Storage: local SQLite for rules, calendar blocks, decision feedback, and decision logs.
- Contracts: OpenAPI and JSON Schema under `/contracts`.
- Evals: local cases under `/evals/cases` and an API trigger for V0 eval runs.

## Boundary Rules

- The frontend calls FastAPI only.
- The frontend does not call Ollama, SQLite, or filesystem resources directly.
- FastAPI owns orchestration, validation, rule application, model calls, and persistence.
- Route handlers stay thin and delegate business behavior to services.
- Deterministic policy checks and model-generated text are separate service boundaries.
- Raw LLM output is validated into contract-shaped models before it can cross the API boundary.
- All persisted records use backend-generated IDs and timestamps.

## Backend Responsibilities

- Parse `MeetingRequestRaw` into `ParsedMeetingRequest`.
- Load and update the single `ExecutiveRulesProfile`.
- Load and create local `CalendarBlock` records.
- Generate `Recommendation` records from parsed request, rules, and calendar context.
- Generate `DraftResponse` records from recommendation context.
- Accept `DecisionFeedback` and write `DecisionLogEntry` records.
- Run local eval cases and return summarized results.

## Frontend Responsibilities

- Provide paste-based request intake.
- Render parsed meeting details with missing fields.
- Render recommendation action, confidence, risk, rationale, and proposed slots.
- Render editable draft response text.
- Capture final user feedback and notes.
- Display decision log entries returned by the backend.
- Treat enum values as closed sets for V0.

## V0 Request Flow

1. Frontend sends `POST /api/requests/parse` with `MeetingRequestRaw`.
2. Backend returns `ParsedMeetingRequest`.
3. Frontend requests rules with `GET /api/rules` and calendar blocks with `GET /api/calendar/blocks` as needed.
4. Frontend sends `POST /api/recommendations/generate` with `request_id` and optional rules/calendar overrides.
5. Backend returns `Recommendation`.
6. Frontend sends `POST /api/drafts/generate` with `request_id`, `recommendation_id`, and `draft_type`.
7. Backend returns `DraftResponse`.
8. Frontend sends `POST /api/feedback` with `DecisionFeedback`.
9. Backend writes and returns `DecisionLogEntry`.
10. Frontend can retrieve logs with `GET /api/decisions`.

## Data Ownership

- `request_id` is created when parsing succeeds.
- `recommendation_id` is created when a recommendation is generated.
- `draft_id` is created when a draft is generated.
- `decision_id` is created when feedback is logged.
- The backend is the source of truth for generated IDs and `created_at` timestamps.

## Failure States

- Invalid request payload: `400` or framework-level validation error with `ErrorResponse`.
- Unknown ID reference: `404` with `ErrorResponse.code=not_found`.
- Invalid state transition: `409` with `ErrorResponse.code=conflict`.
- Invalid model output: response uses `model_status=invalid_output` and either a deterministic fallback or `502`.
- Ollama unavailable: response uses `model_status=unavailable` and deterministic fallback where possible.
- Persistence failure: `500` with `ErrorResponse.code=persistence_error`.

## Future Auth Room

V0 has no enterprise auth. API contracts reserve optional `actor_id` fields and allow future authentication headers without changing core payload models.
