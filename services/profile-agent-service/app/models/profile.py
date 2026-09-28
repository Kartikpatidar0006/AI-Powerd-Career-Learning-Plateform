"""
StudentProfile SQLAlchemy ORM model.

Stores comprehensive profile data including educational background,
raw student inputs, AI-extracted structured skills, target roles,
computed dashboard metrics, and immutability lock status.

NOTE ON HARDENING / IMMUTABILITY:
The 'is_locked' flag is enforced at the application and API service layer
(rejecting any subsequent onboarding/modification attempts once locked).
In a future production hardening pass, a PostgreSQL BEFORE UPDATE trigger
or conditional CHECK constraint (e.g.:
    CREATE OR REPLACE FUNCTION prevent_locked_profile_update()
    RETURNS TRIGGER AS $$
    BEGIN
        IF OLD.is_locked = TRUE THEN
            RAISE EXCEPTION 'StudentProfile is locked and immutable';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    CREATE TRIGGER trg_locked_profile_update
    BEFORE UPDATE ON student_profiles
    FOR EACH ROW EXECUTE FUNCTION prevent_locked_profile_update();
) can enforce this immutability directly at the database engine level.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base


class StudentProfile(Base):
    """
    StudentProfile model representing an AI-analyzed learner profile.

    Attributes:
        id: Primary key UUID.
        user_id: Foreign user UUID (from auth-service, decoupled across DBs).
        education: JSON storing degree, branch, year, institution.
        raw_input: JSON storing the original student answers for audit/re-analysis.
        structured_skills: JSON array of AI-extracted skills with proficiencies.
        target_role: Target career goal (e.g., 'Full Stack Engineer').
        experience_level: Enum/string ('student', 'fresher', '1-2yrs', '2+yrs').
        dashboard_data: JSON storing computed distribution, strengths, readiness score.
        is_locked: Flag indicating onboarding is finalized and immutable.
        created_at: Profile creation timestamp (UTC).
        updated_at: Profile last update timestamp (UTC).
    """

    __tablename__ = "student_profiles"

    id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        UUID(as_uuid=True),
        unique=True,
        index=True,
        nullable=False,
    )

    education: sa.orm.Mapped[dict[str, Any]] = sa.orm.mapped_column(
        JSONB,
        nullable=False,
    )

    raw_input: sa.orm.Mapped[dict[str, Any]] = sa.orm.mapped_column(
        JSONB,
        nullable=False,
    )

    structured_skills: sa.orm.Mapped[list[dict[str, Any]]] = sa.orm.mapped_column(
        JSONB,
        nullable=False,
    )

    target_role: sa.orm.Mapped[str] = sa.orm.mapped_column(
        sa.String(128),
        nullable=False,
    )

    experience_level: sa.orm.Mapped[str] = sa.orm.mapped_column(
        sa.String(32),
        nullable=False,
    )

    dashboard_data: sa.orm.Mapped[dict[str, Any]] = sa.orm.mapped_column(
        JSONB,
        nullable=False,
    )

    is_locked: sa.orm.Mapped[bool] = sa.orm.mapped_column(
        sa.Boolean,
        default=False,
        nullable=False,
    )

    created_at: sa.orm.Mapped[datetime] = sa.orm.mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: sa.orm.Mapped[datetime] = sa.orm.mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<StudentProfile(id={self.id}, user_id={self.user_id}, "
            f"role='{self.target_role}', locked={self.is_locked})>"
        )
