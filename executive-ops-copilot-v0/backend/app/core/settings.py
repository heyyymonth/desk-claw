from functools import lru_cache
from os import getenv

from app.agents import DEFAULT_ADK_MODEL, DEFAULT_OLLAMA_MODEL


class Settings:
    def __init__(self) -> None:
        self.app_name = getenv("APP_NAME", "Executive Ops Scheduling Copilot")
        self.database_url = getenv("DATABASE_URL", "sqlite:///./data/deskclaw.db")
        self.database_dialect = _database_dialect(self.database_url)
        self.sqlite_path = self.database_url.removeprefix("sqlite:///") if self.database_dialect == "sqlite" else None
        self.llm_mode = getenv("LLM_MODE", "ollama")
        self.ollama_base_url = getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_url = self.ollama_base_url
        self.ollama_model = getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.agent_runtime = getenv("AGENT_RUNTIME", "adk")
        self.adk_model = getenv("ADK_MODEL", f"ollama_chat/{self.ollama_model}" if self.llm_mode == "ollama" else DEFAULT_ADK_MODEL)
        self.adk_agent_timeout_seconds = float(getenv("ADK_AGENT_TIMEOUT_SECONDS", "180"))
        self.warm_ollama_on_startup = getenv("WARM_OLLAMA_ON_STARTUP", "true").lower() == "true"
        self.ollama_warmup_timeout_seconds = float(getenv("OLLAMA_WARMUP_TIMEOUT_SECONDS", "180"))
        self.timezone = getenv("APP_TIMEZONE", "America/Los_Angeles")
        self.admin_api_key = getenv("ADMIN_API_KEY")
        self.actor_auth_token = getenv("ACTOR_AUTH_TOKEN")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _database_dialect(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        return "sqlite"
    if database_url.startswith(("postgres://", "postgresql://")):
        return "postgres"
    return "unsupported"
