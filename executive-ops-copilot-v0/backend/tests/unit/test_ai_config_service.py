from app.api.deps import get_native_agent_runner
from app.core.settings import Settings
from app.services.ai_config_service import get_ai_model_config


def test_openai_provider_does_not_report_api_key_when_missing(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    config = get_ai_model_config(Settings())

    assert config.provider == "openai"
    assert config.api_key_configured is False
    assert config.options[0].linked is False


def test_openai_provider_reports_api_key_when_present(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    config = get_ai_model_config(Settings())

    assert config.provider == "openai"
    assert config.api_key_configured is True


def test_native_agent_runner_is_not_created_without_api_key(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AGENT_RUNTIME", "native")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    class Runner:
        def __init__(self, **kwargs):
            raise AssertionError("runner should not be created without a key")

    assert get_native_agent_runner(Runner) is None


def test_unsupported_provider_is_normalized_to_openai(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_MODEL", "claude-opus-4-7")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    config = get_ai_model_config(Settings())

    assert config.provider == "openai"
    assert config.model == "gpt-5.5"
