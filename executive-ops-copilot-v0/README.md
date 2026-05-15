# Executive Ops Scheduling Copilot V0

Local web app for executive operations scheduling triage. V0 helps an executive assistant paste one inbound meeting request, parse it into structured intent, apply a single executive rules profile and local calendar context, generate a recommendation, draft a response for review, capture feedback, and log the final decision.

The app is local-first and contract-first. The frontend calls FastAPI only. FastAPI owns validation, orchestration, policy checks, persistence, and Ollama/Gemma model access.

## System Design

![desk.ai system design](docs/assets/architecture/deskai%20system%20design.png)

## Agent Architecture

![desk.ai multi-agent architecture](docs/assets/architecture/deskai-agent-architecture.png)

The multi-agent layer is the backbone of Desk AI. FastAPI creates typed agent tasks and hands them to the Google ADK runtime, which owns model reasoning, tool selection, and trace capture. Each agent has a narrow responsibility: the parser agent converts raw meeting text into structured intent, the resolution agent reasons through calendar conflicts, executive rules, risk, and scheduling strategy, and the draft agent creates a safe human-reviewable response.

The tools are deterministic backend functions. Agents decide when to call them, but the tools ground the result and the backend validates every output into schema-shaped JSON before it reaches the product surface. This keeps the system model-backed without allowing hidden autonomous actions, calendar write-back, or direct frontend-to-model access.

## Current Scope

In scope:

- Paste-based meeting request intake.
- One local user and one executive rules profile.
- Local mock calendar blocks through the backend API.
- Structured request parsing into contract-shaped models.
- Recommendation generation with policy checks and local Gemma assistance.
- Draft response generation for accept, decline, clarify, or defer paths.
- Decision feedback capture, local SQLite decision log storage, and AI audit logging.
- Local eval cases and JSON Schema/OpenAPI contracts.

Out of scope for V0:

- Real calendar reads or writes.
- Sending email, Slack, Teams, calendar invites, or external messages.
- CRM, ATS, travel, inbox, OAuth, SSO, tenant, billing, or RBAC integrations.
- Autonomous scheduling without human review.
- Generic chatbot behavior outside the scheduling workflow.

## Repository Layout

- `backend/`: FastAPI app, Pydantic models, service layer, SQLite persistence, Ollama client, unit and contract tests.
- `frontend/`: React, TypeScript, Vite, Tailwind workflow UI and component tests.
- `contracts/`: JSON Schema and OpenAPI contracts used as the shared backend/frontend source of truth.
- `docs/`: product scope, architecture, assumptions, interface contracts, test strategy, and ADRs.
- `e2e/`: Playwright browser workflow tests with seeded API mocks.
- `evals/`: fixed scheduling cases, expected outputs, and reusable examples.
- `scripts/`: local helper scripts, including the root E2E runner.

## Requirements

- Python 3.11 or newer.
- Node.js and npm.
- Ollama with `gemma4:latest` pulled for real model-backed local runs.

Tests use deterministic mocks where appropriate, but the intended runnable local app uses Ollama and Gemma4.

## Ollama and Gemma4

Start Ollama and pull the required model:

```bash
ollama serve
ollama pull gemma4:latest
ollama list
```

`ollama list` should include `gemma4:latest`.

For normal local development, start the full stack with:

```bash
./scripts/start-local.sh
```

This script treats model readiness as part of service startup:

1. Starts or verifies Ollama at `http://127.0.0.1:11434`.
2. Verifies `gemma4:latest` is available, pulling it if needed.
3. Starts FastAPI with `WARM_OLLAMA_ON_STARTUP=true`.
4. Waits for `/api/health` to return only after backend startup has loaded the model.
5. Starts the Vite frontend and waits for it to serve `http://127.0.0.1:5173`.

Startup can take around a minute on a cold local model load. After startup, request latency reflects the ADK agent/tool loop rather than model loading. The script stays attached as the local service supervisor; press `Ctrl-C` in that terminal to stop the services.

The backend defaults to:

```bash
LLM_MODE=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma4:latest
```

The health endpoint reports the active model:

```bash
curl http://127.0.0.1:8000/api/health
```

Expected shape:

```json
{
  "status": "ok",
  "ollama": "configured",
  "model": "ollama_chat/gemma4:latest",
  "model_warmup": {
    "status": "ready",
    "model": "gemma4:latest",
    "elapsed_seconds": 59.244,
    "ollama_total_seconds": 58.81,
    "ollama_load_seconds": 36.443
  }
}
```

