"""${message}

Revision ID: ${up_revision}
Revises:     ${down_revision | comma,n}
Create Date: ${create_date}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MIGRATION NOTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Add a plain-English description of WHAT this migration changes and WHY.
• If this migration is destructive (drops columns / tables), note what data
  is at risk and confirm the downgrade() restores the previous state.
• Link the GitHub issue or PR that prompted this change, e.g.:
    Ref: https://github.com/Kartikpatidar0006/AI-Powerd-Career-Learning-Plateform/issues/123
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

# ---------------------------------------------------------------------------
# Revision identifiers — managed by Alembic, do not edit manually.
# ---------------------------------------------------------------------------
revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Apply schema changes introduced by this revision."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Revert schema changes introduced by this revision."""
    ${downgrades if downgrades else "pass"}
