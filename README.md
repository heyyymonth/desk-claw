# Desk Claw

Desk Claw is a local executive operations scheduling copilot. It helps an executive assistant turn a messy inbound meeting request into a structured scheduling decision: parse the request, apply executive preferences and calendar context, generate a recommendation, draft a response, capture feedback, and log the final decision.

The current implementation lives in `executive-ops-copilot-v0/` and is built as a local web app:

- FastAPI backend for validation, orchestration, policy checks, SQLite persistence, and local Gemma/Ollama model calls.
- React, TypeScript, and Vite frontend for the scheduling workflow UI.
- JSON Schema and OpenAPI contracts for backend/frontend data shapes.
- Playwright, Vitest, pytest, and local eval cases for verification.

## System Design

![desk.ai system design](executive-ops-copilot-v0/docs/assets/architecture/deskai%20system%20design.png)

## Product Direction

V0 is focused on human-reviewed executive scheduling triage. The product does not send emails, create calendar invites, write to external calendars, or act autonomously. It keeps the assistant in control while making request parsing, risk review, recommendation generation, and response drafting faster and more consistent.

The intended local model runtime is Ollama with `gemma4:latest`. The frontend never calls the model directly; all model access goes through the backend so outputs can be validated before they reach the UI.

## Repository

- `executive-ops-copilot-v0/`: runnable V0 app, tests, contracts, evals, and detailed README.
- `LICENSE`: project license.

Start with:

```bash
cd executive-ops-copilot-v0
```

Then follow the app-level README for setup, Gemma4/Ollama requirements, backend and frontend run commands, tests, and evals.
