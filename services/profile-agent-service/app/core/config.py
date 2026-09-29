"""
Core configuration module for the profile agent service.

Uses pydantic-settings for environment-based configuration with validation.
Configures database connection, LLM provider selection, and API keys.
"""

from typing import Literal
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Profile Agent Service"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = Field(
        default="production",
        description="Application environment: development or production",
    )
    DEBUG: bool = False

    # Database (Dedicated PostgreSQL for profile-agent-service)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://profile_user:profile_pass@postgres-profile:5432/profile_db",
        description="Async PostgreSQL connection string for profile service",
    )

    # LLM Configuration (Swappable provider abstraction)
    LLM_PROVIDER: Literal["openai", "anthropic", "mock"] = Field(
        default="openai",
        description="Selected LLM provider: openai, anthropic, or mock for offline testing",
    )
    OPENAI_API_KEY: str = Field(
        default="",
        description="API key for OpenAI provider",
    )
    OPENAI_MODEL: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model identifier",
    )
    ANTHROPIC_API_KEY: str = Field(
        default="",
        description="API key for Anthropic provider",
    )
    ANTHROPIC_MODEL: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Anthropic model identifier",
    )
    LLM_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        description="Timeout in seconds for external LLM API calls",
    )

    # Internal service communication & defense in depth
    INTERNAL_SERVICE_TOKEN: str = Field(
        default="change-me-internal-token",
        description="Shared secret for service-to-service authentication (X-Internal-Token header)",
    )
    GATEWAY_SERVICE_TOKEN: str = Field(
        default="change-me-gateway-token",
        description="Shared secret header X-Gateway-Token sent by API Gateway for defense in depth",
    )

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
