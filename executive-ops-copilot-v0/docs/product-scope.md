# Executive Operations Scheduling Copilot V0 Scope

## V0 Goal

Build a local web app that helps an executive assistant triage one pasted meeting request at a time. The app parses the request, applies a single executive rules profile and local calendar context, generates a recommendation, drafts a response, captures the assistant's feedback, and logs the final decision.

## Hard Scope

V0 supports this workflow only:

1. User pastes raw meeting request text.
2. Backend parses the text into a frontend-consumable `ParsedMeetingRequest`.
3. Backend applies `ExecutiveRulesProfile` and `CalendarBlock` context.
4. Backend returns a `Recommendation` with action, confidence, risks, rationale, and proposed slots.
5. Backend generates a `DraftResponse` from the parsed request and recommendation.
6. User gives `DecisionFeedback`.
7. Backend writes a `DecisionLogEntry`.

## In Scope

- Manual request intake from pasted text.
- Single local user and one executive rules profile.
- Structured extraction into the contract models in `/contracts/schemas`.
- Local mock calendar blocks managed through the API.
- Recommendation generation with deterministic rule checks and ADK-routed model assistance when configured.
- Draft response generation for accept, decline, clarify, or defer responses.
- Decision feedback capture and local decision log retrieval.
- Contract examples that can be reused as backend, frontend, and eval fixtures.
- Basic eval trigger endpoint for local contract/eval cases.
- Decoupled technical AI telemetry dashboard for ADK coverage, tool-call reliability, latency, and failure insight, rendered from persisted DB events only.

## Out of Scope

- Real calendar reads or writes.
- Email, Slack, Teams, CRM, ATS, travel, or inbox integrations.
- Sending the drafted response.
- Multi-executive support.
- Multi-user collaboration.
- Enterprise auth, SSO, SAML, SCIM, tenant management, billing, audit exports, or RBAC.
- Desktop packaging or mobile app packaging.
- Autonomous scheduling without human confirmation.
- Generic chatbot behavior outside the scheduling workflow.
- Long-term business analytics, reporting dashboards, or model fine-tuning.

## Primary User

An executive assistant who needs to quickly evaluate inbound scheduling requests while preserving executive preferences, calendar constraints, and decision rationale.

## V0 Success Criteria

- Frontend can implement every screen from OpenAPI and JSON Schema without verbal clarification.
- Backend can implement every route and typed model from OpenAPI and JSON Schema without verbal clarification.
- Every API response is frontend-consumable JSON with stable IDs, enums, timestamps, and display-ready rationale.
- Model output is never returned raw; all generation-style model calls go through ADK and are validated against typed backend models before use.
- Invalid model output and unavailable ADK model runtime return explicit status values and structured errors or fallbacks.
- The local app remains usable without external SaaS services.
