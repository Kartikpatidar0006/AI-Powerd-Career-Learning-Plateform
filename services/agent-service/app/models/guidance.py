"""
services/agent-service/app/models/guidance.py
-----------------------------------------------
Guidance model — Agent 5 provides final career guidance.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Guidance(Base):
    """Final career guidance report by Agent 5."""

    __tablename__ = "agent_guidances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    interview_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_interviews.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Overall career readiness (0-100)
    readiness_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Detailed feedback (JSON lists)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)        # JSON list
    weak_areas: Mapped[str | None] = mapped_column(Text, nullable=True)       # JSON list
    next_steps: Mapped[str | None] = mapped_column(Text, nullable=True)       # JSON list
    recommended_resources: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    career_path_advice: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Short summary shown to student
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    student: Mapped["Student"] = relationship("Student", back_populates="guidances")

    def __repr__(self) -> str:
        return f"Guidance(id={self.id!r}, readiness_score={self.readiness_score!r})"
