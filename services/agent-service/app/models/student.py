"""
services/agent-service/app/models/student.py
----------------------------------------------
Student model — stores student profile and onboarding details.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Student(Base):
    """Student profile collected by Agent 1."""

    __tablename__ = "agent_students"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True, comment="References auth-service users.id"
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    profession: Mapped[str] = mapped_column(String(255), nullable=False)
    experience_level: Mapped[str] = mapped_column(String(50), nullable=False, default="beginner")
    goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_stack: Mapped[str | None] = mapped_column(String(255), nullable=True)
    weekly_hours: Mapped[int] = mapped_column(nullable=False, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    problems: Mapped[list["Problem"]] = relationship("Problem", back_populates="student", cascade="all, delete-orphan")
    evaluations: Mapped[list["Evaluation"]] = relationship("Evaluation", back_populates="student", cascade="all, delete-orphan")
    interviews: Mapped[list["Interview"]] = relationship("Interview", back_populates="student", cascade="all, delete-orphan")
    guidances: Mapped[list["Guidance"]] = relationship("Guidance", back_populates="student", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"Student(id={self.id!r}, email={self.email!r}, profession={self.profession!r})"
