import json

import pytest

from app.core.settings import Settings
from app.services import model_warmup
from app.services.model_warmup import ModelWarmupError, warm_ollama_model


class StubResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_warmup_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("WARM_OLLAMA_ON_STARTUP", "false")

    assert warm_ollama_model(Settings()) == {"status": "skipped", "reason": "warmup_disabled"}


def test_warmup_reports_load_timing(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "ollama")
    monkeypatch.setenv("WARM_OLLAMA_ON_STARTUP", "true")

    def fake_urlopen(request, timeout):
        assert request.full_url == "http://localhost:11434/api/chat"
        assert timeout == 180
        return StubResponse(
            {
                "model": "gemma4:latest",
                "total_duration": 2_500_000_000,
                "load_duration": 1_000_000_000,
            }
        )

    monkeypatch.setattr(model_warmup.urllib.request, "urlopen", fake_urlopen)

    result = warm_ollama_model(Settings())

    assert result["status"] == "ready"
    assert result["model"] == "gemma4:latest"
    assert result["ollama_total_seconds"] == 2.5
    assert result["ollama_load_seconds"] == 1.0


def test_warmup_surfaces_ollama_failure(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "ollama")
    monkeypatch.setenv("WARM_OLLAMA_ON_STARTUP", "true")

    def fake_urlopen(request, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(model_warmup.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(ModelWarmupError, match="Ollama warmup failed"):
        warm_ollama_model(Settings())
