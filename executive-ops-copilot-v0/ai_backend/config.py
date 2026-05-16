from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str | None
    base_url: str
    default_model: str
    extra: dict[str, str]

    @property
    def configured(self) -> bool:
        return bool(self.api_key)


class Settings:
    def __init__(self) -> None:
        self.port = int(getenv("AI_BACKEND_PORT", "9000"))
        self.default_provider = getenv("DEFAULT_AI_PROVIDER", "ollama").lower()
        self.fallback_provider = _optional_lower("FALLBACK_AI_PROVIDER", "openai")
        self.timeout_seconds = float(getenv("AI_REQUEST_TIMEOUT_SECONDS", "120"))
        self.providers = {
            "ollama": ProviderConfig(
                name="ollama",
                api_key=getenv("OLLAMA_API_KEY"),
                base_url=getenv("OLLAMA_BASE_URL", "https://ollama.com/api").rstrip("/"),
                default_model=getenv("OLLAMA_DEFAULT_MODEL", "gemma4:31b-cloud"),
                extra={},
            ),
            "openai": ProviderConfig(
                name="openai",
                api_key=getenv("OPENAI_API_KEY"),
                base_url=getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
                default_model=getenv("OPENAI_DEFAULT_MODEL", "gpt-5.5"),
                extra={},
            ),
            "anthropic": ProviderConfig(
                name="anthropic",
                api_key=getenv("ANTHROPIC_API_KEY"),
                base_url=getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/"),
                default_model=getenv("ANTHROPIC_DEFAULT_MODEL", "claude-opus-4-7"),
                extra={"version": getenv("ANTHROPIC_VERSION", "2023-06-01")},
            ),
            "gemini": ProviderConfig(
                name="gemini",
                api_key=getenv("GEMINI_API_KEY"),
                base_url=getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com").rstrip("/"),
                default_model=getenv("GEMINI_DEFAULT_MODEL", "gemini-3.1-flash-lite"),
                extra={
                    "api_version": getenv("GEMINI_API_VERSION", "v1beta"),
                    "openai_compat_base_url": getenv(
                        "GEMINI_OPENAI_COMPAT_BASE_URL",
                        "https://generativelanguage.googleapis.com/v1beta/openai/",
                    ),
                    "use_openai_compat": getenv("GEMINI_USE_OPENAI_COMPAT", "false").lower(),
                },
            ),
        }


def _optional_lower(name: str, default: str | None = None) -> str | None:
    value = getenv(name, default)
    return value.lower() if value else None
