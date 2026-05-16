import pytest

from app.agents import ModelResponse
from app.core.settings import Settings
from app.services import model_warmup
from app.services.model_warmup import ModelWarmupError, warm_model


class StubModelClient:
    def __init__(self, response: ModelResponse | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls = []

    def complete_json(self, *, system_prompt, payload, timeout_seconds):
        self.calls.append({"system_prompt": system_prompt, "payload": payload, "timeout_seconds": timeout_seconds})
        if self.error:
            raise self.error
        return self.response


def test_warmup_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("WARM_MODEL_ON_STARTUP", "false")

    assert warm_model(Settings()) == {"status": "skipped", "reason": "warmup_disabled"}


def test_warmup_reports_provider_model_and_latency(monkeypatch):
    monkeypatch.setenv("WARM_MODEL_ON_STARTUP", "true")
    monkeypatch.setenv("MODEL_WARMUP_TIMEOUT_SECONDS", "12")
    client = StubModelClient(ModelResponse(output={"ok": True}, model_name="gpt-5.5", provider="openai"))

    monkeypatch.setattr(model_warmup, "build_model_client", lambda **kwargs: client)

    result = warm_model(Settings())

    assert result["status"] == "ready"
    assert result["provider"] == "openai"
    assert result["model"] == "gpt-5.5"
    assert result["elapsed_seconds"] >= 0
    assert client.calls[0]["timeout_seconds"] == 12


def test_warmup_surfaces_model_failure(monkeypatch):
    monkeypatch.setenv("WARM_MODEL_ON_STARTUP", "true")
    client = StubModelClient(error=OSError("connection refused"))
    monkeypatch.setattr(model_warmup, "build_model_client", lambda **kwargs: client)

    with pytest.raises(ModelWarmupError, match="Model warmup failed"):
        warm_model(Settings())
