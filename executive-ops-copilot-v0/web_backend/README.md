# Web Backend

FastAPI service for product APIs, scheduling workflow orchestration, validation, guardrails, and frontend response shaping.

The Web Backend calls the AI Backend through `AI_BACKEND_URL`. It must not contain provider API keys, provider base URLs, or direct provider request formats.

Endpoints:

- `GET /health`
- `GET /api/health`
- `POST /api/parse-request`
- `POST /api/chat`
