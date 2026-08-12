"""
services/auth-service/app/core/security.py
-------------------------------------------
Security utilities for Auth Service using bcrypt and python-jose.
"""

from __future__ import annotations

import logging
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Any, Union

from fastapi import HTTPException, status
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import settings

logger: logging.Logger = logging.getLogger(__name__)

__all__: list[str] = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "JWTError",
]

_ACCESS_TOKEN_TYPE: str = "access"
_REFRESH_TOKEN_TYPE: str = "refresh"

_CREDENTIALS_EXCEPTION: HTTPException = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)
_EXPIRED_TOKEN_EXCEPTION: HTTPException = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Token has expired.",
    headers={"WWW-Authenticate": "Bearer"},
)


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception as exc:
        logger.warning("Password verification error: %s", exc)
        return False


def _build_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    now: datetime = datetime.now(tz=timezone.utc)
    expire: datetime = now + expires_delta
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    delta: timedelta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _build_token(subject=subject, token_type=_ACCESS_TOKEN_TYPE, expires_delta=delta)


def create_refresh_token(subject: str, expires_delta: timedelta | None = None) -> str:
    delta: timedelta = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _build_token(subject=subject, token_type=_REFRESH_TOKEN_TYPE, expires_delta=delta)


def decode_token(token: str, expected_type: str = _ACCESS_TOKEN_TYPE) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != expected_type:
            raise _CREDENTIALS_EXCEPTION
        return payload
    except ExpiredSignatureError as exc:
        raise _EXPIRED_TOKEN_EXCEPTION from exc
    except JWTError as exc:
        raise _CREDENTIALS_EXCEPTION from exc
