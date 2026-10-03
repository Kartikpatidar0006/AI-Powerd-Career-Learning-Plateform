"""
Interview Agent SQLAlchemy ORM models.

Contains:
1. InterviewSession: The interview session record tied to an Agent 3 evaluation and task.
2. InterviewTurn: Individual turns (question/answer pairs and follow-ups).
3. ProctoringEvent: Integrity and proctoring log events (tab switches, copy-paste, etc.).

Design decisions & constraints:
- UNIQUE constraint on task_id: Ensures strictly one interview per task.
- CHECK constraint on violation_count >= 0: Integrity check at DB level.
- Foreign key cascade: deleting a session should NOT cascade-delete in production
  logic (we never delete sessions), but add ondelete="CASCADE" at the DB level for
  InterviewTurn and ProctoringEvent referencing session_id, as a safety net for test
  cleanup only.
- JSONB with standard JSON fallback: sa.JSON().with_variant(JSONB, "postgresql")
  enables production JSONB performance while preserving SQLite test compatibility.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


class InterviewSessionStatus(str, enum.Enum):
    """Interview session lifecycle states."""
    AVAILABLE = "AVAILABLE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    TERMINATED_VIOLATION = "TERMINATED_VIOLATION"


class ProctoringEventType(str, enum.Enum):
    """Proctoring violation event types."""
    TAB_BLUR = "TAB_BLUR"
    FULLSCREEN_EXIT = "FULLSCREEN_EXIT"
    COPY_PASTE_ATTEMPT = "COPY_PASTE_ATTEMPT"
    DEVTOOLS_DETECTED = "DEVTOOLS_DETECTED"


class InterviewSession(Base):
    """
    Interview session record.

    Tied to a specific completed Task (from Agent 2) and Evaluation (from Agent 3).
    Enforces a strict 1-to-1 relationship with task_id.
    """

    __tablename__ = "interview_sessions"

    __table_args__ = (
        sa.UniqueConstraint("task_id", name="uq_interview_sessions_task_id"),
        sa.CheckConstraint("violation_count >= 0", name="ck_interview_sessions_violation_count_non_negative"),
        sa.Index("ix_interview_sessions_user_id", "user_id"),
        sa.Index("ix_interview_sessions_task_id", "task_id"),
        sa.Index("ix_interview_sessions_status", "status"),
    )

    id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
    )

    task_id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
        unique=True,
        comment="Logical FK to task in roadmap-agent-service (strictly one interview per task)",
    )

    evaluation_id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
        comment="Logical FK to evaluation in evaluator-agent-service",
    )

    status: sa.orm.Mapped[str] = sa.orm.mapped_column(
        sa.String(32),
        nullable=False,
        default=InterviewSessionStatus.AVAILABLE.value,
        server_default=InterviewSessionStatus.AVAILABLE.value,
    )

    available_from: sa.orm.Mapped[datetime] = sa.orm.mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
    )

    expires_at: sa.orm.Mapped[datetime] = sa.orm.mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        comment="Expiration timestamp (set to available_from + 24 hours at creation in service layer)",
    )

    started_at: sa.orm.Mapped[datetime | None] = sa.orm.mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

    completed_at: sa.orm.Mapped[datetime | None] = sa.orm.mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

    violation_count: sa.orm.Mapped[int] = sa.orm.mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    termination_reason: sa.orm.Mapped[str | None] = sa.orm.mapped_column(
        sa.Text,
        nullable=True,
    )

    overall_performance_summary: sa.orm.Mapped[dict[str, Any] | None] = sa.orm.mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        comment="Overall interview performance scoring and assessment details",
    )

    created_at: sa.orm.Mapped[datetime] = sa.orm.mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.func.now(),
    )

    # Relationships
    turns: sa.orm.Mapped[list["InterviewTurn"]] = sa.orm.relationship(
        "InterviewTurn",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="InterviewTurn.turn_number",
    )

    proctoring_events: sa.orm.Mapped[list["ProctoringEvent"]] = sa.orm.relationship(
        "ProctoringEvent",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ProctoringEvent.timestamp",
    )

    def __repr__(self) -> str:
        return (
            f"<InterviewSession(id={self.id}, user_id={self.user_id}, "
            f"task_id={self.task_id}, status='{self.status}')>"
        )


class InterviewTurn(Base):
    """
    Individual turn within an interview session.

    Records the generated question, targeted context from Agent 3 findings,
    student answer, duration, and optional link to a previous follow-up turn.
    """

    __tablename__ = "interview_turns"

    __table_args__ = (
        sa.UniqueConstraint("session_id", "turn_number", name="uq_interview_turns_session_turn"),
        sa.Index("ix_interview_turns_session_id", "session_id"),
        sa.Index("ix_interview_turns_follow_up_of", "follow_up_of"),
    )

    id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    session_id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("interview_sessions.id", ondelete="CASCADE", name="fk_interview_turns_session_id"),
        nullable=False,
        comment=(
            "FK to InterviewSession. ondelete=CASCADE is configured at DB level as a "
            "safety net for test cleanup; production logic never deletes sessions."
        ),
    )

    turn_number: sa.orm.Mapped[int] = sa.orm.mapped_column(
        sa.Integer,
        nullable=False,
    )

    question_text: sa.orm.Mapped[str] = sa.orm.mapped_column(
        sa.Text,
        nullable=False,
    )

    question_context: sa.orm.Mapped[dict[str, Any] | None] = sa.orm.mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        comment="Agent 3 finding/skill context targeted by this question",
    )

    answer_text: sa.orm.Mapped[str | None] = sa.orm.mapped_column(
        sa.Text,
        nullable=True,
        comment="Student response text; null until candidate answers",
    )

    answer_duration_seconds: sa.orm.Mapped[float | None] = sa.orm.mapped_column(
        sa.Float,
        nullable=True,
    )

    follow_up_of: sa.orm.Mapped[uuid.UUID | None] = sa.orm.mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("interview_turns.id", ondelete="SET NULL", name="fk_interview_turns_follow_up_of"),
        nullable=True,
        comment="Self-referencing FK to preceding InterviewTurn if this is an adaptive follow-up",
    )

    created_at: sa.orm.Mapped[datetime] = sa.orm.mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.func.now(),
    )

    # Relationships
    session: sa.orm.Mapped["InterviewSession"] = sa.orm.relationship(
        "InterviewSession",
        back_populates="turns",
    )

    follow_up_turn: sa.orm.Mapped["InterviewTurn | None"] = sa.orm.relationship(
        "InterviewTurn",
        remote_side=[id],
    )

    def __repr__(self) -> str:
        return (
            f"<InterviewTurn(id={self.id}, session_id={self.session_id}, "
            f"turn_number={self.turn_number})>"
        )


class ProctoringEvent(Base):
    """
    Proctoring event record.

    Logs anti-cheat and integrity events (tab blur, fullscreen exit,
    copy-paste attempt, devtools detected) with associated turn number.
    """

    __tablename__ = "proctoring_events"

    __table_args__ = (
        sa.Index("ix_proctoring_events_session_id", "session_id"),
        sa.Index("ix_proctoring_events_event_type", "event_type"),
    )

    id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    session_id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("interview_sessions.id", ondelete="CASCADE", name="fk_proctoring_events_session_id"),
        nullable=False,
        comment=(
            "FK to InterviewSession. ondelete=CASCADE is configured at DB level as a "
            "safety net for test cleanup; production logic never deletes sessions."
        ),
    )

    event_type: sa.orm.Mapped[str] = sa.orm.mapped_column(
        sa.String(32),
        nullable=False,
    )

    timestamp: sa.orm.Mapped[datetime] = sa.orm.mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.func.now(),
    )

    turn_number_at_event: sa.orm.Mapped[int | None] = sa.orm.mapped_column(
        sa.Integer,
        nullable=True,
    )

    # Relationships
    session: sa.orm.Mapped["InterviewSession"] = sa.orm.relationship(
        "InterviewSession",
        back_populates="proctoring_events",
    )

    def __repr__(self) -> str:
        return (
            f"<ProctoringEvent(id={self.id}, session_id={self.session_id}, "
            f"event_type='{self.event_type}', timestamp={self.timestamp})>"
        )
