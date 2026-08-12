"""
gateway/app/core/security.py
-----------------------------
JWT validation utilities for the API Gateway.

The gateway validates the JWT *signature and expiry* locally (no network call
to the Auth Service). This enables stateless, per-request auth at zero latency.

Only login / register / refresh requests are forwarded without validation.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

# Paths that are allowed without a valid JWT.
PUBLIC_PATHS: set[str] = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/health",
    "/",
    "/api/v1/openapi.json",
    "/api/v1/docs",
    "/api/v1/redoc",
}


def _is_public(path: str) -> bool:
    """Return True if this path does not require authentication."""
    if path in PUBLIC_PATHS:
        return True
    # Allow docs sub-paths
    if path.startswith(("/api/v1/docs", "/api/v1/redoc", "/openapi")):
        return True
    return False


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate the JWT, returning its payload.

    Raises
    ------
    HTTPException(401)
        If the token is missing, expired, or has an invalid signature.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": True},
        )
        return payload
    except JWTError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def validate_jwt_middleware(request: Request, call_next: Any) -> Any:
    """
    ASGI middleware that validates Bearer JWT for every non-public route.

    On success, the decoded payload is attached to `request.state.jwt_payload`
    so downstream proxy handlers can forward claims to services if needed.
    """
    path = request.url.path

    if request.method == "OPTIONS" or _is_public(path):
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.removeprefix("Bearer ").strip()
    payload = decode_token(token)
    request.state.jwt_payload = payload

    return await call_next(request)