## Run Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
LLM_MODE=ollama OLLAMA_MODEL=gemma4:latest python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

ADK eval dependencies are intentionally separate from the normal backend install. Install them only when running evals:

```bash
pip install -e ".[dev,evals]"
```

The default SQLite database path is `backend/data/deskclaw.db` when running from `backend/`. Local database files are ignored by git.

## Persistence and Audit

The backend uses SQLite for local durable storage. The default database is:

```text
backend/data/deskclaw.db
```

Override it with:

```bash
DATABASE_URL=sqlite:///./data/deskclaw.db
```

Persisted tables include:

- `app_users`: actor identity captured from request headers.
- `ai_audit_log`: AI workflow input/output audit records for parse, recommendation, and draft calls.
- `decisions`: simple feedback events from `POST /api/feedback`.
- `decision_log`: full workflow decision records from `POST /api/decisions`.

AI audit records include actor ID, endpoint, operation, configured model, model status, redacted request/response payload metadata, response/error status, timestamp, and latency. Free-form text fields such as request text, requester, attendees, draft subject/body, notes, and error messages are redacted before SQLite storage. Actor details are trusted only when `ACTOR_AUTH_TOKEN` is configured on the backend and the request includes the matching `X-DeskAI-Actor-Token`. Without that token boundary, supplied actor headers are ignored and audit rows use `local-user`.

```text
X-DeskAI-Actor-Token: $ACTOR_AUTH_TOKEN
X-Actor-Id: ea-1
X-Actor-Email: ea@example.com
X-Actor-Name: EA User
```

Retrieve audit events:

```bash
curl -H "X-DeskAI-Admin-Key: $ADMIN_API_KEY" http://127.0.0.1:8000/api/audit/ai?limit=50
```

