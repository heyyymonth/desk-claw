from functools import lru_cache
from os import getenv

from app.agents import DEFAULT_ADK_MODEL, DEFAULT_OLLAMA_MODEL


class Settings:
    def __init__(self) -> None:
        self.app_name = getenv("APP_NAME", "Executive Ops Scheduling Copilot")
        self.database_url = getenv("DATABASE_URL", "sqlite:///./data/deskclaw.db")
        self.sqlite_path = self.database_url.removeprefix("sqlite:///")
        self.llm_mode = getenv("LLM_MODE", "ollama")
        self.ollama_base_url = getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_url = self.ollama_base_url
        self.ollama_model = getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.agent_runtime = getenv("AGENT_RUNTIME", "adk")
        self.adk_model = getenv("ADK_MODEL", f"ollama_chat/{self.ollama_model}" if self.llm_mode == "ollama" else DEFAULT_ADK_MODEL)
        self.timezone = getenv("APP_TIMEZONE", "America/Los_Angeles")
        self.admin_api_key = getenv("ADMIN_API_KEY")
        self.actor_auth_token = getenv("ACTOR_AUTH_TOKEN")


@lru_cache
def get_settings() -> Settings:
    return Settings()
