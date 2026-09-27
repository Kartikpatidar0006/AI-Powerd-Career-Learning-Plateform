"""
API Gateway configuration.

Defines service URLs and CORS settings loaded from environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """API Gateway settings loaded from environment variables."""

    APP_NAME: str = "API Gateway"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Internal service URLs
    AUTH_SERVICE_URL: str = Field(
        default="http://auth-service:8001",
        description="Base URL for the internal auth service",
    )

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
