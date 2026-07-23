"""
backend/app/schemas/__init__.py
================================
Public re-export surface for all Pydantic v2 schemas.

Import from here rather than from individual modules to keep call-sites
concise and to decouple the rest of the codebase from internal file layout::

    from app.schemas import UserCreate, UserResponse, TokenResponse
    from app.schemas import ProfessionCreate, ProfessionResponse

"""

from app.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetRequest,
    RefreshTokenRequest,
)
from app.schemas.profession import (
    ProfessionCreate,
    ProfessionListResponse,
    ProfessionResponse,
    ProfessionUpdate,
)
from app.schemas.token import (
    AccessTokenResponse,
    TokenPayload,
    TokenResponse,
)
from app.schemas.user import (
    UserAdminUpdate,
    UserBase,
    UserCreate,
    UserPublicResponse,
    UserResponse,
    UserUpdate,
)

__all__: list[str] = [
    # ── Auth request schemas ──────────────────────────────────────────── #
    "LoginRequest",
    "RefreshTokenRequest",
    "PasswordChangeRequest",
    "PasswordResetRequest",
    # ── Token response schemas ────────────────────────────────────────── #
    "TokenResponse",
    "AccessTokenResponse",
    "TokenPayload",
    # ── User schemas ──────────────────────────────────────────────────── #
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserAdminUpdate",
    "UserResponse",
    "UserPublicResponse",
    # ── Profession schemas ────────────────────────────────────────────── #
    "ProfessionCreate",
    "ProfessionUpdate",
    "ProfessionResponse",
    "ProfessionListResponse",
]
