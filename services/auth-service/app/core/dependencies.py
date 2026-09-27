"""
FastAPI dependencies for authentication.

Provides the `get_current_user_id` dependency that extracts and validates
the JWT access token from the Authorization header, returning the
authenticated user's UUID.
"""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.security import decode_token

# HTTP Bearer token extraction scheme
bearer_scheme = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UUID:
    """
    Extract and validate the user ID from the JWT access token.

    This dependency is used to protect routes that require authentication.
    It extracts the Bearer token from the Authorization header, decodes it,
    and returns the user's UUID.

    Args:
        credentials: The HTTP Bearer credentials extracted by FastAPI.

    Returns:
        The authenticated user's UUID.

    Raises:
        HTTPException: 401 if the token is missing, invalid, expired,
                       or not an access token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise credentials_exception

    # Ensure this is an access token, not a refresh token
    if payload.get("type") != "access":
        raise credentials_exception

    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        return UUID(user_id_str)
    except ValueError:
        raise credentials_exception
