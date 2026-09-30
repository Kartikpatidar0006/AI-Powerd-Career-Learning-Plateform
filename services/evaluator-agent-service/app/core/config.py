"""
Core configuration module for the evaluator agent service.

Uses pydantic-settings for environment-based configuration with validation.
Configures database connection, LLM provider selection, GitHub API token,
and internal service communication (X-Internal-Token pattern).
"""

from typing import Literal
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Evaluator Agent Service"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = Field(
        default="production",
        description="Application environment: development or production",
    )
    DEBUG: bool = False

    # Database (Dedicated PostgreSQL for evaluator — never shared with other DBs)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://evaluator_user:evaluator_pass@postgres-evaluator:5432/evaluator_db",
        description="Async PostgreSQL connection string for evaluator service",
    )

    # Internal service communication & defense in depth
    ROADMAP_SERVICE_INTERNAL_URL: str = Field(
        default="http://roadmap-agent-service:8003",
        description="Internal URL for roadmap-agent-service (not via gateway)",
    )
    INTERNAL_SERVICE_TOKEN: str = Field(
        default="change-me-internal-token",
        description="Shared secret for service-to-service authentication (X-Internal-Token)",
    )
    GATEWAY_SERVICE_TOKEN: str = Field(
        default="change-me-gateway-token",
        description="Shared secret header X-Gateway-Token sent by API Gateway for defense in depth",
    )

    # GitHub API
    GITHUB_API_TOKEN: str = Field(
        default="",
        description="GitHub Personal Access Token for higher rate limits (no token = 60 req/hr, with = 5000 req/hr)",
    )
    GITHUB_MAX_SOURCE_FILES: int = Field(
        default=15,
        description="Maximum number of source files to fetch contents for (beyond README)",
    )
    GITHUB_FILE_SIZE_CAP_BYTES: int = Field(
        default=51200,  # 50 KB
        description="Skip fetching file contents for files larger than this size",
    )
    GITHUB_COMMIT_HISTORY_LIMIT: int = Field(
        default=30,
        description="Number of recent commits to fetch from the default branch",
    )

    # Evaluation configuration
    PASS_SCORE: float = Field(
        default=60.0,
        description="Threshold score (0-100) required for an evaluation to be marked passed",
    )
    LLM_CONTENT_CHAR_LIMIT: int = Field(
        default=12000,
        description="Maximum characters of repo content injected into the LLM prompt. Truncated if exceeded.",
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
