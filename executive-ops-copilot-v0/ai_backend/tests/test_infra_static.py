from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_compose_declares_three_service_build_contexts():
    text = (ROOT / "docker-compose.yml").read_text()

    assert "frontend:" in text
    assert "web-backend:" in text
    assert "ai-backend:" in text
    assert "context: ./frontend" in text
    assert "context: ./web_backend" in text
    assert "context: ./ai_backend" in text


def test_provider_env_vars_are_scoped_to_ai_backend():
    text = (ROOT / "docker-compose.yml").read_text()
    web_section = text.split("  web-backend:", 1)[1].split("  ai-backend:", 1)[0]
    ai_section = text.split("  ai-backend:", 1)[1]

    for key in ["OLLAMA_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]:
        assert key not in web_section
        assert key in ai_section


def test_env_example_uses_placeholders_and_env_is_ignored():
    env_example = (ROOT / ".env.example").read_text()
    gitignore = (ROOT / ".gitignore").read_text()

    assert "replace_me" in env_example
    assert ".env" in gitignore
    assert "sk-" not in env_example
