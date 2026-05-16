from fastapi import FastAPI, HTTPException

from config import Settings
from providers.anthropic_provider import AnthropicProvider
from providers.base import ProviderError
from providers.gemini_provider import GeminiProvider
from providers.ollama_provider import OllamaProvider
from providers.openai_provider import OpenAIProvider
from routing.model_router import ModelRouter
from schemas import ChatRequest, TestChatPayload


def build_providers(settings: Settings):
    return {
        "ollama": OllamaProvider(settings.providers["ollama"], settings.timeout_seconds),
        "openai": OpenAIProvider(settings.providers["openai"], settings.timeout_seconds),
        "anthropic": AnthropicProvider(settings.providers["anthropic"], settings.timeout_seconds),
        "gemini": GeminiProvider(settings.providers["gemini"], settings.timeout_seconds),
    }


def create_app() -> FastAPI:
    settings = Settings()
    providers = build_providers(settings)
    router = ModelRouter(providers, settings.default_provider, settings.fallback_provider)
    app = FastAPI(title="AI Backend Model Gateway", version="0.1.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "ai-backend"}

    @app.get("/health/providers")
    async def provider_health():
        results = {name: (await provider.health_check()).model_dump() for name, provider in providers.items()}
        status = "ok" if any(result["configured"] for result in results.values()) else "degraded"
        return {"status": status, "providers": results}

    @app.get("/health/{provider_name}")
    async def single_provider_health(provider_name: str):
        provider = providers.get(provider_name)
        if provider is None:
            raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_name}")
        return (await provider.health_check()).model_dump()

    @app.post("/v1/chat")
    async def chat(request: ChatRequest):
        try:
            return await router.chat(request)
        except ProviderError as exc:
            raise HTTPException(
                status_code=exc.status_code or 503,
                detail={"error": {"type": "provider_unavailable", "message": exc.message, "provider": exc.provider}},
            ) from exc

    @app.post("/test/{provider_name}/chat")
    async def test_provider_chat(provider_name: str, payload: TestChatPayload):
        if provider_name not in providers:
            raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_name}")
        return await chat(
            ChatRequest(
                provider=provider_name,  # type: ignore[arg-type]
                messages=[{"role": "user", "content": payload.message}],
                temperature=0.2,
                max_tokens=1000,
                stream=False,
                metadata={"source": "ai-backend-test"},
            )
        )

    return app


app = create_app()
