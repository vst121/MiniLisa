"""
Application Configuration Module using Pydantic Settings.
Loads configuration from environment variables and .env file.
"""

from pathlib import Path
from typing import List, Literal
from pydantic import Field, PostgresDsn, RedisDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App Settings
    APP_NAME: str = "Procurement AI Assistant"
    ENV: Literal["development", "staging", "production", "testing"] = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "change-this-ultra-secure-secret-key-in-production-32chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Database Settings (PostgreSQL + pgvector)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "procurement_user"
    POSTGRES_PASSWORD: str = "procurement_pass"
    POSTGRES_DB: str = "procurement_ai_db"
    DATABASE_URL: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ASYNC_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Redis Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    EVENT_BUS_TYPE: Literal["redis", "memory"] = "redis"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def REDIS_URI(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # LLM Settings (LiteLLM)
    OPENAI_API_KEY: str = "sk-proj-mock-or-real-key"
    LLM_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_MAX_RETRIES: int = 3
    LLM_TIMEOUT: float = 60.0

    # Observability & Telemetry
    ENABLE_TELEMETRY: bool = True
    LANGFUSE_PUBLIC_KEY: str = "lf_pk_mock"
    LANGFUSE_SECRET_KEY: str = "lf_sk_mock"
    LANGFUSE_HOST: str = "http://localhost:3000"

    # Uploads & Storage
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_FILE_TYPES: List[str] = Field(default_factory=lambda: ["pdf"])
    UPLOAD_DIR: Path = Path("storage/uploads")

    def create_upload_dir(self) -> None:
        """Ensure upload directory exists on startup."""
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# Global settings singleton instance
settings = Settings()
