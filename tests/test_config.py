"""
Unit tests for configuration settings.
"""

from src.config.settings import settings, Settings


def test_settings_initialization() -> None:
    assert settings.APP_NAME == "Procurement AI Assistant"
    assert "postgresql+asyncpg://" in settings.ASYNC_DATABASE_URI
    assert "redis://" in settings.REDIS_URI
    assert settings.MAX_UPLOAD_SIZE_MB == 10


def test_custom_settings_instantiation() -> None:
    custom_settings = Settings(
        POSTGRES_USER="test_user",
        POSTGRES_PASSWORD="test_password",
        POSTGRES_SERVER="test_host",
        POSTGRES_PORT=5433,
        POSTGRES_DB="test_db",
    )
    assert (
        custom_settings.ASYNC_DATABASE_URI
        == "postgresql+asyncpg://test_user:test_password@test_host:5433/test_db"
    )
