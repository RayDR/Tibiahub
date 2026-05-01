"""
Configuration settings for the application
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings"""
    
    # API Configuration
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8001

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
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert CORS_ORIGINS string to list"""
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(',')]
        return self.CORS_ORIGINS
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
