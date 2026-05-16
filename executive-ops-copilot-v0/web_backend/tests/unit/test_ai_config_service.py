from app.api.deps import get_native_agent_runner
from app.core.settings import Settings
from app.services.ai_config_service import get_ai_model_config


def test_web_backend_reports_ai_backend_gateway(monkeypatch):
    monkeypatch.setenv("AI_BACKEND_URL", "http://ai-backend:9000")

    config = get_ai_model_config(Settings())

    assert config.provider == "ai-backend"
    assert config.endpoint == "http://ai-backend:9000"
    assert config.api_key_configured is False
    assert config.options[0].linked is True


def test_provider_keys_are_not_required_by_web_backend(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    config = get_ai_model_config(Settings())

    assert config.provider == "ai-backend"
    assert config.api_key_configured is False


def test_native_agent_runner_is_created_without_provider_keys(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME", "native")
    monkeypatch.setenv("AI_BACKEND_URL", "http://ai-backend:9000")

    class Runner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    runner = get_native_agent_runner(Runner)
    assert runner.kwargs["gateway_url"] == "http://ai-backend:9000"


def test_native_agent_runner_respects_runtime_disable(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME", "disabled")

    assert get_native_agent_runner(object) is None
