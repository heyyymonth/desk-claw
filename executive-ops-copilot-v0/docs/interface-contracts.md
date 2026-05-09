# Interface Contracts

The contracts in `/contracts` are the source of truth for data exchanged between frontend and backend.

## Contract Files

- `contracts/schemas/meeting_request.schema.json`
  - `MeetingRequestRaw`
  - `ParsedMeetingRequest`
  - `CalendarBlock`
- `contracts/schemas/common.schema.json`
  - `ErrorResponse`
- `contracts/schemas/executive_rules.schema.json`
  - `ExecutiveRulesProfile`
- `contracts/schemas/recommendation.schema.json`
  - `Recommendation`
  - `DecisionFeedback`
  - `DecisionLogEntry`
- `contracts/schemas/draft_response.schema.json`
  - `DraftResponse`
- `contracts/openapi/openapi.yaml`
  - API operations, request bodies, response bodies, errors, and examples.

## Required Endpoints

- `POST /api/requests/parse`
- `POST /api/recommendations/generate`
- `POST /api/drafts/generate`
- `GET /api/rules`
- `PUT /api/rules`
- `GET /api/calendar/blocks`
- `POST /api/calendar/blocks`
- `POST /api/feedback`
- `GET /api/decisions`
- `POST /api/evals/run`

## Shared Enums

- `meeting_type`: `intro`, `internal`, `customer`, `investor`, `candidate`, `vendor`, `board`, `personal`, `other`
- `urgency`: `low`, `normal`, `high`, `urgent`
- `importance`: `low`, `medium`, `high`, `critical`
- `risk_level`: `none`, `low`, `medium`, `high`
- `recommended_action`: `accept`, `decline`, `propose_times`, `ask_clarifying_question`, `defer`
- `draft_type`: `accept`, `decline`, `clarify`, `defer`
- `model_status`: `not_used`, `used`, `unavailable`, `invalid_output`
- `sensitivity`: `normal`, `confidential`, `restricted`

## Compatibility Rules

- Additive optional fields are allowed only after schemas and OpenAPI are updated.
- Removing, renaming, or changing enum values requires a documented migration.
- Frontend types should be generated from OpenAPI or manually matched to the schema files.
- Backend models must reject invalid enum values and malformed dates.
- Timestamps are ISO 8601 strings with timezone offsets.
- API error responses use the shared `ErrorResponse` shape.
- Raw model output is never returned directly to the frontend.

## Fixture Examples

- `meeting_request_raw.example.json`
- `parsed_meeting_request.example.json`
- `executive_rules_profile.example.json`
- `calendar_block.example.json`
- `recommendation.example.json`
- `draft_response.example.json`
- `decision_feedback.example.json`
- `decision_log_entry.example.json`
- `error_response.example.json`

Backend and frontend agents can use these as fixtures while implementation catches up to the contracts.
