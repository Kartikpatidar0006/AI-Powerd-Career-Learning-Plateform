"""
Shared security.py for Catalog, Learning, Interview, Progress, Notification, Dashboard BFF.
These services ONLY validate JWTs (no password hashing).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)
_EXPIRED_TOKEN_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Token has expired.",
    headers={"WWW-Authenticate": "Bearer"},
)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT, returning its payload."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except ExpiredSignatureError:
        logger.info("JWT expired.")
        raise _EXPIRED_TOKEN_EXCEPTION
    except JWTError as exc:
        logger.warning("JWT invalid: %s", type(exc).__name__)
        raise _CREDENTIALS_EXCEPTION
