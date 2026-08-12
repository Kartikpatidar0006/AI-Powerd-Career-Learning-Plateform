"""
gateway/app/core/config.py
--------------------------
Settings for the API Gateway.
Reads from environment / .env file.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    # ── Identity ──────────────────────────────────────────────────────────── #
    PROJECT_NAME: str = "AI Career Hub — API Gateway"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # ── Runtime ───────────────────────────────────────────────────────────── #
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # ── JWT (shared secret — same key used by all services) ───────────────── #
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"

    # ── Downstream service URLs ────────────────────────────────────────────── #
    AUTH_SERVICE_URL: str = "http://localhost:8001"
    CATALOG_SERVICE_URL: str = "http://localhost:8002"
    LEARNING_SERVICE_URL: str = "http://localhost:8003"
    INTERVIEW_SERVICE_URL: str = "http://localhost:8004"
    PROGRESS_SERVICE_URL: str = "http://localhost:8005"
    NOTIFICATION_SERVICE_URL: str = "http://localhost:8006"
    DASHBOARD_SERVICE_URL: str = "http://localhost:8007"

    # ── CORS ──────────────────────────────────────────────────────────────── #
    BACKEND_CORS_ORIGINS: str | list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    # ── HTTP client timeout (seconds) ─────────────────────────────────────── #
    HTTP_TIMEOUT: float = 30.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> GatewaySettings:
    return GatewaySettings()


settings: GatewaySettings = get_settings()
