# Architecture

The app now runs as five separate services:

```text
Frontend
  -> Web Backend
  -> AI Backend
  -> Provider Adapter
  -> Ollama/OpenAI/Anthropic/Gemini

Eval Frontend
  -> Eval Backend
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
| Eval Frontend | Benchmark dashboard, editable eval cases, result inspection | Provider keys, product workflow, direct browser calls to AI Backend |
| Eval Backend | Benchmark persistence, eval prompts, scoring, run history, calls to AI Backend | Provider keys, provider base URLs, Web Backend product APIs |

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

The eval flow is intentionally separate from the product workflow:

```text
eval cases
  -> POST /api/eval-runs
  -> Eval Backend fixed parser prompt
  -> AI Backend /v1/chat
  -> provider adapter
  -> normalized model response
  -> eval scoring and SQLite run history
```

## Infrastructure

The service images are intentionally independent:

- `frontend/Dockerfile` builds a static Vite/React app and serves it with nginx.
- `web_backend/Dockerfile` runs only the FastAPI product API on port `8000`.
- `ai_backend/Dockerfile` runs only the FastAPI model gateway on port `9000`.
- `eval_frontend/Dockerfile` builds the eval dashboard and serves it with nginx.
- `eval_backend/Dockerfile` runs only the benchmark API on port `9300`.

Docker Compose wires the product services as `frontend -> web-backend -> ai-backend` and eval services as `eval-frontend -> eval-backend -> ai-backend`. Provider keys and provider base URLs are passed only to `ai-backend`; Web Backend and Eval Backend receive only `AI_BACKEND_URL`; browser frontends receive no provider secrets or AI Backend URL.

CI/CD lives in one primary GitHub Actions workflow, `.github/workflows/ci-cd.yml`, which runs service checks in parallel, builds each container independently, runs container smoke tests, and publishes five GHCR images only for `v*.*.*` tags.

Kubernetes manifests live in root `infra/k8s/` for production-style orchestration. They preserve the same service boundaries as Docker Compose: `frontend` and `eval-frontend` are exposed through Ingress hosts, `web-backend`, `eval-backend`, and `ai-backend` are internal ClusterIP services, and only `ai-backend` owns provider secrets.
