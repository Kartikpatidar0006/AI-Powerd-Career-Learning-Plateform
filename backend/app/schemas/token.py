"""
backend/app/schemas/token.py
============================
Pydantic v2 schemas for JWT token responses and payload structures.

This module defines the data contracts that flow between the authentication
layer (``app/core/security.py``) and the HTTP response layer.  It covers
three distinct responsibilities:

  TokenResponse
    The JSON body returned to the client after a successful login or token
    refresh.  Contains both the access token (short-lived) and the refresh
    token (long-lived) together with standard OAuth2 metadata.

  AccessTokenResponse
    A slimmer variant used when only an access token is reissued (e.g. after
    a silent token refresh via the refresh endpoint).

  TokenPayload
    A typed view of the decoded JWT payload produced by
    ``app/core/security.decode_token()``.  Used by FastAPI dependencies to
    extract and validate the ``sub`` and ``type`` claims with full type safety.

Design notes:
  - All schemas are **read-only** (response-side): no write validators or
    password fields here.
  - No ``ConfigDict(from_attributes=True)`` is needed — these schemas are
    built directly from dicts/primitives, never from ORM instances.
  - ``token_type`` is always ``"bearer"`` per RFC 6750.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Union

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Full token pair — returned on initial login / registration
# ─────────────────────────────────────────────────────────────────────────────


class TokenResponse(BaseModel):
    """Full OAuth2-style token pair returned after a successful login.

    This is the primary response body for ``POST /api/v1/auth/login``.  It
    includes both token strings and the OAuth2 ``token_type`` field so that
    HTTP clients (and OpenAPI-generated clients) can immediately use the
    ``Authorization: Bearer <access_token>`` pattern without any extra parsing.

    Attributes:
        access_token: A signed, compact JWT for authenticating API requests.
            Short-lived (default 30 min, see ``ACCESS_TOKEN_EXPIRE_MINUTES``).
        refresh_token: A signed, compact JWT used solely to obtain new access
            tokens without re-authentication.  Long-lived (default 7 days, see
            ``REFRESH_TOKEN_EXPIRE_DAYS``).  Should be stored in an HttpOnly
            cookie on the client.
        token_type: Always ``"bearer"`` — the OAuth2 token scheme (RFC 6750).

    Example JSON::

        {
            "access_token":  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type":    "bearer"
        }
    """

    access_token: str = Field(
        ...,
        description="Short-lived JWT for authenticating API requests.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyJ9.sig"],
    )
    refresh_token: str = Field(
        ...,
        description="Long-lived JWT used to obtain new access tokens.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyJ9.sig"],
    )
    token_type: Literal["bearer"] = Field(
        default="bearer",
        description="OAuth2 token scheme — always 'bearer' (RFC 6750).",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Slim access-token-only response — returned on token refresh
# ─────────────────────────────────────────────────────────────────────────────


class AccessTokenResponse(BaseModel):
    """Slim response containing only a new access token.

    Returned by ``POST /api/v1/auth/refresh`` after the caller submits a valid
    refresh token.  The refresh token itself is not reissued here — token
    rotation (invalidating the old refresh token and issuing a new one) is an
    optional enhancement handled at the service layer.

    Attributes:
        access_token: A freshly signed, short-lived JWT.
        token_type: Always ``"bearer"`` (RFC 6750).

    Example JSON::

        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type":   "bearer"
        }
    """

    access_token: str = Field(
        ...,
        description="Freshly issued short-lived JWT.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyJ9.sig"],
    )
    token_type: Literal["bearer"] = Field(
        default="bearer",
        description="OAuth2 token scheme — always 'bearer' (RFC 6750).",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Decoded JWT payload — used internally by FastAPI dependencies
# ─────────────────────────────────────────────────────────────────────────────


class TokenPayload(BaseModel):
    """Typed representation of the decoded JWT payload.

    Used by FastAPI security dependencies (e.g. ``get_current_user``) to
    validate and access JWT claims after ``decode_token()`` succeeds.  The
    ``sub`` claim is typed as ``str | int`` to match the union type accepted by
    ``create_access_token`` / ``create_refresh_token`` in ``security.py``.

    Attributes:
        sub: Subject claim — the principal the token represents (typically the
            user's UUID as a string, e.g. ``"550e8400-e29b-41d4-a716-446655440000"``).
        type: Token type discriminator — ``"access"`` or ``"refresh"``.
            Dependencies use this to reject a refresh token when an access
            token is required (and vice versa), even if both are cryptographically
            valid for the same ``SECRET_KEY``.
        exp: Expiry timestamp — UTC Unix timestamp after which the token is
            invalid.  ``python-jose`` validates this automatically; this field
            is provided for completeness and downstream logging.
        iat: Issued-at timestamp — UTC Unix timestamp when the token was minted.
            Useful for token-age checks and reuse-detection heuristics.

    Example::

        payload = decode_token(raw_token)   # returns dict
        token_data = TokenPayload(**payload)
        user_id = token_data.sub
    """

    sub: Union[str, int] = Field(
        ...,
        description=(
            "Subject — identifies the principal (usually user UUID as string)."
        ),
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    type: Literal["access", "refresh"] = Field(
        ...,
        description="Token type discriminator: 'access' or 'refresh'.",
        examples=["access"],
    )
    exp: datetime = Field(
        ...,
        description="Expiry — UTC datetime after which the token must be rejected.",
    )
    iat: datetime = Field(
        ...,
        description="Issued-at — UTC datetime when the token was minted.",
    )
