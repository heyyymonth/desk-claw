# Backend

FastAPI service for validation, agent orchestration, model/tool execution, and response formatting.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Test

```bash
python3 -m pytest
```

Public runtime endpoints:

- `GET /api/health`
- `POST /api/parse-request`
