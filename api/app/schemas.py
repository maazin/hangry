"""Request/response contracts. Mirrors HANGRY-PRD.md section 10."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constraints import ALL_DIETS


class HardConstraints(BaseModel):
    """What a participant cannot bend on.

    Note what is absent: there is no "preferences" field here. Soft
    preferences arrive later as a ranking, never as a 1-5 rating.
    """

    diets: list[str] = Field(default_factory=list)
    max_distance_m: int | None = Field(default=None, ge=100, le=100_000)
    # Wired up but unused in v1, OSM has no price data, so the UI hides it
    # rather than filtering against nulls.
    max_price_tier: int | None = Field(default=None, ge=1, le=4)
    open_now: bool = False

    @field_validator("diets")
    @classmethod
    def known_diets(cls, value: list[str]) -> list[str]:
        unknown = [d for d in value if d not in ALL_DIETS]
        if unknown:
            raise ValueError(f"unknown dietary constraints: {unknown}. Known: {ALL_DIETS}")
        return sorted(set(value))


class ParticipantIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    hard_constraints: HardConstraints = Field(default_factory=HardConstraints)


class SessionCreate(BaseModel):
    creator: ParticipantIn
    radius_m: int = Field(default=4828, ge=500, le=40_300)
    center_lat: float | None = Field(default=None, ge=-90, le=90)
    center_lon: float | None = Field(default=None, ge=-180, le=180)


class SessionCreated(BaseModel):
    slug: str
    participant_id: uuid.UUID
    token: str
    status: str


class ParticipantJoined(BaseModel):
    participant_id: uuid.UUID
    token: str


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    is_creator: bool
    hard_constraints: dict
    joined_at: datetime


class CandidateOut(BaseModel):
    id: uuid.UUID
    place_id: str
    name: str
    lat: float
    lon: float
    cuisine: list[str]
    tier: str
    # Whether this candidate is in the vote. Not implied by tier.
    locked: bool = False
    distance_m: float
    cut_reasons: list[dict] = Field(default_factory=list)


class ResultOut(BaseModel):
    ranked: list[dict]
    alternates: dict
    comparison: dict
    rule: str
    computed_at: datetime


class You(BaseModel):
    """Who the caller is, when they present a token.

    Without this the client cannot tell which row in `participants` is itself,
    and a page reload would ask someone to rank again after they already had.
    """

    participant_id: uuid.UUID
    display_name: str
    is_creator: bool
    has_ranked: bool


class SessionState(BaseModel):
    slug: str
    status: str
    # Set when this session is a round in a group. Lets a round page send
    # someone home when their phone has no token for it.
    group_slug: str | None = None
    radius_m: int
    center_lat: float | None
    center_lon: float | None
    created_at: datetime
    expires_at: datetime
    participants: list[ParticipantOut]
    candidates: list[CandidateOut] = Field(default_factory=list)
    advisories: list[dict] = Field(default_factory=list)
    submitted: int = 0
    result: ResultOut | None = None
    you: You | None = None


class StartResult(BaseModel):
    status: str
    candidates: list[CandidateOut]
    advisories: list[dict] = Field(default_factory=list)
    eliminated_count: int = 0
    # True when the vote is running on candidates the data couldn't verify.
    # The UI must say so; it changes what the result means.
    unverified_used: bool = False


# --------------------------------------------------------------------------
# groups, the durable layer
# --------------------------------------------------------------------------


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    founder: ParticipantIn


class GroupCreated(BaseModel):
    slug: str
    member_id: uuid.UUID
    token: str


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    is_founder: bool
    hard_constraints: dict
    joined_at: datetime


class MemberUpdate(BaseModel):
    """Everything optional, this is used both to move location before a
    round and to correct a diet, and neither should require resending the
    other."""

    name: str | None = Field(default=None, min_length=1, max_length=40)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    hard_constraints: HardConstraints | None = None


class RoundSummary(BaseModel):
    slug: str
    status: str
    created_at: datetime
    expires_at: datetime
    participants: int
    submitted: int
    winner: str | None = None


class GroupYou(BaseModel):
    member_id: uuid.UUID
    display_name: str
    is_founder: bool


class GroupState(BaseModel):
    slug: str
    name: str
    created_at: datetime
    members: list[MemberOut]
    rounds: list[RoundSummary] = Field(default_factory=list)
    # The round still being decided, if there is one. The group page is a
    # launcher when this is null and a signpost when it isn't.
    active_round: RoundSummary | None = None
    advisories: list[dict] = Field(default_factory=list)
    you: GroupYou | None = None


class RoundCreate(BaseModel):
    """Who's actually eating tonight.

    Absent `member_ids` means everyone. Naming a subset matters: including a
    member who isn't coming would apply their dietary constraints to a meal
    they aren't at, which narrows the options for no reason.
    """

    member_ids: list[uuid.UUID] | None = None
    radius_m: int = Field(default=4828, ge=500, le=40_300)


class RoundCreated(BaseModel):
    slug: str
    status: str
    candidates: list[CandidateOut]
    advisories: list[dict] = Field(default_factory=list)
    unverified_used: bool = False


class RankingIn(BaseModel):
    ordered_candidate_ids: list[uuid.UUID] = Field(min_length=1)

    @field_validator("ordered_candidate_ids")
    @classmethod
    def no_duplicates(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(value)) != len(value):
            raise ValueError("a ranking cannot list the same candidate twice")
        return value


class RankingAccepted(BaseModel):
    submitted: int
    total: int
    status: str
