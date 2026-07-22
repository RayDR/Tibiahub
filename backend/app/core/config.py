"""Authoritative application configuration.

Database settings are intentionally resolved from an absolute backend path so
API, scheduler, Alembic, and scripts behave identically regardless of cwd.
"""
from pathlib import Path
from typing import List, Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment and ``backend/.env``."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        case_sensitive=True,
        extra="ignore",
    )

    APP_ENV: Literal["development", "production", "test"] = "development"

    # API Configuration
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8001
    PUBLIC_DOMAIN: str = "tibiahub.domoforge.com"

    # Security
    SECRET_KEY: str = "changethis-to-a-secure-secret-key-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # Database. There is deliberately no runtime default.
    DATABASE_URL: str | None = None
    DATABASE_POOL_SIZE: int = Field(5, ge=1, le=50)
    DATABASE_MAX_OVERFLOW: int = Field(10, ge=0, le=100)
    DATABASE_POOL_RECYCLE_SECONDS: int = Field(1800, ge=60)
    DATABASE_CONNECT_TIMEOUT_SECONDS: int = Field(10, ge=1, le=60)
    DATABASE_STATEMENT_TIMEOUT_MS: int = Field(30_000, ge=1_000)
    DATABASE_IDLE_TRANSACTION_TIMEOUT_MS: int = Field(60_000, ge=1_000)

    # CORS - can be a comma-separated string or JSON list
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://develop.domoforge.com,https://develop.domoforge.com,http://tibiahub.domoforge.com,https://tibiahub.domoforge.com"

    # Tibia Validation
    TIBIA_VALIDATION_ENABLED: bool = True
    TIBIA_VALIDATION_STRICT: bool = False

    # External API configuration
    USE_MOCK_DATA: bool = False
    EXTERNAL_API_CACHE_TTL_SECONDS: int = 900
    EXTERNAL_API_LIST_CACHE_TTL_SECONDS: int = 3600
    TIBIADATA_BASE_URL: str = "https://api.tibiadata.com/v4"
    TIBIAWIKI_API_URL: str = "https://tibia.fandom.com/api.php"
    TIBIAWIKI_BASE_PAGE_URL: str = "https://tibia.fandom.com/wiki"
    TIBIAWIKI_USER_AGENT: str = "TibiaHub/2026.05 (+https://tibiahub.domoforge.com)"
    BESTIARY_BOOTSTRAP_ENABLED: bool = False
    BESTIARY_BOOTSTRAP_MIN_COUNT: int = 100
    RAFFLE_DEFAULT_GUILD_NAME: str = ""
    RAFFLE_SCHEDULER_ENABLED: bool = False
    RAFFLE_SCHEDULER_POLL_SECONDS: int = Field(30, ge=5, le=3600)
    RAFFLE_SCHEDULER_LEASE_SECONDS: int = Field(300, ge=30, le=3600)
    RAFFLE_SCHEDULER_MAX_RETRIES: int = Field(5, ge=0, le=20)
    RAFFLE_SCHEDULER_INITIAL_RETRY_SECONDS: int = Field(60, ge=5, le=3600)
    RAFFLE_SCHEDULER_WORKER_ID: str = "raffle-scheduler-1"
    IMAGE_CACHE_MAX_AGE_SECONDS: int = 86400
    RESET_PASSWORD_URL: str = "https://tibiahub.domoforge.com/reset-password"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False

    @model_validator(mode="after")
    def validate_database(self) -> "Settings":
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL is required; TibiaHub has no default runtime database")
        dialect = make_url(self.DATABASE_URL).get_backend_name()
        if dialect != "postgresql" and not (self.APP_ENV == "test" and dialect == "sqlite"):
            raise ValueError("TibiaHub runtime requires PostgreSQL; SQLite is allowed only with APP_ENV=test")
        return self

    @property
    def database_url(self) -> URL:
        """Return a sync SQLAlchemy URL without ever rendering credentials."""
        url = make_url(self.DATABASE_URL or "")
        if url.drivername == "postgresql+asyncpg":
            return url.set(drivername="postgresql+psycopg2")
        return url

    @property
    def database_name(self) -> str:
        return self.database_url.database or ""

    @property
    def cors_origins_list(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        return self.CORS_ORIGINS

    @property
    def smtp_from_address(self) -> str:
        return self.SMTP_FROM or self.SMTP_USER or "no-reply@domoforge.com"

    @property
    def smtp_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_USER and self.SMTP_PASSWORD)


settings = Settings()
