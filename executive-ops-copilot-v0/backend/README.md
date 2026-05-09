# Backend

FastAPI owns orchestration, validation, policy, recommendation generation, logging, SQLite persistence, AI audit records, and Ollama calls.

## Commands

```bash
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

## Persistence

The backend supports `sqlite:///` URLs only in V0. The default is `sqlite:///./data/deskclaw.db`.

AI parse, recommendation, and draft calls are logged to `ai_audit_log`; actor details are captured from `X-Actor-Id`, `X-Actor-Email`, and `X-Actor-Name` when provided.
