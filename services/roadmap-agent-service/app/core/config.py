"""
Core configuration module for the roadmap agent service.

Uses pydantic-settings for environment-based configuration with validation.
Configures database connection, LLM provider selection, API keys,
and internal service communication.
"""

from typing import Literal
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Roadmap Agent Service"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = Field(
        default="production",
        description="Application environment: development or production",
    )
    DEBUG: bool = False

    # Database (Dedicated PostgreSQL for roadmap-agent-service — never shared with profile DB)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://roadmap_user:roadmap_pass@postgres-roadmap:5432/roadmap_db",
        description="Async PostgreSQL connection string for roadmap service",
    )

    # Internal service communication & defense in depth
    PROFILE_SERVICE_INTERNAL_URL: str = Field(
        default="http://profile-agent-service:8002",
        description="Internal URL for profile-agent-service (not via gateway)",
    )
    EVALUATOR_SERVICE_INTERNAL_URL: str = Field(
        default="http://evaluator-agent-service:8004",
        description="Internal URL for evaluator-agent-service (Agent 3, not via gateway)",
    )
    INTERNAL_SERVICE_TOKEN: str = Field(
        default="change-me-internal-token",
        description="Shared secret for service-to-service authentication",
    )
    GATEWAY_SERVICE_TOKEN: str = Field(
        default="change-me-gateway-token",
        description="Shared secret header X-Gateway-Token sent by API Gateway for defense in depth",
    )

    # Evaluation configuration
    PASS_SCORE: int = Field(
        default=60,
        description="Threshold score (0-100) required for a task to be marked as passed",
    )
    MAX_REMEDIATION_ATTEMPTS: int = Field(
        default=3,
        description=(
            "Maximum number of remediation tasks per milestone. "
            "After this many consecutive failed evaluations on the same milestone, "
            "the milestone is marked needs_review and the student may advance."
        ),
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
