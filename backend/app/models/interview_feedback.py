"""
backend/app/models/interview_feedback.py
-----------------------------------------
ORM model for the ``interview_feedback`` table.

Table overview
--------------
``interview_feedback``
    Stores evaluation feedback for a learner's completed ``Interview`` session.
    Each record links to exactly one ``Interview`` via a UNIQUE foreign key
    constraint (one-to-one relationship).

Columns
-------
id                      UUID PK — Python-generated (uuid4).
interview_id            UUID FK → interviews.id NOT NULL UNIQUE — target interview.
overall_score           INTEGER NOT NULL — aggregated overall score (0–100).
technical_score         INTEGER NOT NULL — technical competency score (0–100).
communication_score     INTEGER NOT NULL — communication clarity score (0–100).
confidence_score        INTEGER NOT NULL — confidence & delivery score (0–100).
problem_solving_score   INTEGER NOT NULL — problem-solving ability score (0–100).
strengths               TEXT NULLABLE — key strengths observed during the interview.
weaknesses              TEXT NULLABLE — key areas of improvement.
suggestions             TEXT NULLABLE — actionable suggestions for future interviews.
recommendation          TEXT NULLABLE — hiring recommendation (e.g. 'Strong Hire', 'Hire').
status                  VARCHAR(20) NOT NULL DEFAULT 'Generated' — Enum: 'Pending', 'Generated'.
created_at              TIMESTAMPTZ NOT NULL — creation timestamp.

Constraints
-----------
UNIQUE (interview_id) — exactly one feedback record per interview.
CHECK (overall_score BETWEEN 0 AND 100)
CHECK (technical_score BETWEEN 0 AND 100)
CHECK (communication_score BETWEEN 0 AND 100)
CHECK (confidence_score BETWEEN 0 AND 100)
CHECK (problem_solving_score BETWEEN 0 AND 100)

Relationships
-------------
interview_feedback.interview → Interview (one-to-one, bidirectional)

Registration
------------
Add the following line in ``app/db/base.py``::

    from app.models.interview_feedback import InterviewFeedback  # noqa: F401
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.interview import Interview  # noqa: F401


class InterviewFeedback(Base):
    """SQLAlchemy 2.x ORM model for the ``interview_feedback`` table.

    Represents evaluation feedback for a completed mock interview session.

    Attributes:
        id: UUID primary key.
        interview_id: FK to evaluated ``Interview`` (UNIQUE).
        overall_score: Aggregated overall score (0–100).
        technical_score: Technical competency score (0–100).
        communication_score: Communication clarity score (0–100).
        confidence_score: Confidence & delivery score (0–100).
        problem_solving_score: Problem-solving score (0–100).
        strengths: Markdown text describing strengths.
        weaknesses: Markdown text describing weaknesses.
        suggestions: Markdown text providing actionable advice.
        recommendation: Hiring recommendation text.
        status: Feedback status — ``'Pending'`` or ``'Generated'``.
        created_at: Creation timestamp.
        interview: Associated ``Interview`` ORM instance.
    """

    __tablename__ = "interview_feedback"

    # ── Table-level constraints ───────────────────────────────────────────── #
    __table_args__ = (
        UniqueConstraint(
            "interview_id",
            name="uq_interview_feedback_interview_id",
        ),
        CheckConstraint(
            "overall_score >= 0 AND overall_score <= 100",
            name="ck_interview_feedback_overall_score_range",
        ),
        CheckConstraint(
            "technical_score >= 0 AND technical_score <= 100",
            name="ck_interview_feedback_technical_score_range",
        ),
        CheckConstraint(
            "communication_score >= 0 AND communication_score <= 100",
            name="ck_interview_feedback_communication_score_range",
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 100",
            name="ck_interview_feedback_confidence_score_range",
        ),
        CheckConstraint(
            "problem_solving_score >= 0 AND problem_solving_score <= 100",
            name="ck_interview_feedback_problem_solving_score_range",
        ),
    )

    # ── Primary key ──────────────────────────────────────────────────────── #
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Surrogate primary key — UUID v4.",
    )

    # ── Foreign key — Interview ─────────────────────────────────────────── #
    interview_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="FK → interviews.id. Feedback deleted with interview.",
    )

    # ── Scores ───────────────────────────────────────────────────────────── #
    overall_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Overall aggregated score (0-100).",
    )

    technical_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Technical score (0-100).",
    )

    communication_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Communication score (0-100).",
    )

    confidence_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Confidence score (0-100).",
    )

    problem_solving_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Problem solving score (0-100).",
    )

    # ── Qualitative Feedback ────────────────────────────────────────────── #
    strengths: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Observed strengths during the interview.",
    )

    weaknesses: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Observed weaknesses during the interview.",
    )

    suggestions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Actionable suggestions for improvement.",
    )

    recommendation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Hiring recommendation (e.g. 'Strong Hire', 'Hire').",
    )

    # ── Status ───────────────────────────────────────────────────────────── #
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        default="Generated",
        server_default="Generated",
        comment="Evaluation status: 'Pending' or 'Generated'.",
    )

    # ── Timestamps ───────────────────────────────────────────────────────── #
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="UTC timestamp of creation.",
    )

    # ── Relationships ─────────────────────────────────────────────────────── #
    interview: Mapped["Interview"] = relationship(
        "Interview",
        back_populates="feedback",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"InterviewFeedback("
            f"id={self.id!r}, "
            f"interview_id={self.interview_id!r}, "
            f"overall_score={self.overall_score!r}, "
            f"recommendation={self.recommendation!r}"
            f")"
        )
