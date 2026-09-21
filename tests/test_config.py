"""
Unit tests for configuration settings.
"""

from src.config.settings import settings, Settings
from pydantic import ValidationError


def test_settings_initialization() -> None:
    assert settings.APP_NAME == "Procurement AI Assistant"
    assert "postgresql+asyncpg://" in settings.ASYNC_DATABASE_URI
    assert "redis://" in settings.REDIS_URI
    assert settings.MAX_UPLOAD_SIZE_MB == 10
    assert settings.REQUIRE_AUTHENTICATION is True
    assert settings.CORS_ALLOW_ORIGINS == ["http://localhost:3000", "http://localhost:5173"]


def test_custom_settings_instantiation() -> None:
    custom_settings = Settings(
        POSTGRES_USER="test_user",
        POSTGRES_PASSWORD="test_password",
        POSTGRES_SERVER="test_host",
        POSTGRES_PORT=5433,
        POSTGRES_DB="test_db",
        DATABASE_URL=None,
    )
    assert (
        custom_settings.ASYNC_DATABASE_URI
        == "postgresql+asyncpg://test_user:test_password@test_host:5433/test_db"
    )


def test_production_settings_reject_placeholder_secret() -> None:
    try:
        Settings(ENV="production", SECRET_KEY="change-this-secret-value-that-is-too-weak")
    except ValidationError as exc:
        assert "SECRET_KEY" in str(exc)
    else:
        raise AssertionError("Weak production secret should be rejected")


def test_production_settings_reject_disabled_authentication() -> None:
    try:
        Settings(
            ENV="production",
            SECRET_KEY="a" * 32,
            REQUIRE_AUTHENTICATION=False,
        )
    except ValidationError as exc:
        assert "REQUIRE_AUTHENTICATION" in str(exc)
    else:
        raise AssertionError("Disabled production authentication should be rejected")
