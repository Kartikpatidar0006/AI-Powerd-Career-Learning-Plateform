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
    PROFILE_SERVICE_URL: str = Field(
        default="http://profile-agent-service:8002",
        description="Base URL for the internal profile agent service",
    )
    ROADMAP_SERVICE_URL: str = Field(
        default="http://roadmap-agent-service:8003",
        description="Base URL for the internal roadmap agent service",
    )

    # JWT Verification
    JWT_SECRET_KEY: str = Field(
        default="change-me-in-production-use-a-strong-secret",
        description="Secret key for validating incoming JWT access tokens",
    )
    JWT_ALGORITHM: str = "HS256"

    # Gateway defense-in-depth token forwarded to downstream services
    GATEWAY_SERVICE_TOKEN: str = Field(
        default="change-me-gateway-token",
        description="Shared secret injected by Gateway into X-Gateway-Token header",
    )

    # Environment
    APP_ENV: str = Field(default="production", description="Application environment: production or development")

    # Timeouts
    DEFAULT_TIMEOUT: float = 30.0
    LLM_ROUTE_TIMEOUT: float = 75.0  # Exceeds LLM timeout (30s) + 1 retry (30s) + overhead

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
