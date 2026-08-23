"""Groups and members, the durable layer under one-off sessions

A session evaporates in 24 hours, so every meal re-collected six people's
names, locations and dietary needs. A group remembers them and a session
becomes a "round" inside it.

Still no accounts: a group is its link, and membership is the same opaque
token model already used for participants.

Revision ID: 0005
Revises: 0004
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(length=40), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("hard_constraints", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_founder", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("members_group_token_idx", "members", ["group_id", "token"], unique=True)

    # Nullable on both: a session created before groups existed, or through the
    # bare session API, still has to be valid.
    op.add_column(
        "sessions",
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=True),
    )
    op.add_column(
        "participants",
        sa.Column("member_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("members.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("sessions_group_idx", "sessions", ["group_id"])


def downgrade() -> None:
    op.drop_index("sessions_group_idx", table_name="sessions")
    op.drop_column("participants", "member_id")
    op.drop_column("sessions", "group_id")
    op.drop_index("members_group_token_idx", table_name="members")
    op.drop_table("members")
    op.drop_table("groups")
