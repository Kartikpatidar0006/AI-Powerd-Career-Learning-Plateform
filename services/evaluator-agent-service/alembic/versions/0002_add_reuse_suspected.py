"""Add reuse_suspected column to evaluations table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_add_reuse_suspected"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add reuse_suspected boolean column to evaluations."""
    op.add_column(
        "evaluations",
        sa.Column(
            "reuse_suspected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="True if zero commits detected after task started_at (reused repo cheat)",
        ),
    )


def downgrade() -> None:
    """Drop reuse_suspected column."""
    op.drop_column("evaluations", "reuse_suspected")
