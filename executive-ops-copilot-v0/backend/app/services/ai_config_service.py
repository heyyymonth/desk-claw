from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, Field

from app.agents import (
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_MODEL_ENDPOINTS,
    DEFAULT_OPENAI_MODEL,
)
from app.core.settings import Settings

ModelProvider = Literal["openai", "anthropic", "gemini", "mock"]

PROVIDER_DEFAULT_MODELS = {
    "openai": DEFAULT_OPENAI_MODEL,
    "anthropic": DEFAULT_ANTHROPIC_MODEL,
    "gemini": DEFAULT_GEMINI_MODEL,
    "mock": "deterministic",
}


class AiProviderOption(BaseModel):
    provider: ModelProvider
    default_model: str
    endpoint: str
    linked: bool
    notes: str


class AiModelConfig(BaseModel):
    provider: ModelProvider
    model: str = Field(min_length=1)
    endpoint: str
    runtime: str
    api_key_configured: bool
    options: list[AiProviderOption]


class AiModelConfigUpdate(BaseModel):
    provider: ModelProvider
    model: str = Field(min_length=1)
    endpoint: str | None = None


_OVERRIDE: dict | None = None


def get_ai_model_config(settings: Settings) -> AiModelConfig:
    base = _base_config(settings)
    if _OVERRIDE:
        base.update(deepcopy(_OVERRIDE))
    provider = base["provider"]
    endpoint = base.get("endpoint") or DEFAULT_MODEL_ENDPOINTS.get(provider, "")
    return AiModelConfig(
        provider=provider,
        model=base["model"],
        endpoint=endpoint,
        runtime=settings.agent_runtime,
        api_key_configured=_api_key_configured(provider, settings),
        options=_provider_options(settings),
    )


def update_ai_model_config(settings: Settings, payload: AiModelConfigUpdate) -> AiModelConfig:
    global _OVERRIDE
    endpoint = payload.endpoint or DEFAULT_MODEL_ENDPOINTS.get(payload.provider, "")
    _OVERRIDE = {"provider": payload.provider, "model": payload.model.strip(), "endpoint": endpoint}
    return get_ai_model_config(settings)


def current_model_client_kwargs(settings: Settings) -> dict:
    config = get_ai_model_config(settings)
    return {
        "provider": config.provider,
        "model": config.model,
        "api_key": _api_key_for_provider(config.provider, settings),
        "endpoint": config.endpoint,
    }


def reset_ai_model_config_override() -> None:
    global _OVERRIDE
    _OVERRIDE = None


def _base_config(settings: Settings) -> dict:
    return {
        "provider": settings.ai_provider,
        "model": settings.ai_model or PROVIDER_DEFAULT_MODELS.get(settings.ai_provider, DEFAULT_OPENAI_MODEL),
        "endpoint": settings.ai_api_endpoint or DEFAULT_MODEL_ENDPOINTS.get(settings.ai_provider, ""),
    }


def _provider_options(settings: Settings) -> list[AiProviderOption]:
    return [
        AiProviderOption(
            provider="openai",
            default_model=DEFAULT_OPENAI_MODEL,
            endpoint=DEFAULT_MODEL_ENDPOINTS["openai"],
            linked=bool(settings.openai_api_key),
            notes="Linked now through OPENAI_API_KEY and the Responses API.",
        ),
        AiProviderOption(
            provider="anthropic",
            default_model=DEFAULT_ANTHROPIC_MODEL,
            endpoint=DEFAULT_MODEL_ENDPOINTS["anthropic"],
            linked=False,
            notes="Decoupled placeholder; no Anthropic key is read by this V0 implementation.",
        ),
        AiProviderOption(
            provider="gemini",
            default_model=DEFAULT_GEMINI_MODEL,
            endpoint=DEFAULT_MODEL_ENDPOINTS["gemini"],
            linked=False,
            notes="Decoupled placeholder; no Gemini key is read by this V0 implementation.",
        ),
        AiProviderOption(
            provider="mock",
            default_model="deterministic",
            endpoint="",
            linked=True,
            notes="Deterministic local fallback for tests and demos.",
        ),
    ]


def _api_key_configured(provider: str, settings: Settings) -> bool:
    return bool(_api_key_for_provider(provider, settings))


def _api_key_for_provider(provider: str, settings: Settings) -> str | None:
    if provider == "openai":
        return settings.openai_api_key
    return None
