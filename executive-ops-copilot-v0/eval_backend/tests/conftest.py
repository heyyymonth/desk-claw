import tempfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app, get_store


@pytest.fixture
def client(monkeypatch) -> Iterator[TestClient]:
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("EVAL_DB_PATH", f"{tmpdir}/evals.db")
        monkeypatch.setenv("AI_BACKEND_URL", "http://ai-backend.test")
        monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        get_store.cache_clear()
        with TestClient(create_app()) as test_client:
            yield test_client
        get_store.cache_clear()
