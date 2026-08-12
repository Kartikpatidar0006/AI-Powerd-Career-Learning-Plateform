"""
services/dashboard-bff/app/core/config.py
-------------------------------------------
Configuration for the Dashboard BFF (Backend-For-Frontend).
This service has NO own database — it aggregates data from other services.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Career Hub — Dashboard BFF"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # JWT (for validating tokens on incoming requests from frontend/gateway)
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"

    # Downstream service base URLs
    AUTH_SERVICE_URL: str = "http://localhost:8001"
    CATALOG_SERVICE_URL: str = "http://localhost:8002"
    LEARNING_SERVICE_URL: str = "http://localhost:8003"
    INTERVIEW_SERVICE_URL: str = "http://localhost:8004"
    PROGRESS_SERVICE_URL: str = "http://localhost:8005"
    NOTIFICATION_SERVICE_URL: str = "http://localhost:8006"

    # HTTP client timeout for downstream calls (seconds)
    HTTP_TIMEOUT: float = 15.0

    BACKEND_CORS_ORIGINS: str | list[str] = ["http://localhost:8000", "http://localhost:5173"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
