"""create student_profiles table

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-03 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "student_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("education", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("structured_skills", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("target_role", sa.String(length=128), nullable=False),
        sa.Column("experience_level", sa.String(length=32), nullable=False),
        sa.Column("dashboard_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_student_profiles_user_id",
        "student_profiles",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_student_profiles_user_id", table_name="student_profiles")
    op.drop_table("student_profiles")
