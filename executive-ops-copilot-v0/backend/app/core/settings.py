from functools import lru_cache
from os import getenv

from app.agents import DEFAULT_MODEL_ENDPOINTS, DEFAULT_MODEL_NAME, DEFAULT_MODEL_PROVIDER

DEFAULT_CORS_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
)


class Settings:
    def __init__(self) -> None:
        self.app_name = getenv("APP_NAME", "Agentic Request Parser")
        self.ai_provider = getenv("AI_PROVIDER", DEFAULT_MODEL_PROVIDER).lower()
        self.agent_runtime = getenv("AGENT_RUNTIME", "native")
        self.ai_model = getenv("AI_MODEL", DEFAULT_MODEL_NAME)
        self.ai_api_endpoint = getenv("AI_API_ENDPOINT", DEFAULT_MODEL_ENDPOINTS.get(self.ai_provider, ""))
        self.openai_api_key = getenv("OPENAI_API_KEY")
        self.ai_agent_timeout_seconds = float(getenv("AI_AGENT_TIMEOUT_SECONDS", "180"))
        self.warm_model_on_startup = getenv("WARM_MODEL_ON_STARTUP", "false").lower() == "true"
        self.model_warmup_timeout_seconds = float(getenv("MODEL_WARMUP_TIMEOUT_SECONDS", "30"))
        self.timezone = getenv("APP_TIMEZONE", "America/Los_Angeles")
        self.cors_allowed_origins = _csv_env("CORS_ALLOWED_ORIGINS", DEFAULT_CORS_ALLOWED_ORIGINS)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _csv_env(name: str, default: tuple[str, ...]) -> list[str]:
    value = getenv(name)
    if value is None:
        return list(default)
    return [entry.strip() for entry in value.split(",") if entry.strip()]
