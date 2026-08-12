"""
backend/app/api/v1/auth/router.py
==================================
FastAPI router for the authentication feature.

This module is the **HTTP transport layer** for authentication.  Its only jobs
are:

  1. Accept and validate incoming HTTP requests via Pydantic schemas.
  2. Construct the ``AuthService`` with the injected database session.
  3. Call the appropriate ``AuthService`` method.
  4. Map ``AuthError`` domain exceptions to ``HTTPException`` with the correct
     HTTP status codes.
  5. Return the appropriate Pydantic response schema.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT THIS FILE MUST NOT CONTAIN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✗ Password hashing or verification.
  ✗ JWT creation or decoding.
  ✗ Database queries (no Session.execute, no selects).
  ✗ Business-rule logic (duplicate checks, account status tests).
  ✗ Direct imports from app.core.security.

All of the above live in ``app/services/auth.py`` and its dependencies.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENDPOINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  POST   /api/v1/auth/register        Register a new user account.
  POST   /api/v1/auth/login           Authenticate and obtain tokens.
  POST   /api/v1/auth/refresh         Exchange a refresh token for a new access token.
  GET    /api/v1/auth/me              Return the current authenticated user.
  POST   /api/v1/auth/change-password Change the authenticated user's password.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AUTHENTICATION DEPENDENCY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
``get_current_user`` is a FastAPI dependency defined in this module.  It:
  - Extracts the raw Bearer token from the ``Authorization`` header via
    ``OAuth2PasswordBearer``.
  - Delegates token validation and user resolution to ``AuthService``.
  - Returns a ``UserResponse`` to inject into the route handler.
  - Converts ``AuthError`` to ``HTTPException(401)`` so FastAPI handles it.

Move ``get_current_user`` to ``app/api/deps.py`` when more routers need it.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ERROR CODE → HTTP STATUS MAP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  email_taken         → 409 Conflict
  invalid_credentials → 401 Unauthorized
  account_inactive    → 403 Forbidden
  account_unverified  → 403 Forbidden
  invalid_token       → 401 Unauthorized
  wrong_password      → 400 Bad Request
  same_password       → 400 Bad Request
  user_not_found      → 404 Not Found
  <anything else>     → 500 Internal Server Error
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    RefreshTokenRequest,
)
from app.schemas.token import AccessTokenResponse, TokenResponse
from app.schemas.user import UserCreate, UserResponse
from app.services.auth import AuthError, AuthService

logger: logging.Logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────────────────────

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# OAuth2 scheme — extracts the Bearer token from the Authorization header.
# ``tokenUrl`` is the login endpoint path (relative to the app root) used by
# Swagger UI to display the "Authorize" button.
# ─────────────────────────────────────────────────────────────────────────────

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# ─────────────────────────────────────────────────────────────────────────────
# AuthError → HTTPException mapping table
# ─────────────────────────────────────────────────────────────────────────────

_AUTH_ERROR_STATUS: dict[str, int] = {
    AuthError.EMAIL_TAKEN:          status.HTTP_409_CONFLICT,
    AuthError.INVALID_CREDENTIALS:  status.HTTP_401_UNAUTHORIZED,
    AuthError.ACCOUNT_INACTIVE:     status.HTTP_403_FORBIDDEN,
    AuthError.ACCOUNT_UNVERIFIED:   status.HTTP_403_FORBIDDEN,
    AuthError.INVALID_TOKEN:        status.HTTP_401_UNAUTHORIZED,
    AuthError.WRONG_PASSWORD:       status.HTTP_400_BAD_REQUEST,
    AuthError.SAME_PASSWORD:        status.HTTP_400_BAD_REQUEST,
    AuthError.USER_NOT_FOUND:       status.HTTP_404_NOT_FOUND,
}

# ─────────────────────────────────────────────────────────────────────────────
# Internal helper — convert AuthError → HTTPException
# ─────────────────────────────────────────────────────────────────────────────


def _raise_http(exc: AuthError) -> None:
    """Convert a domain ``AuthError`` into a FastAPI ``HTTPException``.

    Looks up the HTTP status code from the ``_AUTH_ERROR_STATUS`` mapping.
    Falls back to ``500 Internal Server Error`` for any unknown ``code``
    (which indicates a programming error — a new ``AuthError`` code was added
    to the service without a corresponding mapping here).

    Args:
        exc: The ``AuthError`` raised by ``AuthService``.

    Raises:
        HTTPException: Always — this function never returns normally.
    """
    http_status = _AUTH_ERROR_STATUS.get(
        exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    if http_status == status.HTTP_500_INTERNAL_SERVER_ERROR:
        # Unknown code — log at ERROR so it's caught in monitoring.
        logger.error(
            "Unmapped AuthError code '%s' fell through to 500: %s",
            exc.code,
            exc.message,
        )
    headers = (
        {"WWW-Authenticate": "Bearer"}
        if http_status == status.HTTP_401_UNAUTHORIZED
        else None
    )
    raise HTTPException(
        status_code=http_status,
        detail=exc.message,
        headers=headers,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Reusable dependencies
# ─────────────────────────────────────────────────────────────────────────────

# Annotated type aliases keep route signatures concise.
DbDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(_oauth2_scheme)]


def get_current_user(
    token: TokenDep,
    db: DbDep,
) -> UserResponse:
    """FastAPI dependency that validates a Bearer token and returns the user.

    Extracts the raw JWT string from the ``Authorization: Bearer`` header
    (via ``OAuth2PasswordBearer``), delegates validation and user resolution
    to ``AuthService.get_current_user_by_token``, and returns a
    ``UserResponse`` schema.

    Inject this into any route that requires an authenticated user::

        @router.get("/protected")
        def protected_route(current_user: Annotated[UserResponse, Depends(get_current_user)]):
            ...

    Args:
        token: The raw Bearer JWT string, extracted by ``OAuth2PasswordBearer``.
        db: An active SQLAlchemy ``Session`` provided by ``get_db``.

    Returns:
        The ``UserResponse`` for the authenticated, active user.

    Raises:
        HTTPException: 401 Unauthorized if the token is invalid, expired,
            or the user no longer exists.
        HTTPException: 403 Forbidden if the user account is suspended.
    """
    try:
        return AuthService(db).get_current_user_by_token(token)
    except AuthError as exc:
        _raise_http(exc)


# Annotated dependency for route signatures.
CurrentUserDep = Annotated[UserResponse, Depends(get_current_user)]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description=(
        "Create a new user account with the provided full name, email, and "
        "password.  On success, returns a full token pair (access + refresh) "
        "so the client can immediately make authenticated requests without a "
        "separate login step.\n\n"
        "**Validation rules**\n"
        "- `email` must be a valid RFC 5322 address and unique across the platform.\n"
        "- `password` must be 8–128 characters.\n"
        "- `full_name` must be 1–255 characters.\n\n"
        "**Side effects**\n"
        "- A new `users` row is committed with `is_verified=false`.\n"
        "- A verification email should be triggered by the service layer (not yet wired)."
    ),
    responses={
        201: {"description": "User registered successfully. Token pair returned."},
        409: {"description": "Email address is already registered."},
        422: {"description": "Request body failed schema validation."},
    },
)
def register(
    payload: UserCreate,
    db: DbDep,
) -> TokenResponse:
    """Register a new user and return an access + refresh token pair.

    Args:
        payload: Validated ``UserCreate`` body (full_name, email, password).
        db: Injected database session.

    Returns:
        A ``TokenResponse`` containing the access token, refresh token, and
        ``token_type="bearer"``.

    Raises:
        HTTPException 409: If the email is already taken.
        HTTPException 422: If the request body is invalid (handled by FastAPI).
    """
    logger.info("POST /register | email=%s", payload.email)
    try:
        _, tokens = AuthService(db).register_user(payload)
        return tokens
    except AuthError as exc:
        _raise_http(exc)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and obtain JWT tokens",
    description=(
        "Authenticate with email and password.  Returns a full token pair "
        "(short-lived access token + long-lived refresh token).\n\n"
        "The access token should be included as ``Authorization: Bearer <token>`` "
        "on subsequent requests.  The refresh token should be stored securely "
        "(e.g. in an ``HttpOnly`` cookie) and used only with ``POST /refresh``.\n\n"
        "**Note:** This endpoint accepts JSON body. For the OAuth2 form-based "
        "flow (required by some clients), use the standard "
        "``application/x-www-form-urlencoded`` format with an ``OAuth2PasswordRequestForm``."
    ),
    responses={
        200: {"description": "Login successful. Token pair returned."},
        401: {"description": "Invalid email or password."},
        403: {"description": "Account is suspended."},
        422: {"description": "Request body failed schema validation."},
    },
)
def login(
    payload: LoginRequest,
    db: DbDep,
) -> TokenResponse:
    """Authenticate a user with email + password and return a token pair.

    Args:
        payload: Validated ``LoginRequest`` body (email, password).
        db: Injected database session.

    Returns:
        A ``TokenResponse`` containing the access and refresh JWTs.

    Raises:
        HTTPException 401: If credentials are invalid.
        HTTPException 403: If the account is suspended.
    """
    logger.info("POST /login | email=%s", payload.email)
    try:
        _, tokens = AuthService(db).login_user(payload)
        return tokens
    except AuthError as exc:
        _raise_http(exc)


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Exchange a refresh token for a new access token",
    description=(
        "Submit a valid, non-expired refresh token to receive a new short-lived "
        "access token.  The refresh token itself is not rotated in this implementation "
        "(token rotation is an opt-in enhancement for the service layer).\n\n"
        "**Security note:** Only tokens with ``type=\\\"refresh\\\"`` are accepted. "
        "Submitting an access token returns 401."
    ),
    responses={
        200: {"description": "New access token issued successfully."},
        401: {"description": "Refresh token is invalid, expired, or of wrong type."},
        403: {"description": "Account associated with the token has been suspended."},
        422: {"description": "Request body failed schema validation."},
    },
)
def refresh(
    payload: RefreshTokenRequest,
    db: DbDep,
) -> AccessTokenResponse:
    """Issue a new access token from a valid refresh token.

    Args:
        payload: Validated ``RefreshTokenRequest`` body (refresh_token string).
        db: Injected database session.

    Returns:
        An ``AccessTokenResponse`` containing a freshly signed access token.

    Raises:
        HTTPException 401: If the refresh token is invalid, expired, or of
            the wrong type.
        HTTPException 403: If the user account is suspended.
    """
    logger.info("POST /refresh")
    try:
        return AuthService(db).refresh_access_token(payload)
    except AuthError as exc:
        _raise_http(exc)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the current authenticated user",
    description=(
        "Return the full profile of the currently authenticated user.  "
        "Requires a valid access token in the ``Authorization: Bearer`` header.\n\n"
        "**Fields returned:** id, full_name, email, role_id, is_active, "
        "is_verified, created_at, updated_at.\n\n"
        "**Fields never returned:** password_hash (excluded by design)."
    ),
    responses={
        200: {"description": "Current user profile returned successfully."},
        401: {"description": "Missing, invalid, or expired access token."},
        403: {"description": "Account has been suspended."},
    },
)
def me(current_user: CurrentUserDep) -> UserResponse:
    """Return the profile of the currently authenticated user.

    The user is resolved by the ``get_current_user`` dependency which
    validates the Bearer token and performs the database lookup.  No
    additional service call is needed here.

    Args:
        current_user: ``UserResponse`` injected by the ``get_current_user``
            dependency.

    Returns:
        The ``UserResponse`` for the authenticated user.
    """
    logger.debug("GET /me | user_id=%s", current_user.id)
    return current_user


@router.post(
    "/change-password",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Change the current user's password",
    description=(
        "Change the authenticated user's password.  Requires both the current "
        "password (for re-verification) and the new password.\n\n"
        "**Validation rules**\n"
        "- ``current_password`` must match the stored bcrypt hash.\n"
        "- ``new_password`` must be 8–128 characters.\n"
        "- ``new_password`` and ``confirm_password`` must be identical.\n"
        "- ``new_password`` must differ from ``current_password``.\n\n"
        "**Security note:** Requiring the current password prevents account "
        "takeover via a stolen access token alone."
    ),
    responses={
        200: {"description": "Password changed successfully. Updated profile returned."},
        400: {"description": "Current password is wrong, or new == current."},
        401: {"description": "Missing, invalid, or expired access token."},
        403: {"description": "Account has been suspended."},
        422: {"description": "Request body failed schema validation."},
    },
)
def change_password(
    payload: PasswordChangeRequest,
    current_user: CurrentUserDep,
    db: DbDep,
) -> UserResponse:
    """Change the authenticated user's password.

    Args:
        payload: Validated ``PasswordChangeRequest`` body containing
            ``current_password``, ``new_password``, and ``confirm_password``.
        current_user: The authenticated user, resolved by the
            ``get_current_user`` dependency.
        db: Injected database session.

    Returns:
        The updated ``UserResponse`` after a successful password change.

    Raises:
        HTTPException 400: If the current password is incorrect or the new
            password is identical to the current one.
        HTTPException 401: If the access token is invalid or expired.
        HTTPException 403: If the account is suspended.
    """
    logger.info("POST /change-password | user_id=%s", current_user.id)
    try:
        return AuthService(db).change_password(current_user.id, payload)
    except AuthError as exc:
        _raise_http(exc)
