from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import create_app


def test_cors_defaults_allow_local_vite_origins(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    get_settings.cache_clear()

    try:
        origins = get_settings().cors_allowed_origins
    finally:
        get_settings.cache_clear()

    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins
    assert "http://localhost:5174" in origins
    assert "http://127.0.0.1:5174" in origins


def test_cors_allows_configured_frontend_origin(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://heyyymonth.github.io, https://request-parser.example.com")
    get_settings.cache_clear()

    try:
        client = TestClient(create_app())
        response = client.options(
            "/api/health",
            headers={
                "Origin": "https://heyyymonth.github.io",
                "Access-Control-Request-Method": "GET",
            },
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://heyyymonth.github.io"
    assert response.headers["access-control-allow-credentials"] == "true"
