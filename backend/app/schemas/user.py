"""
backend/app/schemas/user.py
============================
Pydantic v2 schemas for user registration and user read/response operations.

This module defines the full schema hierarchy for the ``User`` domain, following
the layered pattern:

  ┌─────────────────────────────────────────────────────────────────────────┐
  │  UserBase          — shared fields (full_name, email)                   │
  │    └── UserCreate  — + password (write-only, plain-text)                │
  │    └── UserUpdate  — all fields optional (PATCH semantics)              │
  │    └── UserAdminUpdate — superuser-only fields (is_active, is_verified) │
  │                                                                         │
  │  UserResponse      — safe read model (no password_hash)                 │
  │    └── UserPublicResponse — minimal public profile (id, full_name only) │
  └─────────────────────────────────────────────────────────────────────────┘

Key design decisions:
  - ``password_hash`` is **never** present in any response schema.  Passwords
    appear only in ``UserCreate`` as ``password`` (plain-text, write-only).
  - ``UserResponse`` uses ``ConfigDict(from_attributes=True)`` so FastAPI can
    serialise SQLAlchemy ``User`` ORM instances directly.
  - Email is normalised to lowercase via a ``field_validator`` to ensure
    consistent storage and lookup behaviour.
  - ``uuid.UUID`` is used for the ``id`` field, matching the ORM column type,
    so FastAPI serialises it as a string UUID in JSON automatically.
  - No business logic, no database access — pure data contracts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Base — shared read/write fields
# ─────────────────────────────────────────────────────────────────────────────


class UserBase(BaseModel):
    """Shared fields present in both request and response schemas.

    ``UserBase`` is an abstract base — never used directly as a request or
    response body.  It centralises field definitions so that ``UserCreate``,
    ``UserUpdate``, and ``UserResponse`` stay DRY.

    Attributes:
        full_name: The user's display name shown in the UI.  Not a login
            identifier.  Accepts names up to 255 characters including
            multi-part surnames, honorifics, and Unicode characters
            (e.g. ``"Dr. María García López"``).
        email: The user's primary login identifier.  Validated as a proper
            email address by Pydantic's ``EmailStr`` (uses the ``email-validator``
            library under the hood).  Normalised to lowercase on input to
            ensure consistent storage regardless of how the user typed it.
    """

    full_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User's display name (1–255 characters, Unicode allowed).",
        examples=["Alice Nguyen"],
    )
    email: EmailStr = Field(
        ...,
        description="Primary login identifier — must be a valid email address.",
        examples=["alice@example.com"],
    )

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        """Lowercase and strip the email address before EmailStr validation.

        Ensures that ``Alice@Example.COM`` and ``alice@example.com`` are
        treated as the same account, consistent with the database's unique
        index on the email column.  Running in ``mode="before"`` means the
        value is lowercased *before* ``EmailStr`` parses it, so the
        validated result is already fully lowercased.

        Args:
            value: The raw email string from the request body.

        Returns:
            The lowercased, whitespace-stripped email string.
        """
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        """Strip leading/trailing whitespace from full_name.

        Args:
            value: The raw full_name string from the request body.

        Returns:
            The stripped full_name string.
        """
        if isinstance(value, str):
            return value.strip()
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Create — registration request body
# ─────────────────────────────────────────────────────────────────────────────


class UserCreate(UserBase):
    """Request body for user registration (``POST /api/v1/auth/register``).

    Extends ``UserBase`` with a plain-text ``password`` field.  The password
    is never stored in this form — the service layer calls
    ``app/core/security.hash_password(schema.password)`` and writes only the
    resulting hash to ``users.password_hash``.

    Validation:
        - ``full_name``: 1–255 characters (inherited from ``UserBase``).
        - ``email``: valid email format, normalised to lowercase.
        - ``password``: 8–128 characters.  OWASP recommends a minimum of 8;
          128 is the maximum accepted to prevent denial-of-service via
          extremely long bcrypt inputs (bcrypt truncates at 72 bytes anyway,
          but validation here provides a clear error message).

    Attributes:
        full_name: Display name (inherited).
        email: Login identifier (inherited).
        password: Plain-text password.  Validated for length only — complexity
            rules (uppercase, digit, symbol) can be added via a
            ``field_validator`` if required by the security policy.

    Example JSON::

        {
            "full_name": "Alice Nguyen",
            "email":     "alice@example.com",
            "password":  "MyStr0ngP@ss!"
        }
    """

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description=(
            "Plain-text password (8–128 characters).  "
            "Hashed with bcrypt before storage — never persisted as-is."
        ),
        examples=["MyStr0ngP@ss!"],
        repr=False,   # Omit from __repr__ to prevent accidental log leaks.
    )


# ─────────────────────────────────────────────────────────────────────────────
# Update — partial self-service profile edit (PATCH semantics)
# ─────────────────────────────────────────────────────────────────────────────


class UserUpdate(BaseModel):
    """Request body for a partial user profile update (``PATCH /api/v1/users/me``).

    All fields are optional — the client sends only the fields it wants to
    change.  ``None`` means "leave this field unchanged"; the service layer
    skips ``None`` fields when building the SQL UPDATE statement.

    Attributes:
        full_name: New display name.  ``None`` = no change.
        email: New email address.  ``None`` = no change.  If provided, the
            service layer should trigger re-verification (set
            ``is_verified=False`` and send a verification email).

    Example JSON (change only the name)::

        { "full_name": "Alice M. Nguyen" }
    """

    full_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="New display name (1–255 characters).  Omit to keep unchanged.",
        examples=["Alice M. Nguyen"],
    )
    email: Optional[EmailStr] = Field(
        default=None,
        description=(
            "New email address.  Omit to keep unchanged.  "
            "Changing email triggers re-verification."
        ),
        examples=["alice.new@example.com"],
    )

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, value: Optional[str]) -> Optional[str]:
        """Lowercase and strip the email address before EmailStr validation.

        Args:
            value: The raw email string, or ``None``.

        Returns:
            Lowercased, stripped email string, or ``None``.
        """
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, value: Optional[str]) -> Optional[str]:
        """Strip whitespace from full_name if provided.

        Args:
            value: The raw full_name string, or ``None``.

        Returns:
            Stripped full_name string, or ``None``.
        """
        if isinstance(value, str):
            return value.strip()
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Admin update — superuser-only fields
# ─────────────────────────────────────────────────────────────────────────────


class UserAdminUpdate(UserUpdate):
    """Request body for administrative user updates (superuser-only route).

    Extends ``UserUpdate`` with privileged fields that regular users must not
    be able to change themselves.  Only routes protected by a superuser
    dependency should accept this schema.

    Attributes:
        full_name: Inherited from ``UserUpdate``.
        email: Inherited from ``UserUpdate``.
        is_active: Activate or deactivate the account.  Setting to ``False``
            performs a soft-delete — the user can no longer log in, but their
            data is preserved.
        is_verified: Manually mark the email as verified (e.g. after a
            support-assisted verification check).

    Example JSON (suspend an account)::

        { "is_active": false }
    """

    is_active: Optional[bool] = Field(
        default=None,
        description=(
            "Set to false to soft-delete / suspend the account.  "
            "Omit to keep unchanged."
        ),
        examples=[False],
    )
    is_verified: Optional[bool] = Field(
        default=None,
        description=(
            "Manually mark the email address as verified.  "
            "Omit to keep unchanged."
        ),
        examples=[True],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Response — safe user representation (no secrets)
# ─────────────────────────────────────────────────────────────────────────────


class UserResponse(BaseModel):
    """Safe, full user representation returned by authenticated API endpoints.

    This schema mirrors every column of the ``users`` table **except**
    ``password_hash``, which must never leave the server.  FastAPI uses this
    schema as the ``response_model`` for routes that return user data.

    ``ConfigDict(from_attributes=True)`` enables Pydantic to populate this
    schema directly from a SQLAlchemy ``User`` ORM instance, so the service
    layer can do::

        user_orm = db.get(User, user_id)
        return UserResponse.model_validate(user_orm)

    Attributes:
        id: The user's UUID primary key.  Serialised as a string in JSON
            (``"550e8400-e29b-41d4-a716-446655440000"``).
        full_name: Display name.
        email: Login identifier / contact email.
        role_id: UUID of the assigned role, or ``None`` if no role has been
            assigned yet.
        is_active: ``True`` if the account is active; ``False`` if suspended.
        is_verified: ``True`` once the user has confirmed their email address.
        created_at: UTC timestamp of account creation.
        updated_at: UTC timestamp of the last row modification.

    Example JSON::

        {
            "id":          "550e8400-e29b-41d4-a716-446655440000",
            "full_name":   "Alice Nguyen",
            "email":       "alice@example.com",
            "role_id":     null,
            "is_active":   true,
            "is_verified": false,
            "created_at":  "2024-03-01T12:00:00Z",
            "updated_at":  "2024-03-15T09:30:00Z"
        }
    """

    model_config = ConfigDict(
        from_attributes=True,       # Allow ORM model → schema coercion.
        populate_by_name=True,      # Accept both alias and field name.
    )

    id: uuid.UUID = Field(
        ...,
        description="User UUID primary key.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    full_name: str = Field(
        ...,
        description="User's display name.",
        examples=["Alice Nguyen"],
    )
    email: EmailStr = Field(
        ...,
        description="Primary login identifier and contact email.",
        examples=["alice@example.com"],
    )
    role_id: Optional[uuid.UUID] = Field(
        default=None,
        description="UUID of the assigned role, or null if no role assigned.",
        examples=[None],
    )
    is_active: bool = Field(
        ...,
        description="False if the account has been suspended (soft-deleted).",
        examples=[True],
    )
    is_verified: bool = Field(
        ...,
        description="True once the user has confirmed their email address.",
        examples=[False],
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp of account creation (immutable).",
    )
    updated_at: datetime = Field(
        ...,
        description="UTC timestamp of the most recent row modification.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public profile — minimal, intentionally restricted view
# ─────────────────────────────────────────────────────────────────────────────


class UserPublicResponse(BaseModel):
    """Minimal public user profile for contexts where full details are inappropriate.

    Used in scenarios such as listing participants in a shared session,
    attributing a comment, or displaying a user's name in a shared workspace —
    where the caller must know *who* someone is but should not receive their
    email, account status, or timestamps.

    Attributes:
        id: The user's UUID — allows the client to link back to the full
            profile if the caller has the appropriate permissions.
        full_name: Display name shown in UI.

    Example JSON::

        {
            "id":        "550e8400-e29b-41d4-a716-446655440000",
            "full_name": "Alice Nguyen"
        }
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(
        ...,
        description="User UUID primary key.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    full_name: str = Field(
        ...,
        description="User's display name.",
        examples=["Alice Nguyen"],
    )
