from pydantic import BaseModel, Field

from app.core.settings import Settings

class AiProviderOption(BaseModel):
    provider: str
    default_model: str
    endpoint: str
    linked: bool
    notes: str


class AiModelConfig(BaseModel):
    provider: str
    model: str = Field(min_length=1)
    endpoint: str
    runtime: str
    api_key_configured: bool
    options: list[AiProviderOption]


class AiModelConfigUpdate(BaseModel):
    provider: str
    model: str = Field(min_length=1)
    endpoint: str | None = None


def get_ai_model_config(settings: Settings) -> AiModelConfig:
    return AiModelConfig(
        provider="ai-backend",
        model="gateway-default",
        endpoint=settings.ai_backend_url,
        runtime=settings.agent_runtime,
        api_key_configured=False,
        options=_provider_options(settings),
    )


def update_ai_model_config(settings: Settings, payload: AiModelConfigUpdate) -> AiModelConfig:
    return get_ai_model_config(settings)


def current_model_client_kwargs(settings: Settings) -> dict:
    return {
        "gateway_url": settings.ai_backend_url,
    }


def reset_ai_model_config_override() -> None:
    return None


def _provider_options(settings: Settings) -> list[AiProviderOption]:
    return [
        AiProviderOption(
            provider="ai-backend",
            default_model="gateway-default",
            endpoint=settings.ai_backend_url,
            linked=True,
            notes="Model routing and provider secrets are owned by the AI Backend.",
        )
    ]
