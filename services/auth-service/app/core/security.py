"""
Security utilities for password hashing and JWT token management.

Provides bcrypt-based password hashing, SHA-256 token hashing,
and JWT token creation/verification with support for both
access tokens (short-lived) and refresh tokens (long-lived).
"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Bcrypt password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.

    Args:
        password: The plaintext password to hash.

    Returns:
        The bcrypt-hashed password string.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a bcrypt hash.

    Args:
        plain_password: The plaintext password to verify.
        hashed_password: The stored bcrypt hash.

    Returns:
        True if the password matches, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def hash_token(token: str) -> str:
    """
    Create a SHA-256 hash of a token string.

    Used to store refresh tokens securely in the database.
    We never store the raw JWT — only its hash.

    Args:
        token: The raw JWT token string.

    Returns:
        Hex-encoded SHA-256 hash.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(subject: str | UUID, extra_claims: dict[str, Any] | None = None) -> str:
    """
    Create a short-lived JWT access token.

    Args:
        subject: The token subject (typically user ID).
        extra_claims: Optional additional claims to embed in the token.

    Returns:
        Encoded JWT access token string.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str | UUID) -> tuple[str, datetime]:
    """
    Create a long-lived JWT refresh token.

    Args:
        subject: The token subject (typically user ID).

    Returns:
        Tuple of (encoded JWT refresh token string, expiry datetime).
    """
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "type": "refresh",
    }
    token = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expire


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: The JWT token string to decode.

    Returns:
        Dictionary of decoded token claims.

    Raises:
        JWTError: If the token is invalid, expired, or tampered with.
    """
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
