"""Initial schema: roadmaps and tasks tables.

Revision ID: 001_initial
Revises: 
Create Date: 2026-09-28

Includes all DB-level constraints:
- UNIQUE(user_id) on roadmaps
- UNIQUE(user_id, sequence_number) on tasks
- PARTIAL UNIQUE INDEX on tasks(user_id) WHERE status IN ('ASSIGNED','IN_PROGRESS','SUBMITTED')
- CHECK(difficulty BETWEEN 1 AND 5)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Create roadmaps table ──────────────────────────────────────────
    op.create_table(
        "roadmaps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  comment="Copy of profile data used at generation time for audit trail"),
        sa.Column("milestones", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_roadmap_user_id"),
    )
    op.create_index("ix_roadmaps_user_id", "roadmaps", ["user_id"])

    # ── Create tasks table ─────────────────────────────────────────────
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("roadmap_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("milestone_order", sa.Integer(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False,
                  comment="Global sequential task number per user (1, 2, 3, ...)"),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("acceptance_criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("skills_targeted", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False,
                  comment="Task difficulty 1-5, computed deterministically (never LLM-chosen)"),
        sa.Column("estimated_hours", sa.Float(), nullable=False),
        sa.Column("starter_hint", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ASSIGNED"),
        sa.Column("github_repo_url", sa.String(512), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluation_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                  comment="Populated by Agent 3 in Week 4 via POST /internal/tasks/{id}/evaluation"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["roadmap_id"], ["roadmaps.id"], ondelete="CASCADE"),
        # UNIQUE per-user sequence number
        sa.UniqueConstraint("user_id", "sequence_number", name="uq_task_user_sequence"),
        # DB-level difficulty range check
        sa.CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_task_difficulty_range"),
    )

    # Standard indexes
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_index("ix_tasks_roadmap_id", "tasks", ["roadmap_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])

    # CRITICAL: Partial unique index — one active task per user
    # This is the DB-level safety net against concurrent /tasks/next requests.
    op.execute(
        """
        CREATE UNIQUE INDEX uix_one_active_task_per_user
        ON tasks (user_id)
        WHERE status IN ('ASSIGNED', 'IN_PROGRESS', 'SUBMITTED')
        """
    )


def downgrade() -> None:
    op.drop_index("uix_one_active_task_per_user", table_name="tasks")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_roadmap_id", table_name="tasks")
    op.drop_index("ix_tasks_user_id", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_roadmaps_user_id", table_name="roadmaps")
    op.drop_table("roadmaps")
