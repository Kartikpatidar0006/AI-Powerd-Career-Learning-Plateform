"""Initial migration for interview-agent-service: creates interview_sessions, interview_turns, proctoring_events tables.

Revision ID: 0001_initial
Revises: None
Create Date: 2026-10-02

Includes all DB-level constraints:
- UNIQUE constraint on interview_sessions(task_id) (strictly one interview per task)
- CHECK constraint on interview_sessions(violation_count >= 0)
- Foreign key cascade: deleting a session should NOT cascade-delete in production logic
  (we never delete sessions), but ondelete="CASCADE" is added at the DB level for
  interview_turns and proctoring_events referencing session_id as a safety net for test cleanup.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Create interview_sessions table ──────────────────────────────
    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "task_id",
            sa.Uuid(),
            nullable=False,
            comment="Logical FK to task in roadmap-agent-service (one interview per task)",
        ),
        sa.Column(
            "evaluation_id",
            sa.Uuid(),
            nullable=False,
            comment="Logical FK to evaluation in evaluator-agent-service",
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="AVAILABLE",
            comment="AVAILABLE, IN_PROGRESS, COMPLETED, EXPIRED, TERMINATED_VIOLATION",
        ),
        sa.Column("available_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="available_from + 24 hours at creation",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("violation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("termination_reason", sa.Text(), nullable=True),
        sa.Column(
            "overall_performance_summary",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id", name="pk_interview_sessions"),
        sa.UniqueConstraint("task_id", name="uq_interview_sessions_task_id"),
        sa.CheckConstraint("violation_count >= 0", name="ck_interview_sessions_violation_count_non_negative"),
    )
    op.create_index("ix_interview_sessions_user_id", "interview_sessions", ["user_id"])
    op.create_index("ix_interview_sessions_task_id", "interview_sessions", ["task_id"])
    op.create_index("ix_interview_sessions_status", "interview_sessions", ["status"])

    # ── 2. Create interview_turns table ─────────────────────────────────
    op.create_table(
        "interview_turns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column(
            "question_context",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("answer_duration_seconds", sa.Float(), nullable=True),
        sa.Column("follow_up_of", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id", name="pk_interview_turns"),
        # Foreign key cascade: deleting a session should NOT cascade-delete in production logic
        # (we never delete sessions), but add ondelete="CASCADE" at the DB level as a safety net for test cleanup
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["interview_sessions.id"],
            name="fk_interview_turns_session_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["follow_up_of"],
            ["interview_turns.id"],
            name="fk_interview_turns_follow_up_of",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("session_id", "turn_number", name="uq_interview_turns_session_turn"),
    )
    op.create_index("ix_interview_turns_session_id", "interview_turns", ["session_id"])
    op.create_index("ix_interview_turns_follow_up_of", "interview_turns", ["follow_up_of"])

    # ── 3. Create proctoring_events table ───────────────────────────────
    op.create_table(
        "proctoring_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("turn_number_at_event", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_proctoring_events"),
        # Foreign key cascade: safety net for test cleanup only
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["interview_sessions.id"],
            name="fk_proctoring_events_session_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_proctoring_events_session_id", "proctoring_events", ["session_id"])
    op.create_index("ix_proctoring_events_event_type", "proctoring_events", ["event_type"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_index("ix_proctoring_events_event_type", table_name="proctoring_events")
    op.drop_index("ix_proctoring_events_session_id", table_name="proctoring_events")
    op.drop_table("proctoring_events")

    op.drop_index("ix_interview_turns_follow_up_of", table_name="interview_turns")
    op.drop_index("ix_interview_turns_session_id", table_name="interview_turns")
    op.drop_table("interview_turns")

    op.drop_index("ix_interview_sessions_status", table_name="interview_sessions")
    op.drop_index("ix_interview_sessions_task_id", table_name="interview_sessions")
    op.drop_index("ix_interview_sessions_user_id", table_name="interview_sessions")
    op.drop_table("interview_sessions")
