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

Actor headers are trusted only when `ACTOR_AUTH_TOKEN` is configured and requests include the matching `X-DeskAI-Actor-Token`. Without that configured token, actor headers are ignored and AI audit rows use `local-user` so clients cannot forge arbitrary audit identities.

AI audit and telemetry read endpoints expose sensitive request/response payloads and require `ADMIN_API_KEY` on the backend plus the `X-DeskAI-Admin-Key` request header. If `ADMIN_API_KEY` is not configured, those admin read endpoints fail closed.
