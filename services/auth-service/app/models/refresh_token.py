"""
RefreshToken SQLAlchemy ORM model.

Stores hashed refresh tokens in the database for secure validation,
rotation, and revocation. Each token is tied to a specific user and
tracks its expiry and revocation status.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RefreshToken(Base):
    """
    Refresh token model for database-backed token management.

    Stores a SHA-256 hash of the JWT refresh token (never the raw token)
    alongside metadata for validation, rotation, and revocation.

    Attributes:
        id: UUID primary key, auto-generated.
        user_id: FK to the owning user.
        token_hash: SHA-256 hash of the JWT refresh token string.
        expires_at: When this refresh token expires (UTC).
        revoked: Whether this token has been explicitly revoked.
        created_at: Timestamp of token creation (UTC).
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, revoked={self.revoked})>"
