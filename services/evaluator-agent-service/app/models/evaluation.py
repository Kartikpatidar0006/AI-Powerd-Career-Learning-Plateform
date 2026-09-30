"""
Evaluation SQLAlchemy ORM model.

Stores the full audit record of a GitHub repository evaluation.
One evaluation per task (task_id is unique per run but history is kept —
re-evaluation creates a new row; the latest row supersedes older ones).

Design decisions:
- repo_snapshot (JSONB): stores file tree, commit count/timestamps, README presence
  for audit. Does NOT store full file contents (too large, not needed for audit).
- deterministic_checks (JSONB): itemized pass/fail per check with scores and details,
  fully explainable to the student.
- llm_review (JSONB): raw strengths/weaknesses/suggestions/red_flags from LLM.
  red_flags about injection attempts are logged internally and NOT shown verbatim to student.
- final_score: computed from both scores with a documented cap rule.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base


class EvaluationStatus(str, enum.Enum):
    """Evaluation pipeline lifecycle states."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Evaluation(Base):
    """
    A complete GitHub repository evaluation record.

    Indexes:
    - task_id: Non-unique index (history kept); query latest with ORDER BY created_at DESC.
    - user_id: Index for user-scoped queries (GET /evaluations/{task_id} authorization).
    - status: Index for monitoring/ops queries.
    """

    __tablename__ = "evaluations"

    __table_args__ = (
        # Non-unique index on task_id — we keep history, latest row supersedes
        sa.Index("ix_evaluation_task_id", "task_id"),
        sa.Index("ix_evaluation_user_id", "user_id"),
    )

    id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    task_id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="FK to task in roadmap-agent-service (logical, no DB FK across services)",
    )

    user_id: sa.orm.Mapped[uuid.UUID] = sa.orm.mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    github_repo_url: sa.orm.Mapped[str] = sa.orm.mapped_column(
        sa.String(512),
        nullable=False,
    )

    # ── Audit snapshot (no full file contents to keep rows small) ──────
    repo_snapshot: sa.orm.Mapped[dict[str, Any] | None] = sa.orm.mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "Audit snapshot: {file_tree_count, commit_count, commit_timestamps, "
            "readme_present, primary_language, default_branch, pushed_at}"
        ),
    )

    # ── Deterministic checks (pure functions, no LLM) ──────────────────
    deterministic_checks: sa.orm.Mapped[list[dict[str, Any]] | None] = sa.orm.mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "Itemized deterministic check results. Each item: "
            "{check_name, passed, score_contribution, weight_pct, detail}"
        ),
    )

    deterministic_score: sa.orm.Mapped[float | None] = sa.orm.mapped_column(
        sa.Float,
        nullable=True,
        comment="Aggregate deterministic score 0-100",
    )

    # ── LLM review (runs only if deterministic gate passes) ────────────
    llm_review: sa.orm.Mapped[dict[str, Any] | None] = sa.orm.mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "LLM code review output: {strengths, weaknesses, suggestions, "
            "red_flags, quality_score}. red_flags are NOT exposed verbatim to students."
        ),
    )

    llm_score: sa.orm.Mapped[float | None] = sa.orm.mapped_column(
        sa.Float,
        nullable=True,
        comment="LLM quality_score (0-100) after cap rule applied",
    )

    # ── Final composed score ────────────────────────────────────────────
    final_score: sa.orm.Mapped[float | None] = sa.orm.mapped_column(
        sa.Float,
        nullable=True,
        comment="final = (det_score * 0.65) + (llm_score * 0.35), capped by det-score + 15",
    )

    passed: sa.orm.Mapped[bool | None] = sa.orm.mapped_column(
        sa.Boolean,
        nullable=True,
        comment="final_score >= PASS_SCORE",
    )

    reuse_suspected: sa.orm.Mapped[bool] = sa.orm.mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        server_default=sa.text("false"),
        comment="True if zero commits were detected after task started_at (reused repo cheat)",
    )

    feedback_summary: sa.orm.Mapped[str | None] = sa.orm.mapped_column(
        sa.Text,
        nullable=True,
        comment="Student-facing mentor-style feedback paragraph (generated, not raw LLM JSON)",
    )

    # ── Pipeline status ─────────────────────────────────────────────────
    status: sa.orm.Mapped[str] = sa.orm.mapped_column(
        sa.String(32),
        nullable=False,
        default=EvaluationStatus.PENDING.value,
        index=True,
    )

    error_detail: sa.orm.Mapped[str | None] = sa.orm.mapped_column(
        sa.Text,
        nullable=True,
        comment="Non-null only when status=FAILED; safe-to-show error reason",
    )

    created_at: sa.orm.Mapped[datetime] = sa.orm.mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    completed_at: sa.orm.Mapped[datetime | None] = sa.orm.mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<Evaluation(id={self.id}, task_id={self.task_id}, "
            f"status='{self.status}', final_score={self.final_score})>"
        )
