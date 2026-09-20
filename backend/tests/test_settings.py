"""Tests for application settings loading and validation."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_defaults_load_without_env() -> None:
    settings = Settings()
    assert settings.project_name == "Nestro"
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.database_url
    assert settings.jwt_secret


def test_valid_environment_accepted() -> None:
    assert Settings(environment="staging").environment == "staging"
    assert Settings(environment="production").environment == "production"
    assert Settings(environment="development").environment == "development"


def test_invalid_environment_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="bogus")


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second
    get_settings.cache_clear()