import sys
from pathlib import Path

import pytest

from app.core.settings import get_settings
from app.services.ai_config_service import reset_ai_model_config_override

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(autouse=True)
def test_env(monkeypatch):
    get_settings.cache_clear()
    reset_ai_model_config_override()
    monkeypatch.setenv("AI_BACKEND_URL", "http://ai-backend.test")
    yield
    reset_ai_model_config_override()
    get_settings.cache_clear()
