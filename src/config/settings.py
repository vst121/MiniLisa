"""
Application Configuration Module using Pydantic Settings.
Loads configuration from environment variables and .env file.
"""

from pathlib import Path
from typing import Any, List, Literal

from pydantic import Field, field_validator, computed_field
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
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    API_V1_STR: str = "/api/v1"
    REQUIRE_AUTHENTICATION: bool = True
    SECRET_KEY: str = "replace-with-secure-random-key-for-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    CORS_ALLOW_ORIGINS: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )

    @field_validator("ALLOWED_FILE_TYPES", "CORS_ALLOW_ORIGINS", mode="before")
    @classmethod
    def parse_string_list(cls, value: Any) -> List[str] | Any:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                import json

                try:
                    parsed = json.loads(text)
                    return parsed if isinstance(parsed, list) else [parsed]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

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
    EVENT_BUS_TYPE: Literal["redis", "memory"] = "memory"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def REDIS_URI(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # LLM Settings (LiteLLM)
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "ollama_chat/llama3.1:8b"
    EMBEDDING_MODEL: str = "ollama/nomic-embed-text"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
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
    WORKFLOW_CHECKPOINT_DIR: Path = Path("storage/checkpoints")

    def create_upload_dir(self) -> None:
        """Ensure upload directory exists on startup."""
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.WORKFLOW_CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


# Global settings singleton instance
settings = Settings()
