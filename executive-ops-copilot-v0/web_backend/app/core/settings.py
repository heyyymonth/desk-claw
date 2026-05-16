from functools import lru_cache
from os import getenv

DEFAULT_CORS_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
)


class Settings:
    def __init__(self) -> None:
        self.app_name = getenv("APP_NAME", "Agentic Request Parser")
        self.agent_runtime = getenv("AGENT_RUNTIME", "native")
        self.ai_backend_url = getenv("AI_BACKEND_URL", "http://localhost:9000").rstrip("/")
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
