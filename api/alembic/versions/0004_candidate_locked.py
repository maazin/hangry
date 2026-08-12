"""Phase 4 — mark which candidates are actually in the vote

Tier alone could not express this: a feasible place beyond the locked 6-8 is
not ranked, and on sparse OSM data an unverified place sometimes is.

Revision ID: 0004
Revises: 0003
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()))
    # Existing rows predate the degraded path, where only feasible was ranked.
    op.execute("update candidates set locked = true where tier = 'feasible'")


def downgrade() -> None:
    op.drop_column("candidates", "locked")
