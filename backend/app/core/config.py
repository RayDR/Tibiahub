"""
Configuration settings for the application
"""
from pydantic_settings import BaseSettings
from typing import List
from pydantic import Field


class Settings(BaseSettings):
    """Application settings"""
    
    # API Configuration
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8001
    PUBLIC_DOMAIN: str = "tibiahub.domoforge.com"

    # Security
    SECRET_KEY: str = "changethis-to-a-secure-secret-key-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 1 week
    
    # Database
    DATABASE_URL: str = "sqlite:///./tibia_bestiary.db"
    
    # CORS - can be a comma-separated string or JSON list
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://develop.domoforge.com,https://develop.domoforge.com,http://tibiahub.domoforge.com,https://tibiahub.domoforge.com"
    
    # Tibia Validation
    TIBIA_VALIDATION_ENABLED: bool = True  # Enable/disable Tibia character validation
    TIBIA_VALIDATION_STRICT: bool = False  # If True, fail registration when API is down. If False, allow without validation

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
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert CORS_ORIGINS string to list"""
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(',')]
        return self.CORS_ORIGINS

    @property
    def smtp_from_address(self) -> str:
        return self.SMTP_FROM or self.SMTP_USER or "no-reply@domoforge.com"

    @property
    def smtp_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_USER and self.SMTP_PASSWORD)
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
