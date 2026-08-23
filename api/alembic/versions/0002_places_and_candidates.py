"""Phase 2, place cache, tile cache, per-session candidates

Revision ID: 0002
Revises: 0001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "places",
        sa.Column("osm_id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("geohash5", sa.Text(), nullable=False),
        sa.Column("cuisine", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        # Null means unknown, and OSM has no price data at all in v1.
        sa.Column("price_tier", sa.SmallInteger(), nullable=True),
        # Per-key null means "absent from OSM", which must never be read as "no".
        sa.Column("diet_flags", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("hours", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="osm"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("places_geohash5_idx", "places", ["geohash5"])

    op.create_table(
        "tile_cache",
        sa.Column("geohash5", sa.Text(), primary_key=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("place_id", sa.Text(), sa.ForeignKey("places.osm_id"), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column("cut_reasons", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("session_id", "place_id", name="candidates_session_place_key"),
    )


def downgrade() -> None:
    op.drop_table("candidates")
    op.drop_table("tile_cache")
    op.drop_index("places_geohash5_idx", table_name="places")
    op.drop_table("places")
