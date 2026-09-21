
"""
services/agent-service/app/models/interview.py
------------------------------------------------
Interview model — Agent 4 conducts AI mock interviews.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Interview(Base):
    """AI-conducted mock interview session (Agent 4)."""

    __tablename__ = "agent_interviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_evaluations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Questions asked (JSON list of {question, answer, score, feedback})
    qa_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Scores
    communication_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    technical_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    current_question_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="scheduled")
    # scheduled | in_progress | completed | abandoned

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    student: Mapped["Student"] = relationship("Student", back_populates="interviews")
    evaluation: Mapped["Evaluation"] = relationship("Evaluation", back_populates="interviews")

    def __repr__(self) -> str:
        return f"Interview(id={self.id!r}, status={self.status!r}, overall_score={self.overall_score!r})"
