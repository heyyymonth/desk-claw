import httpx
import asyncio

from config import ProviderConfig
from providers.anthropic_provider import AnthropicProvider
from providers.gemini_provider import GeminiProvider
from providers.ollama_provider import OllamaProvider
from providers.openai_provider import OpenAIProvider
from schemas import ChatRequest


def test_ollama_health_and_chat_mapping():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": []})
        seen["payload"] = _json(request)
        return httpx.Response(200, json={"model": "gemma4:31b-cloud", "message": {"content": "hello"}, "done_reason": "stop"})

    provider = OllamaProvider(config("ollama", "https://ollama.com/api", "gemma4:31b-cloud"), 1, httpx.MockTransport(handler))

    health = asyncio.run(provider.health_check())
    response = asyncio.run(provider.chat(chat_request()))

    assert health.configured is True
    assert seen["auth"] == "Bearer test-key"
    assert seen["url"] == "https://ollama.com/api/chat"
    assert seen["payload"]["model"] == "gemma4:31b-cloud"
    assert response.content == "hello"


def test_openai_uses_responses_api_and_normalizes_usage():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["payload"] = _json(request)
        return httpx.Response(
            200,
            headers={"x-request-id": "req_openai"},
            json={"model": "gpt-5.5", "output_text": "hello", "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}},
        )

    provider = OpenAIProvider(config("openai", "https://api.openai.com/v1", "gpt-5.5"), 1, httpx.MockTransport(handler))

    response = asyncio.run(provider.chat(chat_request()))

    assert seen["url"] == "https://api.openai.com/v1/responses"
    assert seen["auth"] == "Bearer test-key"
    assert seen["payload"]["store"] is False
    assert seen["payload"]["max_output_tokens"] == 1000
    assert response.usage.total_tokens == 3
    assert response.provider_request_id == "req_openai"


def test_anthropic_maps_system_and_messages():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-api-key")
        seen["version"] = request.headers.get("anthropic-version")
        seen["payload"] = _json(request)
        return httpx.Response(
            200,
            headers={"request-id": "req_anthropic"},
            json={"model": "claude-opus-4-7", "content": [{"type": "text", "text": "hello"}], "usage": {"input_tokens": 4, "output_tokens": 5}, "stop_reason": "end_turn"},
        )

    provider = AnthropicProvider(
        ProviderConfig("anthropic", "test-key", "https://api.anthropic.com", "claude-opus-4-7", {"version": "2023-06-01"}),
        1,
        httpx.MockTransport(handler),
    )

    response = asyncio.run(provider.chat(chat_request()))

    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["key"] == "test-key"
    assert seen["version"] == "2023-06-01"
    assert seen["payload"]["system"] == "You are helpful."
    assert seen["payload"]["messages"] == [{"role": "user", "content": "hello"}]
    assert response.usage.total_tokens == 9


def test_gemini_uses_generate_content_and_normalizes_usage():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["payload"] = _json(request)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "hello"}]}, "finishReason": "STOP"}],
                "usageMetadata": {"promptTokenCount": 6, "candidatesTokenCount": 7, "totalTokenCount": 13},
            },
        )

    provider = GeminiProvider(
        ProviderConfig("gemini", "test-key", "https://generativelanguage.googleapis.com", "gemini-3.1-flash-lite", {"api_version": "v1beta"}),
        1,
        httpx.MockTransport(handler),
    )

    response = asyncio.run(provider.chat(chat_request()))

    assert seen["url"] == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"
    assert seen["key"] == "test-key"
    assert seen["payload"]["systemInstruction"]["parts"][0]["text"] == "You are helpful."
    assert seen["payload"]["contents"][0]["role"] == "user"
    assert seen["payload"]["generationConfig"]["maxOutputTokens"] == 1000
    assert response.content == "hello"
    assert response.usage.total_tokens == 13


def config(name: str, base_url: str, default_model: str) -> ProviderConfig:
    return ProviderConfig(name, "test-key", base_url, default_model, {})


def chat_request() -> ChatRequest:
    return ChatRequest(
        messages=[
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hello"},
        ],
        temperature=0.2,
        max_tokens=1000,
    )


def _json(request: httpx.Request):
    import json

    return json.loads(request.content.decode("utf-8"))
