"""Unit test for application configuration loading and environment overrides."""

import pytest
from pydantic import ValidationError

from satbhoomi.config.settings import Settings, get_settings


def test_default_settings_loading(clean_settings: Settings) -> None:
    """Verify that settings load with correct defaults."""
    assert clean_settings.app_name == "SatBhoomi Score + Raksha"
    assert clean_settings.app_env in {"development", "staging", "production", "test"}
    assert clean_settings.api_port == 8000
    assert clean_settings.database_url.startswith("sqlite")


def test_custom_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that environment variables properly override default settings."""
    monkeypatch.setenv("APP_NAME", "SatBhoomi Staging")
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("API_PORT", "9090")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost:5432/satbhoomi")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.app_name == "SatBhoomi Staging"
    assert settings.app_env == "staging"
    assert settings.api_port == 9090
    assert settings.database_url == "postgresql+psycopg2://user:pass@localhost:5432/satbhoomi"

    get_settings.cache_clear()


def test_invalid_environment_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that invalid enum values for app_env raise validation errors."""
    monkeypatch.setenv("APP_ENV", "invalid_environment")
    with pytest.raises(ValidationError):
        Settings()
