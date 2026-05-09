# Executive Ops Scheduling Copilot V0

Local web app for executive operations scheduling triage.

## Layout

- `contracts`: JSON Schema and OpenAPI contracts.
- `backend`: FastAPI app, services, tests, SQLite storage.
- `frontend`: React + TypeScript + Vite app.
- `e2e`: Playwright tests.
- `evals`: fixed evaluation cases and expected outputs.
- `docs`: scope, architecture, assumptions, ADRs, and test strategy.

## Run Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

## Optional Ollama

```bash
ollama serve
ollama pull gemma
```
