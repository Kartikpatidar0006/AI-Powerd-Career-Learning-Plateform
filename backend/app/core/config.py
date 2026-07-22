"""
backend/app/core/config.py
--------------------------
Central application configuration powered by pydantic-settings.

Why pydantic-settings?
  - Automatic type coercion and validation of environment variables.
  - Native support for .env file loading (no manual dotenv calls needed).
  - IDE-friendly: full autocomplete and type checking on settings fields.

Pattern used:
  - `Settings` is a pydantic BaseSettings class that reads from the environment
    and from the `.env` file located at the backend root.
  - `get_settings()` is decorated with `@lru_cache` so the Settings object is
    constructed exactly once per process (singleton) — safe for FastAPI's
    dependency injection system.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ------------------------------------------------------------------ #
    # Project metadata                                                     #
    # ------------------------------------------------------------------ #
    PROJECT_NAME: str = "AI Powered Career Learning Platform"
    PROJECT_VERSION: str = "0.1.0"
    PROJECT_DESCRIPTION: str = (
        "Backend API for the AI-powered career learning and interview platform."
    )
    API_V1_STR: str = "/api/v1"

    # ------------------------------------------------------------------ #
    # Runtime environment                                                  #
    # ------------------------------------------------------------------ #
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = True

    # ------------------------------------------------------------------ #
    # Security                                                             #
    # ------------------------------------------------------------------ #
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ------------------------------------------------------------------ #
    # Database                                                             #
    # ------------------------------------------------------------------ #
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "career_platform"

    # Assembled DSN — built automatically from the individual parts above.
    # Declared as optional so pydantic does not expect it from .env.
    DATABASE_URL: str | None = None

    @model_validator(mode="after")
    def assemble_database_url(self) -> "Settings":
        """Build the PostgreSQL DSN if not explicitly provided via DATABASE_URL."""
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+psycopg2://"
                f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}"
                f"/{self.POSTGRES_DB}"
            )
        return self

    # ------------------------------------------------------------------ #
    # CORS                                                                 #
    # ------------------------------------------------------------------ #
    # Accept a comma-separated string from .env, e.g.:
    #   BACKEND_CORS_ORIGINS=http://localhost:3000,http://localhost:5173
    # Accepts either a JSON array or a comma-separated string from .env.
    # Annotated as `str | list[str]` so pydantic-settings v2 skips its
    # automatic JSON-decode step and lets the field_validator handle both formats.
    BACKEND_CORS_ORIGINS: str | list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        """Allow BACKEND_CORS_ORIGINS to be a comma-separated string or a list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return value
        raise ValueError(
            "BACKEND_CORS_ORIGINS must be a list or a comma-separated string."
        )

    # ------------------------------------------------------------------ #
    # SQLAlchemy engine tuning                                             #
    # ------------------------------------------------------------------ #
    # Pool size: number of persistent connections kept open.
    DB_POOL_SIZE: int = 10
    # Max overflow: extra connections allowed beyond pool_size under load.
    DB_MAX_OVERFLOW: int = 20
    # Seconds to wait for a connection before raising a timeout error.
    DB_POOL_TIMEOUT: int = 30
    # Recycle connections older than this (seconds) to prevent stale connections.
    DB_POOL_RECYCLE: int = 1800
    # Echo raw SQL to stdout — disable in production.
    DB_ECHO: bool = False

    # ------------------------------------------------------------------ #
    # Pydantic-settings configuration                                      #
    # ------------------------------------------------------------------ #
    model_config = SettingsConfigDict(
        # Resolved relative to the CWD when the process starts (backend/).
        env_file=".env",
        env_file_encoding="utf-8",
        # Silently ignore extra env vars present in .env that are not declared.
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.

    FastAPI dependency injection usage:
        from fastapi import Depends
        from app.core.config import get_settings, Settings

        def my_route(s: Settings = Depends(get_settings)):
            ...

    Direct usage (e.g., db/session.py):
        from app.core.config import settings
    """
    return Settings()


# Convenience module-level alias — import this for non-DI usage.
#   from app.core.config import settings
settings: Settings = get_settings()
