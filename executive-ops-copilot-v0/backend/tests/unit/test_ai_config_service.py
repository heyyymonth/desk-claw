from app.core.settings import Settings
from app.services.ai_config_service import get_ai_model_config


def test_mock_provider_does_not_report_api_key_configured(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    config = get_ai_model_config(Settings())

    assert config.provider == "mock"
    assert config.api_key_configured is False
    assert config.options[-1].linked is True


def test_openai_provider_reports_api_key_when_present(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    config = get_ai_model_config(Settings())

    assert config.provider == "openai"
    assert config.api_key_configured is True
