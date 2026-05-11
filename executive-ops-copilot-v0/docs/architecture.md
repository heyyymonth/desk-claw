# Architecture

## System Shape

- Frontend: local React, TypeScript, Vite web app.
- Backend: local FastAPI service with Pydantic models aligned to `/contracts`.
- Model runtime: Google ADK agent runners owned by the backend, model-agnostic through `ADK_MODEL` and defaulting to local Ollama `ollama_chat/gemma4:latest`.
- Storage: local SQLite for actor records, AI audit logs, decision feedback, and decision logs.
- Contracts: OpenAPI and JSON Schema under `/contracts`.
- Evals: local cases under `/evals/cases` and an API trigger for V0 eval runs.

## Boundary Rules

- The frontend calls FastAPI only.
- The frontend does not call Ollama, SQLite, or filesystem resources directly.
- FastAPI owns orchestration, validation, rule application, ADK model calls, and persistence.
- No parse, recommendation, or draft model call is made outside Google ADK. Health checks report configuration only; model availability is observed through ADK telemetry.
- Route handlers stay thin and delegate business behavior to services.
- Deterministic policy checks and model-generated text are separate service boundaries.
- Raw LLM output is validated into contract-shaped models before it can cross the API boundary.
- All persisted records use backend-generated IDs and timestamps.
- AI workflow calls are audited with actor context, endpoint, operation, ADK model, model status, runtime, agent name, tool calls, request payload, response payload or error, status, and latency.

## Backend Responsibilities

- Parse `MeetingRequestRaw` into `ParsedMeetingRequest`.
- Load and update the single `ExecutiveRulesProfile`.
- Load and create local `CalendarBlock` records.
- Generate `Recommendation` records from parsed request, rules, and calendar context.
- Generate `DraftResponse` records from recommendation context.
- Accept `DecisionFeedback` and write `DecisionLogEntry` records.
- Persist AI request/response audit records for parse, recommendation, and draft operations.
- Expose decoupled AI technical telemetry derived only from stored audit events without coupling dashboard logic to the scheduling workflow.
- Run local eval cases and return summarized results.

## Frontend Responsibilities

- Provide paste-based request intake.
- Render parsed meeting details with missing fields.
- Render recommendation action, confidence, risk, rationale, and proposed slots.
- Render editable draft response text.
- Capture final user feedback and notes.
- Display decision log entries returned by the backend.
- Render the AI Technical Dashboard as a separate page backed by `GET /api/telemetry/ai/dashboard`; it must not compute metrics from in-memory workflow state.
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
11. Admin/development audit inspection can retrieve AI audit records with `GET /api/audit/ai`.
12. The decoupled technical telemetry dashboard can retrieve aggregate quality, latency, tool, and insight metrics with `GET /api/telemetry/ai/dashboard`.

## Data Ownership

- `request_id` is created when parsing succeeds.
- `recommendation_id` is created when a recommendation is generated.
- `draft_id` is created when a draft is generated.
- `decision_id` is created when feedback is logged.
- The backend is the source of truth for generated IDs and `created_at` timestamps.
- `actor_id` defaults to `local-user` and can be supplied with `X-Actor-Id`; `X-Actor-Email` and `X-Actor-Name` are persisted when present.
- AI audit entries are append-only records in `ai_audit_log`.
- AI telemetry metrics are derived read models. The telemetry service reads persisted `ai_audit_log` rows and does not receive workflow objects directly.

## Telemetry Extension Pattern

- Workflow services emit AI telemetry only by writing audit events during parse, recommendation, and draft operations.
- `AuditRepository` owns persistence and raw event retrieval.
- `TelemetryService` is read-only and builds dashboard views from stored events.
- `app.telemetry.ai_quality` owns quality aggregation, tool reliability, failure reasoning, and eval-like insight generation.
- Frontend dashboard code lives separately from scheduling workflow panels and fetches only the telemetry API.
- Future providers, model families, tools, or eval dimensions should add event fields or derived telemetry adapters without coupling the dashboard to live workflow state.

## Failure States

- Invalid request payload: `400` or framework-level validation error with `ErrorResponse`.
- Unknown ID reference: `404` with `ErrorResponse.code=not_found`.
- Invalid state transition: `409` with `ErrorResponse.code=conflict`.
- Invalid model output: response uses `model_status=invalid_output` and either a deterministic fallback or `502`.
- Configured ADK model unavailable: response uses `model_status=unavailable` and deterministic fallback where possible.
- Persistence failure: `500` with `ErrorResponse.code=persistence_error`.

## Future Auth Room

V0 has no enterprise auth. API contracts reserve optional `actor_id` fields and allow future authentication headers without changing core payload models.
