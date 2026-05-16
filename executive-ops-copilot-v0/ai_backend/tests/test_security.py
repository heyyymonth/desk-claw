import asyncio

import httpx

from config import ProviderConfig
from providers.ollama_provider import OllamaProvider


def test_health_does_not_expose_provider_keys():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": []})

    provider = OllamaProvider(
        ProviderConfig("ollama", "secret-ollama-key", "https://ollama.com/api", "gemma4:31b-cloud", {}),
        1,
        httpx.MockTransport(handler),
    )

    body = asyncio.run(provider.health_check()).model_dump_json()

    assert "secret-ollama-key" not in body
