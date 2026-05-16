# Agentic Request Parser

A lightweight scheduling workbench that parses incoming request text, applies scheduling guardrails, and returns a human-reviewable recommendation and draft.

## Architecture

```text
Frontend
  -> Web Backend
  -> AI Backend
  -> Provider Adapter
  -> Ollama/OpenAI/Anthropic/Gemini
```

The services are separate runtime processes with separate Docker build contexts and images:

- `frontend/`: Vite/React UI served by nginx.
- `web_backend/`: FastAPI product API, scheduling workflow, validation, guardrails, and response shaping.
- `ai_backend/`: FastAPI model gateway with provider adapters, provider health, routing, fallback, timeouts, and normalized AI responses.

| Service | Owns | Does not own |
| --- | --- | --- |
| Frontend | UI and calls to Web Backend | Model calls, provider keys, AI routing |
| Web Backend | Product APIs and business workflow | Provider keys, provider base URLs, provider request formats |
| AI Backend | Provider integrations and model routing | Product UI or scheduling business rules |

## Local Setup

Create env from the placeholder example:

```bash
cp .env.example .env
```

Run all services with Docker:

```bash
docker compose build
docker compose up
```

Default local ports:

- Frontend: `http://localhost:3000`
- Web Backend: `http://localhost:8000`
- AI Backend: `http://localhost:9000`

Run locally without Docker:

```bash
./scripts/start-local.sh
```

## Environment

Frontend uses only the Web Backend URL. Web Backend uses only:

```bash
AI_BACKEND_URL=http://localhost:9000
```

Provider keys and provider base URLs belong only to AI Backend:

```bash
DEFAULT_AI_PROVIDER=ollama
FALLBACK_AI_PROVIDER=openai
OLLAMA_API_KEY=replace_me
OPENAI_API_KEY=replace_me
ANTHROPIC_API_KEY=replace_me
GEMINI_API_KEY=replace_me
```

Switch the default provider by changing `DEFAULT_AI_PROVIDER`. Provider-specific model names are configured with `OLLAMA_DEFAULT_MODEL`, `OPENAI_DEFAULT_MODEL`, `ANTHROPIC_DEFAULT_MODEL`, and `GEMINI_DEFAULT_MODEL`.

## API Checks

Web Backend:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/health
curl http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Explain this architecture simply."}'
```

AI Backend:

```bash
curl http://localhost:9000/health
curl http://localhost:9000/health/providers
curl http://localhost:9000/health/ollama
curl http://localhost:9000/health/openai
curl http://localhost:9000/health/anthropic
curl http://localhost:9000/health/gemini
```

Model-agnostic chat:

```bash
curl http://localhost:9000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "ollama",
    "messages": [{"role": "user", "content": "Explain service separation simply."}],
    "temperature": 0.2,
    "max_tokens": 1000,
    "stream": false
  }'
```

Provider test routes:

```bash
curl http://localhost:9000/test/ollama/chat -H "Content-Type: application/json" -d '{"message":"Say hello from Ollama Cloud"}'
curl http://localhost:9000/test/openai/chat -H "Content-Type: application/json" -d '{"message":"Say hello from OpenAI"}'
curl http://localhost:9000/test/anthropic/chat -H "Content-Type: application/json" -d '{"message":"Say hello from Anthropic"}'
curl http://localhost:9000/test/gemini/chat -H "Content-Type: application/json" -d '{"message":"Say hello from Gemini"}'
```

## Development

```bash
make test-web-backend
make test-ai-backend
make test-frontend
make test-all
make build-all
make health
make health-providers
```

Direct commands:

```bash
cd web_backend && python3 -m pytest
cd ai_backend && python3 -m pytest
cd frontend && npm test -- --run && npm run build
docker compose config
```

## Adding A Provider

Add a provider config entry in `ai_backend/config.py`, implement `ModelProvider` in `ai_backend/providers/`, register it in `ai_backend/main.py`, and add router/provider tests. Do not add provider keys, SDKs, or provider HTTP formats to `frontend/` or `web_backend/`.
