"""SQLAlchemy models. Mirrors the DDL in HANGRY-PRD.md section 9."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Place(Base):
    """Global place cache, shared across every session."""

    __tablename__ = "places"

    osm_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    geohash5: Mapped[str] = mapped_column(Text, nullable=False)
    cuisine: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    # OSM carries no price data. Left null in v1 rather than faked; the price
    # filter is hidden in the UI for the same reason.
    price_tier: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # {"vegetarian": "yes", "gluten_free": null} — null means *absent from
    # OSM*, which is not the same as "no". Nothing may collapse the two.
    diet_flags: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    hours: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="osm")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("places_geohash5_idx", "geohash5"),)


class TileCache(Base):
    """Which geohash tiles we have already pulled from Overpass."""

    __tablename__ = "tile_cache"

    geohash5: Mapped[str] = mapped_column(Text, primary_key=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # collecting | ranking | decided | expired
    status: Mapped[str] = mapped_column(Text, nullable=False, default="collecting")
    center_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    center_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    radius_m: Mapped[int] = mapped_column(Integer, nullable=False, default=5000)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    participants: Mapped[list[Participant]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )
    candidates: Mapped[list[Candidate]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    # Opaque, client-stored. Not real auth — it stops accidental cross-writes
    # and nothing more, which is the right level for an ephemeral session
    # holding no personal data.
    token: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(String(40), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    hard_constraints: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_creator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[Session] = relationship(back_populates="participants")

    __table_args__ = (
        Index("participants_session_token_idx", "session_id", "token", unique=True),
    )


class Candidate(Base):
    """Per-session snapshot of a place, with why it survived or didn't."""

    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    place_id: Mapped[str] = mapped_column(Text, ForeignKey("places.osm_id"), nullable=False)
    # feasible | unverified | eliminated
    tier: Mapped[str] = mapped_column(Text, nullable=False)
    # Whether this candidate is actually in the vote. Tier alone can't say:
    # a feasible place beyond the locked 6-8 isn't ranked either, and on
    # sparse data an unverified one sometimes is.
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # [{"participant": "Sam", "constraint": "gluten_free", "detail": "..."}]
    # Storing *why* is not optional: it is the difference between a result
    # that reads as reasoned and one that reads as arbitrary.
    cut_reasons: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    session: Mapped[Session] = relationship(back_populates="candidates")
    place: Mapped[Place] = relationship(lazy="selectin")

    __table_args__ = (UniqueConstraint("session_id", "place_id", name="candidates_session_place_key"),)


class Ranking(Base):
    __tablename__ = "rankings"

    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), primary_key=True
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Result(Base):
    __tablename__ = "results"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    ranked: Mapped[list] = mapped_column(JSONB, nullable=False)
    alternates: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rule: Mapped[str] = mapped_column(Text, nullable=False, default="minimax_regret")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
