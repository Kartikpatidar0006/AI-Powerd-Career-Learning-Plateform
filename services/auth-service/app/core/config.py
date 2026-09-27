"""
Core configuration module for the auth service.

Uses pydantic-settings for environment-based configuration with validation.
All settings are loaded from environment variables with sensible defaults
for development.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Auth Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://auth_user:auth_pass@postgres-auth:5432/auth_db",
        description="Async PostgreSQL connection string",
    )

    # JWT Configuration
    JWT_SECRET_KEY: str = Field(
        default="change-me-in-production-use-a-strong-secret",
        description="Secret key for signing JWT tokens",
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
