"""
Authentication API router.

Thin HTTP layer that handles request parsing, error translation, and
response formatting. All business logic is delegated to AuthService.

Rate limiting is applied to /signup and /login (5 requests/minute/IP)
to mitigate brute-force and credential-stuffing attacks.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.session import get_db
from app.schemas.auth import (
    LogoutRequest,
    MessageResponse,
    TokenRefreshRequest,
    TokenResponse,
    UserLoginRequest,
    UserResponse,
    UserSignupRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Rate limiter — keyed by client IP address
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={
        409: {"model": MessageResponse, "description": "Email already registered"},
        429: {"model": MessageResponse, "description": "Too many requests"},
    },
)
@limiter.limit("5/minute")
async def signup(
    request: Request,
    payload: UserSignupRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Register a new user account.

    Creates a new user with the provided email and password.
    The password is securely hashed before storage.

    Rate limited to 5 requests per minute per IP.
    """
    service = AuthService(db)
    try:
        return await service.register_user(
            email=payload.email,
            password=payload.password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and obtain tokens",
    responses={
        401: {"model": MessageResponse, "description": "Invalid credentials"},
        429: {"model": MessageResponse, "description": "Too many requests"},
    },
)
@limiter.limit("5/minute")
async def login(
    request: Request,
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate a user with email and password.

    Returns a pair of JWT tokens: a short-lived access token and a
    long-lived refresh token. The refresh token is stored (hashed) in
    the database for secure rotation and revocation.

    Rate limited to 5 requests per minute per IP.
    """
    service = AuthService(db)
    try:
        return await service.authenticate_user(
            email=payload.email,
            password=payload.password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post(
    "/refresh-token",
    response_model=TokenResponse,
    summary="Refresh access token",
    responses={
        401: {"model": MessageResponse, "description": "Invalid refresh token"},
    },
)
async def refresh_token(
    payload: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Rotate tokens: validate the old refresh token, revoke it, issue a new pair.

    The old refresh token is invalidated in the database (rotation).
    A new refresh token is issued and stored.
    """
    service = AuthService(db)
    try:
        return await service.refresh_tokens(refresh_token=payload.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout and revoke refresh tokens",
    responses={
        401: {"model": MessageResponse, "description": "Not authenticated"},
    },
)
async def logout(
    payload: LogoutRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Revoke refresh tokens for the authenticated user.

    If a specific refresh_token is provided in the body, only that
    token is revoked. Otherwise, all active refresh tokens for the
    user are revoked (full session invalidation).
    """
    service = AuthService(db)
    await service.logout(user_id=user_id, refresh_token=payload.refresh_token)
    return MessageResponse(message="Successfully logged out")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    responses={
        401: {"model": MessageResponse, "description": "Not authenticated"},
    },
)
async def get_me(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Retrieve the currently authenticated user's profile.

    Requires a valid access token in the Authorization header.
    """
    service = AuthService(db)
    try:
        return await service.get_current_user(user_id=user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
