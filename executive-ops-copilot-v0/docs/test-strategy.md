# Test Strategy

## Unit

Backend unit tests cover ADK agent wiring, deterministic fallback behavior, request parsing fallback, rules, calendar slot analysis, recommendations, draft responses, and decision-log persistence.

Frontend unit and component tests should cover API-client error handling, local workflow state transitions, editable rule/draft controls, and rendering of risk, rationale, calendar impact, and decision-log entries.

## Contract

Contract tests validate the FastAPI endpoints against the Pydantic models and OpenAPI examples in `contracts/`. They should protect request and response shape for:

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

## Integration

Backend integration tests run FastAPI through `TestClient` with a test SQLite database. They verify that parse, recommendation, draft, and decision logging work together without real Google, Microsoft, email, Slack, or Ollama services.

Local integration runs should use deterministic test data and mocked LLM behavior. Ollama availability is treated as an external dependency and is not required for CI.

## E2E

Playwright tests in `e2e/tests/v0-workflow.spec.ts` validate the complete V0 browser workflow:

1. Open the local web app.
2. Paste a meeting request.
3. Parse the request.
4. Review structured intent.
5. Confirm executive rules.
6. Confirm seeded mock calendar blocks.
7. Generate a recommendation.
8. Verify risk, rationale, calendar impact, and recommended action.
9. Generate a draft response.
10. Accept or edit the draft.
11. Submit decision feedback.
12. Verify the decision log.

The E2E suite currently covers:

- Vague external request
- Customer escalation
- Investor during board prep
- Internal recurring sync that should be challenged
- Missing context request
- Backend unavailable error state
- Ollama unavailable mocked fallback state

The browser tests intercept `/api/**` and return seeded responses. This keeps the suite deterministic and avoids real calendar accounts, email, Slack, or local Ollama requirements while still exercising the frontend workflow end to end.

## Evals

The backend eval endpoint `POST /api/evals/run` executes `evals/cases/v0_scheduling_cases.yaml` against the local parser, recommender, and draft services, then compares results with `evals/expected/v0_expected_outputs.yaml`.

The same endpoint also runs Google ADK trajectory evaluation for the scheduling agent. The ADK eval checks that the expected tool path is followed:

1. `inspect_calendar_conflicts`
2. `validate_scheduling_rules`
3. `classify_priority_and_risk`
4. `select_resolution_strategy`

Eval labels including `meeting_type`, `draft_type`, sensitivity, and aggregate `risk_level` are first-class V0 contract fields. Async candidacy and escalation requirement remain qualitative eval assertions. The JSON Schema contract test must pass before qualitative eval assertions are trusted.

## Running E2E Locally

From the repo root:

```bash
./scripts/run-e2e.sh
```

Or manually:

```bash
cd frontend
npm install
cd ../e2e
npm install
npm run test:e2e
```

Playwright starts the Vite dev server automatically from `e2e/playwright.config.ts`.
