"""
Pydantic v2 schemas for authentication request/response validation.

Defines strict input validation for signup, login, token refresh,
logout, and structured response models for API consumers.
"""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ──────────────────────────────────────────────
# Request Schemas
# ──────────────────────────────────────────────


class UserSignupRequest(BaseModel):
    """Schema for user registration requests."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (8-128 characters, must contain at least one letter and one number)",
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """
        Enforce password strength requirements.

        Rules:
            - Minimum 8 characters (handled by Field min_length)
            - At least one letter (a-z or A-Z)
            - At least one digit (0-9)
        """
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "secureP@ss123",
            }
        }
    )


class UserLoginRequest(BaseModel):
    """Schema for user login requests."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "secureP@ss123",
            }
        }
    )


class TokenRefreshRequest(BaseModel):
    """Schema for token refresh requests."""

    refresh_token: str = Field(..., description="Valid refresh token")


class LogoutRequest(BaseModel):
    """Schema for logout requests."""

    refresh_token: str | None = Field(
        default=None,
        description="Optional specific refresh token to revoke. If omitted, all tokens are revoked.",
    )


# ──────────────────────────────────────────────
# Response Schemas
# ──────────────────────────────────────────────


class UserResponse(BaseModel):
    """Schema for user data in API responses."""

    id: UUID
    email: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Schema for authentication token responses."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    """Generic message response schema."""

    message: str
    detail: str | None = None
