import httpx
import pytest

from app.core.errors import ServiceError
from app.services.ai_client import AiBackendClient


def test_ai_client_calls_ai_backend_url(monkeypatch):
    seen = {}

    def fake_post(url, json, timeout):
        seen["url"] = url
        seen["json"] = json
        seen["timeout"] = timeout
        return httpx.Response(200, json={"content": "hello", "provider": "ollama", "model": "gemma4:31b-cloud"})

    monkeypatch.setattr(httpx, "post", fake_post)

    response = AiBackendClient("http://ai-backend:9000", 12).chat("Say hello")

    assert seen["url"] == "http://ai-backend:9000/v1/chat"
    assert seen["json"]["messages"][1]["content"] == "Say hello"
    assert seen["timeout"] == 12
    assert response.provider == "ollama"


def test_ai_client_normalizes_ai_backend_failure(monkeypatch):
    def fake_post(url, json, timeout):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(ServiceError) as exc:
        AiBackendClient("http://ai-backend:9000").chat("Say hello")

    assert exc.value.code == "ai_backend_unavailable"
