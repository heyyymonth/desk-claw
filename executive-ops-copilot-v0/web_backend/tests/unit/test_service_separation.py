from pathlib import Path


def test_web_backend_app_does_not_contain_provider_secrets_or_urls():
    app_dir = Path(__file__).resolve().parents[2] / "app"
    forbidden = [
        "OPENAI_API_KEY",
        "OLLAMA_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "api.openai.com",
        "api.anthropic.com",
        "generativelanguage.googleapis.com",
        "ollama.com/api",
    ]

    offenders = []
    for path in app_dir.rglob("*.py"):
        text = path.read_text()
        for needle in forbidden:
            if needle in text:
                offenders.append(f"{path.relative_to(app_dir)}:{needle}")

    assert offenders == []
