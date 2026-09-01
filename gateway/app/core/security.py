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


from fastapi.responses import JSONResponse

def _is_public(path: str, method: str = "GET") -> bool:
    """Return True if this path does not require authentication."""
    if path in PUBLIC_PATHS:
        return True
    # Allow docs sub-paths
    if path.startswith(("/api/v1/docs", "/api/v1/redoc", "/openapi")):
        return True
    # Allow public catalog read endpoints
    if method in ("GET", "HEAD") and (
        path.startswith("/api/v1/professions")
        or path.startswith("/api/v1/skills")
        or path.startswith("/api/v1/career-roadmaps")
        or path.startswith("/api/v1/roadmap-steps")
        or path.startswith("/api/v1/courses")
    ):
        return True
    return False


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate the JWT, returning its payload.
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
    """
    path = request.url.path

    if request.method == "OPTIONS" or _is_public(path, request.method):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()
            try:
                request.state.jwt_payload = decode_token(token)
            except Exception:
                pass
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Missing Bearer token."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.removeprefix("Bearer ").strip()
    try:
        payload = decode_token(token)
        request.state.jwt_payload = payload
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid token."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await call_next(request)