AI audit and telemetry read endpoints require `ADMIN_API_KEY` on the backend. If the key is not configured, those admin read endpoints fail closed.

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173/
```

The frontend defaults to the backend on the same hostname at port `8000`. Override with:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

## Workflow

1. Paste a raw meeting request.
2. Parse the request into structured intent.
3. Review requester, priority, duration, meeting type, missing fields, sensitivity, async candidacy, and escalation requirement.
4. Review or edit executive rules.
5. Review local mock calendar context.
6. Generate a recommendation with decision, confidence, risks, rationale, safe action, and proposed slots.
7. Generate an editable draft response.
8. Submit final decision feedback and notes.
9. Review decision log entries.

Drafts are never sent automatically. Calendar state is not written to any external system.

## API Surface

Primary contract endpoints:

- `GET /api/health`
- `POST /api/requests/parse`
- `POST /api/recommendations/generate`
- `POST /api/drafts/generate`
- `GET /api/rules`
- `GET /api/rules/default`
- `PUT /api/rules`
- `GET /api/calendar/blocks`
- `GET /api/calendar/mock`
- `POST /api/calendar/blocks`
- `POST /api/feedback`
- `GET /api/decisions`
- `GET /api/audit/ai`
- `GET /api/telemetry/ai/dashboard`
- `GET /metrics`
- `POST /api/evals/run`

Legacy compatibility endpoints retained for older local clients:

- `GET /api/default-rules`
- `GET /api/mock-calendar`
- `POST /api/parse-request`
- `POST /api/recommendation`
- `POST /api/draft-response`
- `POST /api/decisions`

Contracts live in:

- `contracts/openapi/openapi.yaml`
- `contracts/schemas/*.schema.json`

Raw model output must not cross the API boundary. Backend services validate LLM output into typed models before returning JSON to the frontend.

## Testing

Backend:

```bash
cd backend
python3 -m pytest
```

Frontend:

```bash
cd frontend
npm test
npm run build
```

E2E:

```bash
./scripts/run-e2e.sh
```

Or manually:

```bash
cd e2e
npm install
npm run test:e2e
```

The Playwright suite mocks `/api/**` with seeded V0 data, so it does not require real calendar, email, Slack, Microsoft, Google, or Ollama integrations.

CI runs backend tests, frontend tests, frontend build, and Playwright E2E automatically on every push to `main` and every pull request targeting `main`.
ADK evals are not part of the default CI test gate.

## Deployment Prep

Container and Kubernetes deployment artifacts live in `infra/`.
The tracked deployment readiness checklist lives in `docs/deployment-readiness.md`.

Local container stack:

```bash
docker compose up --build
```

Kubernetes manifests:

```bash
kubectl apply -k infra/k8s
```

Validate the rendered manifests locally:

```bash
./scripts/validate-k8s.sh
```

Install `kubeconform` locally to run the same offline schema validation that CI runs. Without it, the script still renders the manifests and checks Desk AI deployment invariants.

Render immutable-image release manifests:

```bash
./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
```

Promote or roll back a Kubernetes release using the runbook:

```text
docs/deployment-rollout-runbook.md
```

Smoke test a deployed public ingress:

```bash
./scripts/smoke-deploy.sh https://desk-ai.example.com
```

The services are split into frontend, backend, and Ollama pods. Backend readiness waits for model warmup, so a ready backend means the configured Ollama model has been loaded before user traffic is served.
Before public exposure, review `docs/deployment-resource-tuning.md` for Ollama/backend CPU, memory, GPU, and timeout sizing.
Provider selection guidance lives in `docs/deployment-provider-selection.md`.
Container image access guidance lives in `docs/deployment-image-access.md`.
Network policy guidance lives in `docs/deployment-network-policy.md`.
Database migration guidance lives in `docs/deployment-database-migration.md`; backend replicas must stay at one while SQLite is configured.
Backup and restore guidance lives in `docs/deployment-backup-restore.md`.
Production auth and session guidance lives in `docs/deployment-auth-session.md`.
Runtime observability guidance lives in `docs/deployment-observability.md`.

## Evals

Scheduling eval cases live in:

- `evals/cases/v0_scheduling_cases.yaml`
- `evals/expected/v0_expected_outputs.yaml`

Run evals through the backend endpoint:

```bash
cd backend
pip install -e ".[dev,evals]"
curl -X POST http://127.0.0.1:8000/api/evals/run
```

Or run the eval-marked endpoint contract directly:

```bash
cd backend
python3 -m pytest -m evals
```

Eval assertions cover meeting type, draft type, sensitivity, async candidacy, escalation requirement, aggregate risk level, and safe action.

## Development Rules

- Keep the frontend as a workflow UI. It must call FastAPI only.
- Keep route handlers thin and put business behavior in backend services.
- Keep deterministic calendar math, rule checks, and persistence in the backend.
- Validate all LLM output before using it.
- Update JSON Schema and OpenAPI when request or response shapes change.
- Add or update tests when changing service behavior, API contracts, or user-visible workflow behavior.
- Do not commit secrets, tokens, real customer data, private calendar payloads, generated databases, or local cache files.

## Key Docs

- `docs/product-scope.md`: V0 goal, hard scope, success criteria.
- `docs/architecture.md`: system shape, ownership, request flow, failure states.
- `docs/interface-contracts.md`: contract files, endpoints, enums, compatibility rules.
- `docs/test-strategy.md`: unit, contract, integration, E2E, and eval strategy.
- `docs/deployment-readiness.md`: public deployment readiness checklist, known issues, remaining repo work, and outside dependencies.
- `docs/deployment-provider-selection.md`: EKS/GKE/AKS decision guide, required cluster capabilities, and first-cluster shape.
- `docs/deployment-image-access.md`: public/private GHCR pull options and Kubernetes image-pull Secret setup.
- `docs/deployment-resource-tuning.md`: Ollama/backend CPU, memory, GPU, and timeout sizing guidance.
- `docs/deployment-rollout-runbook.md`: immutable commit-tag promotion, rollout verification, smoke checks, and rollback commands.
- `docs/deployment-network-policy.md`: Kubernetes NetworkPolicy baseline, CNI requirements, and provider-specific hardening guidance.
- `docs/deployment-database-migration.md`: SQLite-to-managed-Postgres migration path and backend scaling gate.
- `docs/deployment-backup-restore.md`: backend SQLite backup/restore, provider snapshots, and Ollama data recovery guidance.
- `docs/deployment-auth-session.md`: OIDC/session/RBAC target design before public admin dashboard exposure.
- `docs/deployment-observability.md`: Prometheus backend metrics, ingress-controller error metrics, and alert guidance.
- `docs/assumptions.md`: product, enterprise, and eval assumptions.
- `docs/adr/0001-local-web-app.md`: local web app and FastAPI-owned orchestration.
- `docs/adr/0002-ai-boundaries.md`: AI boundaries and enterprise safety.
