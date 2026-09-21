"""
services/agent-service/app/models/problem.py
----------------------------------------------
Problem model — AI-generated coding/career problems (Agent 2).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Problem(Base):
    """AI-generated problem for a student based on profession and difficulty."""

    __tablename__ = "agent_problems"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)  # easy|medium|hard
    tech_stack: Mapped[str | None] = mapped_column(String(255), nullable=True)
    estimated_hours: Mapped[int] = mapped_column(nullable=False, default=8)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    is_assigned: Mapped[bool] = mapped_column(nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    student: Mapped["Student"] = relationship("Student", back_populates="problems")
    evaluations: Mapped[list["Evaluation"]] = relationship("Evaluation", back_populates="problem")

    def __repr__(self) -> str:
        return f"Problem(id={self.id!r}, title={self.title!r}, difficulty={self.difficulty!r})"
