"""
services/auth-service/app/models/user.py
-----------------------------------------
User ORM model — lifted from the monolith.

MICROSERVICES NOTE: The `profession_id` column references a table owned
by Catalog Service. In this service, we store it as a plain UUID
(no FK constraint across service boundaries). Validation happens
at the application layer by calling the Catalog Service API.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.role import Role  # noqa: F401


class User(Base):
    """Registered user account."""

    __tablename__ = "users"

    __table_args__ = (
        Index("ix_users_email_active", "email", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="SET NULL", name="fk_users_role_id"),
        nullable=True,
        index=True,
        default=None,
    )

    # NOTE: No FK constraint here — profession_id is owned by catalog-service.
    profession_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        default=None,
    )

    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    assessment_score: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )

    ai_match_percentage: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )

    daily_study_time: Mapped[str | None] = mapped_column(String(50), nullable=True)

    experience_level: Mapped[str | None] = mapped_column(String(50), nullable=True)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )



    def __repr__(self) -> str:
        return (
            f"User(id={self.id!r}, email={self.email!r}, "
            f"is_active={self.is_active!r})"
        )
