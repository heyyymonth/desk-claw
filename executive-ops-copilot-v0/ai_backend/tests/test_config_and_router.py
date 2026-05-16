import pytest
import asyncio

from config import ProviderConfig, Settings
from providers.base import ModelProvider, ProviderError
from routing.model_router import ModelRouter
from schemas import ChatRequest, ChatResponse, ProviderHealth, Usage


def test_missing_provider_key_marks_provider_unconfigured(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "")

    settings = Settings()

    assert settings.providers["ollama"].configured is False
    assert settings.providers["ollama"].base_url == "https://ollama.com/api"
    assert settings.providers["openai"].default_model == "gpt-5.5"


def test_router_uses_default_provider():
    router = ModelRouter({"ollama": StubProvider("ollama")}, "ollama", None)

    response = asyncio.run(router.chat(chat_request()))

    assert response.provider == "ollama"


def test_router_uses_explicit_provider_override():
    router = ModelRouter({"ollama": StubProvider("ollama"), "gemini": StubProvider("gemini")}, "ollama", None)

    response = asyncio.run(router.chat(chat_request(provider="gemini")))

    assert response.provider == "gemini"


def test_router_falls_back_once_when_primary_fails():
    router = ModelRouter({"ollama": FailingProvider("ollama"), "openai": StubProvider("openai")}, "ollama", "openai")

    response = asyncio.run(router.chat(chat_request()))

    assert response.provider == "openai"
    assert response.fallback_used is True
    assert response.primary_provider_error == "ollama failed"


def test_router_rejects_streaming():
    router = ModelRouter({"ollama": StubProvider("ollama")}, "ollama", None)

    with pytest.raises(ProviderError) as exc:
        asyncio.run(router.chat(chat_request(stream=True)))

    assert exc.value.status_code == 400


class StubProvider(ModelProvider):
    def __init__(self, name: str):
        self.name = name
        super().__init__(ProviderConfig(name, "key", f"https://{name}.test", f"{name}-model", {}), 1)

    def health_url(self) -> str:
        return f"{self.config.base_url}/health"

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(configured=True, reachable=True, auth="valid", base_url=self.config.base_url, default_model=self.default_model)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(id="airesp_test", provider=self.name, model=self.default_model, content="ok", usage=Usage(), latency_ms=1)


class FailingProvider(StubProvider):
    async def chat(self, request: ChatRequest) -> ChatResponse:
        raise ProviderError(self.name, f"{self.name} failed", 401)


def chat_request(provider=None, stream=False) -> ChatRequest:
    return ChatRequest(provider=provider, messages=[{"role": "user", "content": "hello"}], stream=stream)
