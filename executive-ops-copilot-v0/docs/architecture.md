# Architecture

The app now runs as three separate services:

```text
Frontend
  -> Web Backend
  -> AI Backend
  -> Provider Adapter
  -> Ollama/OpenAI/Anthropic/Gemini
```

## Responsibilities

| Service | Owns | Does not own |
| --- | --- | --- |
| Frontend | UI, browser interactions, calls to Web Backend | Model calls, provider keys, AI routing |
| Web Backend | Product APIs, scheduling workflow, validation, guardrails, response shaping | Provider SDKs, provider keys, provider base URLs |
| AI Backend | Model routing, provider adapters, provider health, retries/fallback, normalized AI responses | Product UI, product DB logic, scheduling business rules |

## Runtime Flow

```text
raw text
  -> POST /api/parse-request
  -> Web Backend validation and scheduling workflow
  -> AI Backend /v1/chat for model-backed JSON steps
  -> provider adapter
  -> normalized model response
  -> guarded Web Backend product response
```

The compatibility frontend route remains `POST /api/parse-request`. A simple model smoke route is also available at `POST /api/chat`.

## Infrastructure

The service images are intentionally independent:

- `frontend/Dockerfile` builds a static Vite/React app and serves it with nginx.
- `web_backend/Dockerfile` runs only the FastAPI product API on port `8000`.
- `ai_backend/Dockerfile` runs only the FastAPI model gateway on port `9000`.

Docker Compose wires the services as `frontend -> web-backend -> ai-backend`. Provider keys and provider base URLs are passed only to `ai-backend`; Web Backend receives only `AI_BACKEND_URL`; Frontend receives no provider secrets or AI Backend URL for browser code.

CI/CD lives in one primary GitHub Actions workflow, `.github/workflows/ci-cd.yml`, which runs service checks in parallel, builds each container independently, runs container smoke tests, and publishes three GHCR images only for `v*.*.*` tags.

Kubernetes manifests live in root `infra/k8s/` for production-style orchestration. They preserve the same service boundaries as Docker Compose: `frontend` is exposed through Ingress, `web-backend` is an internal ClusterIP service, and `ai-backend` is an internal ClusterIP service that owns provider secrets.
