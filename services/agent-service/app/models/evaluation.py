"""
services/agent-service/app/models/evaluation.py
-------------------------------------------------
Evaluation model — Agent 3 evaluates submitted GitHub repos.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Evaluation(Base):
    """Evaluation of a student's GitHub submission by Agent 3."""

    __tablename__ = "agent_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    problem_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_problems.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    github_url: Mapped[str] = mapped_column(String(1000), nullable=False)

    # Evaluation scores (0-100)
    code_quality_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    functionality_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    documentation_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    best_practices_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Evaluation details (JSON strings)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)       # JSON list
    improvements: Mapped[str | None] = mapped_column(Text, nullable=True)    # JSON list
    interview_questions: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of 8-15 questions
    raw_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)    # Full LLM analysis

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    # pending | evaluating | completed | failed

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    student: Mapped["Student"] = relationship("Student", back_populates="evaluations")
    problem: Mapped["Problem"] = relationship("Problem", back_populates="evaluations")
    interviews: Mapped[list["Interview"]] = relationship("Interview", back_populates="evaluation")

    def __repr__(self) -> str:
        return f"Evaluation(id={self.id!r}, github_url={self.github_url!r}, overall_score={self.overall_score!r})"
