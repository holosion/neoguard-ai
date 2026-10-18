import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_app_env_enables_production_validation(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    with pytest.raises(ValidationError, match="Production CORS_ORIGINS"):
        Settings(_env_file=None)
    monkeypatch.setenv("CORS_ORIGINS", "https://neoguard-ai.vercel.app")
    assert Settings(_env_file=None).environment == "production"
