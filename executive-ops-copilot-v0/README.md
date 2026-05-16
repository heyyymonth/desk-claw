# Agentic Request Parser

A lightweight agentic request parser that converts incoming scheduling or operational text into structured intent and recommended next steps.

## What It Does

- Accepts raw request text from the frontend or API.
- Parses the request into structured intent.
- Runs a small agentic scheduling planner over default rules and request context.
- Returns parsed intent, a recommendation, recommended next steps, and a human-reviewable draft response.
- Keeps model calls behind FastAPI. The frontend never calls an LLM provider directly.

## Architecture Overview

```text
React frontend
  -> FastAPI API layer
  -> request validation
  -> RequestParser service
  -> native agent runners and deterministic tools
  -> RecommendationService
  -> DraftService
  -> structured JSON response
```

The services stay decoupled:

- `frontend/`: single request-entry UI.
- `backend/app/api/`: HTTP routes and request/response wiring.
- `backend/app/services/`: parser, recommendation, draft, rules, calendar analysis, risk classification, model warmup.
- `backend/app/agents/`: native agent definitions, model client adapters, and deterministic tool orchestration.
- `backend/app/llm/schemas.py`: shared backend response schemas.

## Request/Response Flow

1. User enters incoming request text.
2. Frontend calls `POST /api/parse-request`.
3. FastAPI validates the payload.
4. `RequestParser` extracts structured intent.
5. `RecommendationService` runs the planner and returns the recommended action.
6. `DraftService` creates a short draft response.
7. FastAPI returns one structured JSON payload to the frontend.

## Local Setup

Backend:

```bash
cd executive-ops-copilot-v0/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd executive-ops-copilot-v0/frontend
npm install
npm run dev
```

Or start both:

```bash
cd executive-ops-copilot-v0
./scripts/start-local.sh
```

## Environment Variables

Backend:

- `AI_PROVIDER`: `openai`, `anthropic`, `gemini`, or `mock`. Only `openai` and deterministic `mock` are currently wired for runtime behavior.
- `AI_MODEL`: model name used by the native agent runner.
- `AI_API_ENDPOINT`: provider endpoint override.
- `OPENAI_API_KEY`: required only when `AI_PROVIDER=openai`.
- `AGENT_RUNTIME`: defaults to `native`; set `mock` provider for deterministic local behavior.
- `AI_AGENT_TIMEOUT_SECONDS`: model request timeout.
- `WARM_MODEL_ON_STARTUP`: set `true` to warm the configured model at startup.
- `CORS_ALLOWED_ORIGINS`: comma-separated frontend origins.

Frontend:

- `VITE_API_BASE_URL`: backend base URL. Leave empty in the Docker image when frontend and backend are routed together.

## API Endpoints

### `GET /api/health`

Returns backend status and configured model metadata.

### `POST /api/parse-request`

Request:

```json
{
  "raw_text": "From Jordan at Atlas Finance: can Dana meet for 30 minutes next Tuesday afternoon?"
}
```

Response:

```json
{
  "parsed_request": {
    "raw_text": "From Jordan at Atlas Finance: can Dana meet for 30 minutes next Tuesday afternoon?",
    "intent": {
      "title": "Meeting with Atlas Finance",
      "requester": "Jordan",
      "duration_minutes": 30,
      "priority": "normal",
      "meeting_type": "customer",
      "attendees": ["Jordan", "Dana"],
      "preferred_windows": [],
      "constraints": [],
      "missing_fields": [],
      "sensitivity": "low",
      "async_candidate": false,
      "escalation_required": false
    }
  },
  "recommendation": {
    "decision": "clarify",
    "confidence": 0.65,
    "rationale": ["No confirmed open slot was available."],
    "risks": [],
    "risk_level": "low",
    "safe_action": "ask_for_missing_context",
    "proposed_slots": [],
    "model_status": "not_configured"
  },
  "draft_response": {
    "subject": "Meeting request",
    "body": "Thanks for reaching out. We need a bit more information before proposing a time.",
    "tone": "concise",
    "draft_type": "clarify",
    "model_status": "not_configured"
  },
  "next_steps": ["Ask for missing context"]
}
```

## Deployment Notes

- Use `docker-compose.yml` for the simplest two-service deployment.
- The backend exposes only `/api/health` and `/api/parse-request` for the runtime app.
- Set `OPENAI_API_KEY` only on the backend service.
- Keep the frontend static; it should only know the backend URL.
- Start with `AI_PROVIDER=mock` for deterministic smoke tests, then switch to `openai` when the backend secret is configured.

## Development Notes

Run backend tests:

```bash
cd executive-ops-copilot-v0/backend
python3 -m pytest
```

Run frontend tests and build:

```bash
cd executive-ops-copilot-v0/frontend
npm test
npm run build
```
