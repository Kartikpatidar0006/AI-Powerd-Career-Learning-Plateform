"""
backend/app/schemas/auth.py
============================
Pydantic v2 schemas for authentication request bodies.

This module defines the inbound data contracts for the authentication flow:

  LoginRequest
    The request body for ``POST /api/v1/auth/login``.  Accepts an email and
    a plain-text password.  FastAPI will also accept this endpoint via the
    standard OAuth2 ``application/x-www-form-urlencoded`` form using
    ``OAuth2PasswordRequestForm``; this schema covers the JSON variant.

  RefreshTokenRequest
    The request body for ``POST /api/v1/auth/refresh``.  Contains only the
    refresh token string.  (The access token itself is not sent here — the
    client uses it until it expires, then calls this endpoint.)

  PasswordChangeRequest
    The request body for ``POST /api/v1/auth/change-password`` (authenticated
    route).  Requires the current password for verification before hashing
    the new one — prevents account takeover if a session is stolen.

  PasswordResetRequest
    The request body for ``POST /api/v1/auth/reset-password``.  Used in the
    second step of a forgot-password flow: the caller provides the reset token
    received via email together with the new password.

Design notes:
  - All schemas are **write-side** (request bodies) — no ORM attributes, so
    ``ConfigDict(from_attributes=True)`` is deliberately omitted.
  - Plain-text passwords are validated for minimum length here; hashing is
    performed exclusively in ``app/core/security.hash_password()``.
  - Passwords are intentionally excluded from ``model_repr=True`` to prevent
    accidental logging.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing_extensions import Self


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    """Request body for user login (JSON variant).

    Carries the user's email and plain-text password.  After validation the
    service layer passes the password to ``verify_password()`` and returns a
    ``TokenResponse`` on success.

    Attributes:
        email: The user's registered email address.  Pydantic's ``EmailStr``
            validates RFC 5322 format and normalises the address to lowercase.
        password: The user's plain-text password.  Never stored — passed
            directly to ``app/core/security.verify_password()``.

    Example JSON::

        {
            "email":    "alice@example.com",
            "password": "MyStr0ngP@ss!"
        }
    """

    email: EmailStr = Field(
        ...,
        description="Registered email address of the user.",
        examples=["alice@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plain-text password (8–128 characters).  Never stored.",
        examples=["MyStr0ngP@ss!"],
        repr=False,   # Exclude from repr/logging to prevent accidental leaks.
    )

    model_config = {"str_strip_whitespace": True}

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        """Lowercase and strip the email address before EmailStr validation.

        Ensures consistent lookup against the database index regardless of
        the casing the user typed at login.

        Args:
            value: The raw email string from the request body.

        Returns:
            The lowercased, whitespace-stripped email string.
        """
        if isinstance(value, str):
            return value.strip().lower()
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Token refresh
# ─────────────────────────────────────────────────────────────────────────────


class RefreshTokenRequest(BaseModel):
    """Request body for ``POST /api/v1/auth/refresh``.

    The caller submits a valid (non-expired) refresh token obtained during
    login.  The server validates the token, confirms ``type == "refresh"``,
    and issues a new access token.

    Attributes:
        refresh_token: The raw JWT refresh token string.

    Example JSON::

        {
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        }
    """

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Valid JWT refresh token string.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"],
    )

    model_config = {"str_strip_whitespace": True}


# ─────────────────────────────────────────────────────────────────────────────
# Password change (authenticated)
# ─────────────────────────────────────────────────────────────────────────────


class PasswordChangeRequest(BaseModel):
    """Request body for an authenticated password change.

    Requires the user to provide their current password before the new one is
    accepted.  This prevents session-hijack attacks: a stolen access token
    alone is not enough to change the account password.

    Validation:
        - ``new_password`` must be at least 8 characters long.
        - ``new_password`` and ``confirm_password`` must match.
        - ``new_password`` must differ from ``current_password`` (prevents
          no-op changes that silently succeed).

    Attributes:
        current_password: The user's existing plain-text password.  Passed to
            ``verify_password()`` before any changes are committed.
        new_password: The desired new password.  Passed to ``hash_password()``
            on success.
        confirm_password: Confirmation field — must equal ``new_password``.
            Validated at the model level (not stored or processed further).

    Example JSON::

        {
            "current_password": "OldP@ss123",
            "new_password":     "NewStr0ng!99",
            "confirm_password": "NewStr0ng!99"
        }
    """

    current_password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="The user's current plain-text password for verification.",
        repr=False,
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="The desired new password (8–128 characters).",
        repr=False,
    )
    confirm_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Must match new_password exactly.",
        repr=False,
    )

    model_config = {"str_strip_whitespace": True}

    @model_validator(mode="after")
    def passwords_must_match_and_differ(self) -> Self:
        """Validate that new passwords match and differ from the current one.

        Raises:
            ValueError: If ``new_password`` != ``confirm_password``, or if
                ``new_password`` is identical to ``current_password``.

        Returns:
            The validated model instance.
        """
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password do not match.")
        if self.new_password == self.current_password:
            raise ValueError(
                "new_password must differ from the current password."
            )
        return self


# ─────────────────────────────────────────────────────────────────────────────
# Password reset (unauthenticated — forgot-password flow)
# ─────────────────────────────────────────────────────────────────────────────


class PasswordResetRequest(BaseModel):
    """Request body for the second step of the forgot-password flow.

    The caller supplies the one-time reset token received via email and their
    desired new password.  Token validation (expiry, single-use) is handled at
    the service layer.

    Attributes:
        token: The one-time password-reset token from the email link.
        new_password: The desired new password.
        confirm_password: Confirmation — must equal ``new_password``.

    Example JSON::

        {
            "token":            "abc123resettoken",
            "new_password":     "NewStr0ng!99",
            "confirm_password": "NewStr0ng!99"
        }
    """

    token: str = Field(
        ...,
        min_length=1,
        description="One-time password-reset token received via email.",
        examples=["abc123resettoken"],
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Desired new password (8–128 characters).",
        repr=False,
    )
    confirm_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Must match new_password exactly.",
        repr=False,
    )

    model_config = {"str_strip_whitespace": True}

    @model_validator(mode="after")
    def passwords_must_match(self) -> Self:
        """Validate that new_password and confirm_password are equal.

        Raises:
            ValueError: If the two password fields do not match.

        Returns:
            The validated model instance.
        """
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password do not match.")
        return self
