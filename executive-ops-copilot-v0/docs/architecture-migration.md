# Architecture Migration

## Existing Flow

```text
Frontend -> FastAPI backend -> native agent runners -> provider HTTP call
```

The frontend already calls the backend only. The old backend owned both product orchestration and provider configuration, including model endpoints and `OPENAI_API_KEY`.

## Target Flow

```text
Frontend -> Web Backend -> AI Backend -> Provider Adapter -> Ollama/OpenAI/Anthropic/Gemini
```

The Web Backend owns product APIs, scheduling validation, guardrails, and response shaping. The AI Backend owns provider keys, provider base URLs, routing, fallback, health checks, and normalized model responses.

## Files Split

- `backend/` moved to `web_backend/`.
- Provider-specific HTTP logic was removed from Web Backend agent code and replaced with an AI Backend client.
- New AI Backend service added under `ai_backend/`.
- Docker Compose now builds `frontend`, `web-backend`, and `ai-backend` as separate images.

## Env Ownership

- Frontend: Web Backend public URL only.
- Web Backend: `AI_BACKEND_URL` only for model access.
- AI Backend: all provider keys, provider base URLs, default provider, fallback provider, and default models.

## Tests Added Or Updated

- Web Backend tests cover `/health`, `/api/health`, `/api/chat`, provider-key independence, AI Backend failure handling, and static provider-secret separation.
- AI Backend tests cover provider config, request mapping, response normalization, router fallback, unsupported streaming, and secret redaction.
- Infra validation uses `docker compose config` and Makefile targets.
