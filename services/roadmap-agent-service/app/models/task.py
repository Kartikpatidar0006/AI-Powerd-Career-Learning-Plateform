"""
Task SQLAlchemy ORM model.

Represents an individual learning task within a roadmap milestone.
Critical database-level constraints enforce the "one active task per user" rule:
  1. UNIQUE(user_id, sequence_number) — no duplicate sequence numbers per user.
  2. PARTIAL UNIQUE INDEX on (user_id) WHERE status IN ('ASSIGNED','IN_PROGRESS','SUBMITTED')
     — ensures a user can never have more than one active task, even under concurrent requests.
  3. CHECK constraint on difficulty between 1 and 5.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base


class TaskStatus(str, enum.Enum):
    """
    Valid task lifecycle states.

    Transitions are enforced exclusively by TaskStateMachine.
    ASSIGNED -> IN_PROGRESS -> SUBMITTED -> EVALUATING -> EVALUATED
    EVALUATING -> SUBMITTED (on evaluator failure)
    Re-submission is allowed only in SUBMITTED (never in EVALUATING).
    """
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    EVALUATING = "EVALUATING"
    EVALUATED = "EVALUATED"


class Task(Base):
    """
    A learning task assigned to a student within a roadmap milestone.

    DB-level constraints:
    - UNIQUE(user_id, sequence_number): Global task ordering per user.
    - PARTIAL UNIQUE INDEX on (user_id) WHERE status IN ('ASSIGNED','IN_PROGRESS','SUBMITTED','EVALUATING'):
      The critical safety net ensuring only ONE active task per user at all times.
      This index is the final defense against concurrent /tasks/next race conditions.
    - PARTIAL UNIQUE INDEX on (user_id, github_repo_url) WHERE github_repo_url IS NOT NULL:
      Ensures a user cannot reuse the same GitHub repo URL for multiple tasks.
    - CHECK(difficulty BETWEEN 1 AND 5): Enforces valid difficulty range at DB level.
    """

    __tablename__ = "tasks"

    __table_args__ = (
        # UNIQUE per-user task sequence
        sa.UniqueConstraint("user_id", "sequence_number", name="uq_task_user_sequence"),
        # DB-level check for difficulty band
        sa.CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_task_difficulty_range"),
        # PARTIAL UNIQUE INDEX: One active task per user (including EVALUATING).
        sa.Index(
            "uix_one_active_task_per_user",
            "user_id",
            unique=True,
            postgresql_where=sa.text("status IN ('ASSIGNED', 'IN_PROGRESS', 'SUBMITTED', 'EVALUATING')"),
        ),
        # PARTIAL UNIQUE INDEX: GitHub repo URL uniqueness per user
        sa.Index(
            "uix_task_user_github_repo",
            "user_id",
            "github_repo_url",
            unique=True,
            postgresql_where=sa.text("github_repo_url IS NOT NULL"),
        ),
    )

    id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        UUID(as_uuid=True),
        index=True,
        nullable=False,
    )

    roadmap_id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("roadmaps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    milestone_order: sa.orm.Mapped[int] = sa.orm.mapped_column(
        sa.Integer,
        nullable=False,
    )

    sequence_number: sa.orm.Mapped[int] = sa.orm.mapped_column(
        sa.Integer,
        nullable=False,
        comment="Global sequential task number per user (1, 2, 3, ...)",
    )

    title: sa.orm.Mapped[str] = sa.orm.mapped_column(
        sa.String(256),
        nullable=False,
    )

    description: sa.orm.Mapped[str] = sa.orm.mapped_column(
        sa.Text,
        nullable=False,
    )

    requirements: sa.orm.Mapped[list[str]] = sa.orm.mapped_column(
        JSONB,
        nullable=False,
    )

    acceptance_criteria: sa.orm.Mapped[list[str]] = sa.orm.mapped_column(
        JSONB,
        nullable=False,
    )

    skills_targeted: sa.orm.Mapped[list[str]] = sa.orm.mapped_column(
        JSONB,
        nullable=False,
    )

    difficulty: sa.orm.Mapped[int] = sa.orm.mapped_column(
        sa.Integer,
        nullable=False,
        comment="Task difficulty 1-5, computed deterministically (never LLM-chosen)",
    )

    estimated_hours: sa.orm.Mapped[float] = sa.orm.mapped_column(
        sa.Float,
        nullable=False,
    )

    starter_hint: sa.orm.Mapped[str | None] = sa.orm.mapped_column(
        sa.Text,
        nullable=True,
    )

    status: sa.orm.Mapped[str] = sa.orm.mapped_column(
        sa.String(32),
        nullable=False,
        default=TaskStatus.ASSIGNED.value,
        index=True,
    )

    github_repo_url: sa.orm.Mapped[str | None] = sa.orm.mapped_column(
        sa.String(512),
        nullable=True,
    )

    started_at: sa.orm.Mapped[datetime | None] = sa.orm.mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when task transitioned from ASSIGNED to IN_PROGRESS",
    )

    submitted_at: sa.orm.Mapped[datetime | None] = sa.orm.mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

    evaluated_at: sa.orm.Mapped[datetime | None] = sa.orm.mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

    evaluation_summary: sa.orm.Mapped[dict[str, Any] | None] = sa.orm.mapped_column(
        JSONB,
        nullable=True,
        comment="Populated by Agent 3 in Week 4 via POST /internal/tasks/{id}/evaluation",
    )

    created_at: sa.orm.Mapped[datetime] = sa.orm.mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Task(id={self.id}, user_id={self.user_id}, "
            f"seq={self.sequence_number}, status='{self.status}', "
            f"difficulty={self.difficulty})>"
        )
