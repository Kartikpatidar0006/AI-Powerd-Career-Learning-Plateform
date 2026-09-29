"""Week 4 Prep: started_at, EVALUATING status, repo URL uniqueness.

Revision ID: 002_week4_prep
Revises: 001_initial
Create Date: 2026-09-28

Changes:
1. Add tasks.started_at (timestamp with timezone, nullable). Set on ASSIGNED -> IN_PROGRESS.
2. Update partial unique index uix_one_active_task_per_user to include EVALUATING:
   WHERE status IN ('ASSIGNED', 'IN_PROGRESS', 'SUBMITTED', 'EVALUATING')
3. Add partial unique index on (user_id, github_repo_url) WHERE github_repo_url IS NOT NULL:
   uix_task_user_github_repo ensures a user cannot submit the same GitHub repo URL for multiple tasks.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_week4_prep"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add started_at column to tasks table
    op.add_column(
        "tasks",
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when task transitioned from ASSIGNED to IN_PROGRESS",
        ),
    )

    # 2. Update partial unique index to include EVALUATING
    op.drop_index("uix_one_active_task_per_user", table_name="tasks")
    op.execute(
        """
        CREATE UNIQUE INDEX uix_one_active_task_per_user
        ON tasks (user_id)
        WHERE status IN ('ASSIGNED', 'IN_PROGRESS', 'SUBMITTED', 'EVALUATING')
        """
    )

    # 3. Add partial unique index for GitHub repo URL uniqueness per user
    op.execute(
        """
        CREATE UNIQUE INDEX uix_task_user_github_repo
        ON tasks (user_id, github_repo_url)
        WHERE github_repo_url IS NOT NULL
        """
    )


def downgrade() -> None:
    # 1. Drop GitHub repo URL uniqueness index
    op.drop_index("uix_task_user_github_repo", table_name="tasks")

    # 2. Revert partial unique index to exclude EVALUATING
    op.drop_index("uix_one_active_task_per_user", table_name="tasks")
    op.execute(
        """
        CREATE UNIQUE INDEX uix_one_active_task_per_user
        ON tasks (user_id)
        WHERE status IN ('ASSIGNED', 'IN_PROGRESS', 'SUBMITTED')
        """
    )

    # 3. Drop started_at column
    op.drop_column("tasks", "started_at")
