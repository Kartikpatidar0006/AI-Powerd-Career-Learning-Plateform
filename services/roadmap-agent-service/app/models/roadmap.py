"""
Roadmap SQLAlchemy ORM model.

Stores AI-generated learning roadmaps with milestone data as JSONB.
One roadmap per user, immutable once created (locked by application logic
and UNIQUE(user_id) DB constraint).
"""

import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base


class Roadmap(Base):
    """
    AI-generated learning roadmap for a student.

    Attributes:
        id: Primary key UUID.
        user_id: One-to-one with auth user (enforced by UNIQUE constraint).
        profile_snapshot: JSONB copy of the profile data used at generation
            time — stored for audit and reproducibility.
        milestones: JSONB list of MilestoneItem objects.
        status: Roadmap status ('active' once created, future expansion).
        created_at: Creation timestamp (UTC).
    """

    __tablename__ = "roadmaps"

    id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        UUID(as_uuid=True),
        unique=True,          # One roadmap per user, enforced at DB level
        index=True,
        nullable=False,
    )

    profile_snapshot: sa.orm.Mapped[dict[str, Any]] = sa.orm.mapped_column(
        JSONB,
        nullable=False,
        comment="Copy of profile data used at generation time for audit trail",
    )

    milestones: sa.orm.Mapped[list[dict[str, Any]]] = sa.orm.mapped_column(
        JSONB,
        nullable=False,
    )

    status: sa.orm.Mapped[str] = sa.orm.mapped_column(
        sa.String(32),
        nullable=False,
        default="active",
    )

    created_at: sa.orm.Mapped[datetime] = sa.orm.mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Roadmap(id={self.id}, user_id={self.user_id}, "
            f"milestones={len(self.milestones)}, status='{self.status}')>"
        )
