"""
Authentication business logic service.

Contains all auth-related operations: user registration, authentication,
token management with database-backed refresh token rotation, and logout.
No HTTP concerns leak into this layer — it operates purely on domain
objects and returns structured results.
"""

from datetime import datetime, timezone
from uuid import UUID

from jose import JWTError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenResponse, UserResponse


class AuthService:
    """Service class encapsulating all authentication business logic."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the auth service with a database session.

        Args:
            db: An active async database session.
        """
        self.db = db

    # ──────────────────────────────────────────
    # User lookups
    # ──────────────────────────────────────────

    async def get_user_by_email(self, email: str) -> User | None:
        """
        Look up a user by their email address.

        Args:
            email: The email address to search for.

        Returns:
            The User object if found, None otherwise.
        """
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """
        Look up a user by their UUID.

        Args:
            user_id: The UUID of the user.

        Returns:
            The User object if found, None otherwise.
        """
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ──────────────────────────────────────────
    # Refresh token persistence
    # ──────────────────────────────────────────

    async def _store_refresh_token(
        self, user_id: UUID, raw_token: str, expires_at: datetime
    ) -> None:
        """
        Persist a hashed refresh token to the database.

        Args:
            user_id: The owning user's UUID.
            raw_token: The raw JWT refresh token (hashed before storage).
            expires_at: When the token expires.
        """
        token_record = RefreshToken(
            user_id=user_id,
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
        )
        self.db.add(token_record)
        await self.db.flush()

    async def _validate_and_revoke_refresh_token(self, raw_token: str) -> RefreshToken:
        """
        Validate a refresh token against the database and revoke it.

        Performs rotation: the old token is always revoked regardless of
        whether new tokens are successfully issued.

        Args:
            raw_token: The raw JWT refresh token to validate.

        Returns:
            The RefreshToken database record (now revoked).

        Raises:
            ValueError: If the token is not found, already revoked, or expired.
        """
        token_hash_value = hash_token(raw_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash_value)
        result = await self.db.execute(stmt)
        token_record = result.scalar_one_or_none()

        if not token_record:
            raise ValueError("Refresh token not found")

        if token_record.revoked:
            raise ValueError("Refresh token has been revoked")

        if token_record.expires_at < datetime.now(timezone.utc):
            raise ValueError("Refresh token has expired")

        # Revoke the old token (rotation)
        token_record.revoked = True
        await self.db.flush()

        return token_record

    async def _revoke_all_user_tokens(self, user_id: UUID) -> None:
        """
        Revoke all active refresh tokens for a user.

        Used during logout to invalidate all sessions.

        Args:
            user_id: The user whose tokens should be revoked.
        """
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)  # noqa: E712
            .values(revoked=True)
        )
        await self.db.execute(stmt)
        await self.db.flush()

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    async def register_user(self, email: str, password: str) -> UserResponse:
        """
        Register a new user account.

        Args:
            email: The user's email address.
            password: The plaintext password to hash and store.

        Returns:
            UserResponse with the newly created user's data.

        Raises:
            ValueError: If a user with the given email already exists.
        """
        existing_user = await self.get_user_by_email(email)
        if existing_user:
            raise ValueError("A user with this email already exists")

        user = User(
            email=email,
            hashed_password=hash_password(password),
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        return UserResponse.model_validate(user)

    async def authenticate_user(self, email: str, password: str) -> TokenResponse:
        """
        Authenticate a user, issue JWT tokens, and persist the refresh token.

        Args:
            email: The user's email address.
            password: The plaintext password to verify.

        Returns:
            TokenResponse containing access and refresh tokens.

        Raises:
            ValueError: If credentials are invalid or account is inactive.
        """
        user = await self.get_user_by_email(email)
        if not user:
            raise ValueError("Invalid email or password")

        if not verify_password(password, user.hashed_password):
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is deactivated")

        access_token = create_access_token(
            subject=user.id,
            extra_claims={"email": user.email},
        )
        refresh_token, expires_at = create_refresh_token(subject=user.id)

        # Store the refresh token hash in the database
        await self._store_refresh_token(user.id, refresh_token, expires_at)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """
        Rotate refresh tokens: validate the old one, revoke it, issue new pair.

        The old refresh token is always revoked (rotation). A new refresh
        token is issued and stored in the database.

        Args:
            refresh_token: The raw JWT refresh token to validate.

        Returns:
            TokenResponse containing new access and refresh tokens.

        Raises:
            ValueError: If the refresh token is invalid, expired, revoked,
                        or the associated user doesn't exist.
        """
        # Decode the JWT first to extract claims
        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise ValueError("Invalid or expired refresh token")

        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type — expected a refresh token")

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise ValueError("Invalid token payload")

        # Validate against DB and revoke the old token
        await self._validate_and_revoke_refresh_token(refresh_token)

        user = await self.get_user_by_id(UUID(user_id_str))
        if not user:
            raise ValueError("User not found")

        if not user.is_active:
            raise ValueError("Account is deactivated")

        # Issue new token pair
        new_access_token = create_access_token(
            subject=user.id,
            extra_claims={"email": user.email},
        )
        new_refresh_token, new_expires_at = create_refresh_token(subject=user.id)

        # Store the new refresh token
        await self._store_refresh_token(user.id, new_refresh_token, new_expires_at)

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
        )

    async def logout(self, user_id: UUID, refresh_token: str | None = None) -> None:
        """
        Revoke refresh tokens for the user.

        If a specific refresh_token is provided, only that token is revoked.
        Otherwise, all active refresh tokens for the user are revoked.

        Args:
            user_id: The authenticated user's UUID.
            refresh_token: Optional specific refresh token to revoke.
        """
        if refresh_token:
            token_hash_value = hash_token(refresh_token)
            stmt = (
                update(RefreshToken)
                .where(
                    RefreshToken.token_hash == token_hash_value,
                    RefreshToken.user_id == user_id,
                )
                .values(revoked=True)
            )
            await self.db.execute(stmt)
            await self.db.flush()
        else:
            await self._revoke_all_user_tokens(user_id)

    async def get_current_user(self, user_id: UUID) -> UserResponse:
        """
        Retrieve the current authenticated user's profile.

        Args:
            user_id: The UUID extracted from the JWT token.

        Returns:
            UserResponse with the user's profile data.

        Raises:
            ValueError: If the user doesn't exist or is inactive.
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        if not user.is_active:
            raise ValueError("Account is deactivated")

        return UserResponse.model_validate(user)
