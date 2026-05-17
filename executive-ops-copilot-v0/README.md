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

## Ollama Cloud Check

Ollama Cloud direct API access is the production path for the AI Backend. Do not mount a local Ollama login into the container and do not install the Ollama CLI in the image. Keep `OLLAMA_API_KEY` in local runtime configuration only; `.env` and `.env.*` are gitignored.

First validate the direct cloud API from the host:

```bash
export OLLAMA_API_KEY="your-local-key"

curl https://ollama.com/api/tags \
  -H "Authorization: Bearer $OLLAMA_API_KEY"

curl https://ollama.com/api/chat \
  -H "Authorization: Bearer $OLLAMA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma4:31b-cloud",
    "messages": [{"role": "user", "content": "Reply with exactly: ollama-cloud-ok"}],
    "stream": false
  }'
```

Then validate the containerized AI Backend:

```bash
OLLAMA_API_KEY="$OLLAMA_API_KEY" \
DEFAULT_AI_PROVIDER=ollama \
FALLBACK_AI_PROVIDER= \
OLLAMA_BASE_URL=https://ollama.com/api \
OLLAMA_DEFAULT_MODEL=gemma4:31b-cloud \
docker compose up -d --build ai-backend

curl http://localhost:9000/health/ollama

curl http://localhost:9000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "ollama",
    "messages": [{"role": "user", "content": "Reply with exactly: ai-backend-ollama-ok"}],
    "temperature": 0.2,
    "max_tokens": 100,
    "stream": false
  }'
```

For a local-account sanity check only, a signed-in host Ollama daemon can be tested outside the containers:

```bash
curl http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma4:31b-cloud",
    "messages": [{"role": "user", "content": "Reply with exactly: ollama-cloud-ok"}],
    "stream": false
  }'
```

## Development

```bash
make lint-all
make test-web-backend
make test-ai-backend
make test-frontend
make test-all
make build-all
make smoke-containers
make health
make health-providers
```

Direct commands:

```bash
cd web_backend && python3 -m ruff check app tests
cd web_backend && python3 -m pytest
cd ai_backend && python3 -m ruff check .
cd ai_backend && python3 -m pytest
cd frontend && npm run lint && npm test -- --run && npm run build
docker compose config
```

## Containers

Each major service has its own Dockerfile and image:

| Service | Build context | Local image | Port |
| --- | --- | --- | --- |
| Frontend | `frontend/` | `app-frontend:local` | `3000 -> 80` |
| Web Backend | `web_backend/` | `app-web-backend:local` | `8000` |
| AI Backend | `ai_backend/` | `app-ai-backend:local` | `9000` |

Build one service at a time with `make build-frontend`, `make build-web-backend`, or `make build-ai-backend`. Run `make smoke-containers` to build the stack, start it, hit health endpoints, and confirm Web Backend can reach AI Backend over the Docker network.

If local ports are already in use, override host ports without changing container wiring:

```bash
FRONTEND_HOST_PORT=3100 WEB_BACKEND_HOST_PORT=8100 AI_BACKEND_HOST_PORT=9100 make smoke-containers
```

## Deployment Levels

- Docker Compose is the local development and smoke-test orchestrator.
- GitHub Actions runs lint/test/build checks, builds each service image independently, smoke-tests the composed stack, and publishes GHCR images only for `v*.*.*` tags.
- Kubernetes manifests in root `infra/k8s/` provide production-style orchestration for the same three-service layout. Apply them with `kubectl apply -k ../infra/k8s` from this directory or `kubectl apply -k infra/k8s` from the repo root.

## CI/CD

The primary workflow is `.github/workflows/ci-cd.yml`.

- Pull requests to `main` and pushes to `main` run frontend, Web Backend, AI Backend, Docker Compose config, container build, and container smoke jobs.
- Frontend, Web Backend, AI Backend, and Compose checks run in parallel.
- Container image builds wait for checks to pass and build `frontend`, `web-backend`, and `ai-backend` independently.
- Container smoke tests start the composed stack and verify `GET /health`, `GET /health/providers`, frontend `GET /`, and Web Backend-to-AI Backend network reachability.
- Version tags matching `v*.*.*` publish all three GHCR images after checks and smoke tests pass:
  - `ghcr.io/heyyymonth/desk-claw-frontend:<tag>`
  - `ghcr.io/heyyymonth/desk-claw-web-backend:<tag>`
  - `ghcr.io/heyyymonth/desk-claw-ai-backend:<tag>`

Provider secrets are not required for CI health checks. Provider keys must be supplied only to the AI Backend runtime environment.

## Adding A Provider

Add a provider config entry in `ai_backend/config.py`, implement `ModelProvider` in `ai_backend/providers/`, register it in `ai_backend/main.py`, and add router/provider tests. Do not add provider keys, SDKs, or provider HTTP formats to `frontend/` or `web_backend/`.
