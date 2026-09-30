"""Initial migration for evaluator-agent-service: creates evaluations table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create evaluations table."""
    op.create_table(
        "evaluations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("github_repo_url", sa.String(512), nullable=False),
        sa.Column("repo_snapshot", JSONB, nullable=True),
        sa.Column("deterministic_checks", JSONB, nullable=True),
        sa.Column("deterministic_score", sa.Float, nullable=True),
        sa.Column("llm_review", JSONB, nullable=True),
        sa.Column("llm_score", sa.Float, nullable=True),
        sa.Column("final_score", sa.Float, nullable=True),
        sa.Column("passed", sa.Boolean, nullable=True),
        sa.Column("feedback_summary", sa.Text, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Indexes
    op.create_index("ix_evaluation_task_id", "evaluations", ["task_id"])
    op.create_index("ix_evaluation_user_id", "evaluations", ["user_id"])
    op.create_index("ix_evaluation_status", "evaluations", ["status"])


def downgrade() -> None:
    """Drop evaluations table."""
    op.drop_index("ix_evaluation_status", table_name="evaluations")
    op.drop_index("ix_evaluation_user_id", table_name="evaluations")
    op.drop_index("ix_evaluation_task_id", table_name="evaluations")
    op.drop_table("evaluations")
