"""
Core configuration module for the interview agent service.

Uses pydantic-settings for environment-based configuration with validation.
Configures database connection, LLM provider selection, API keys,
and internal service communication (X-Internal-Token and X-Gateway-Token).
"""

from typing import Literal
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Interview Agent Service"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = Field(
        default="production",
        description="Application environment: development or production",
    )
    DEBUG: bool = False

    # Database (Dedicated PostgreSQL for interview agent service)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://interview_user:interview_pass@postgres-interview:5432/interview_db",
        description="Async PostgreSQL connection string for interview service",
    )

    # Internal service communication & defense in depth
    ROADMAP_SERVICE_INTERNAL_URL: str = Field(
        default="http://roadmap-agent-service:8003",
        description="Internal URL for roadmap-agent-service (not via gateway)",
    )
    PROFILE_SERVICE_INTERNAL_URL: str = Field(
        default="http://profile-agent-service:8002",
        description="Internal URL for profile-agent-service (not via gateway)",
    )
    EVALUATOR_SERVICE_INTERNAL_URL: str = Field(
        default="http://evaluator-agent-service:8004",
        description="Internal URL for evaluator-agent-service (not via gateway)",
    )
    INTERNAL_SERVICE_TOKEN: str = Field(
        default="change-me-internal-token",
        description="Shared secret for service-to-service authentication (X-Internal-Token)",
    )
    GATEWAY_SERVICE_TOKEN: str = Field(
        default="change-me-gateway-token",
        description="Shared secret header X-Gateway-Token sent by API Gateway for defense in depth",
    )
    INTERVIEW_MAX_TURNS: int = Field(
        default=6,
        description="Maximum turns before generating closing remark and completing interview",
    )
    PROCTORING_MAX_VIOLATIONS: int = Field(
        default=3,
        description="Maximum proctoring violations before terminating the interview",
    )
    PROCTORING_RATE_LIMIT_PER_MINUTE: int = Field(
        default=20,
        description="Maximum proctoring events allowed per minute per session to prevent spam",
    )

    # LLM Configuration (Swappable provider abstraction — intentionally duplicated for service independence)
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
        default=60.0,
        description="Timeout in seconds for external LLM API calls",
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
