"""Groups, the durable layer that makes the second meal cheap.

A session decides one meal and evaporates. A group is the six people who keep
having the argument, so it holds their names, locations and dietary
constraints and hands them to every round. The first meal costs what it
always did; the fifth costs two taps.

Still no accounts. The group is its link, membership is an opaque token in
localStorage, and that token doubles as the participant token inside every
round so a phone only ever stores one string per group.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import feasibility as feas
from app.config import settings
from app.deps import CurrentGroup, CurrentMember, DbSession, OptionalMember
from app.models import Group, Member, Participant, Ranking, Result, Session
from app.routes import run_start
from app.schemas import (
    GroupCreate,
    GroupCreated,
    GroupState,
    GroupYou,
    MemberOut,
    MemberUpdate,
    ParticipantIn,
    RoundCreate,
    RoundCreated,
    RoundSummary,
)
from app.slug import new_slug, new_token

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/groups")

LIVE_STATUSES = ("collecting", "ranking")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


async def _unique_member_name(db: DbSession, group_id: uuid.UUID, wanted: str) -> str:
    """Names identify people in every result sentence, so two Sams must not
    collapse into one."""
    rows = await db.execute(select(Member.display_name).where(Member.group_id == group_id))
    taken = set(rows.scalars().all())
    if wanted not in taken:
        return wanted
    for n in range(2, 100):
        if (candidate := f"{wanted} ({n})") not in taken:
            return candidate
    return f"{wanted} ({uuid.uuid4().hex[:4]})"


async def _round_summary(db: DbSession, session: Session) -> RoundSummary:
    participant_ids = [p.id for p in session.participants]
    submitted = 0
    if participant_ids:
        count = await db.execute(
            select(func.count(func.distinct(Ranking.participant_id))).where(
                Ranking.participant_id.in_(participant_ids)
            )
        )
        submitted = count.scalar_one() or 0

    winner = None
    if session.status == "decided":
        stored = await db.get(Result, session.id)
        if stored and stored.ranked:
            winner = stored.ranked[0].get("name")

    return RoundSummary(
        slug=session.slug,
        status=session.status,
        created_at=session.created_at,
        expires_at=session.expires_at,
        participants=len(participant_ids),
        submitted=submitted,
        winner=winner,
    )


async def _build_group_state(db: DbSession, group: Group, member: Member | None) -> GroupState:
    rows = await db.execute(
        select(Session).where(Session.group_id == group.id).order_by(Session.created_at.desc()).limit(12)
    )
    sessions = list(rows.scalars().all())

    now = datetime.now(UTC)
    summaries = [await _round_summary(db, s) for s in sessions]

    # A round that ran out of clock is over, whatever its status column says.
    active = next(
        (s for s, summary in zip(sessions, summaries) if s.status in LIVE_STATUSES and s.expires_at > now),
        None,
    )
    active_summary = next((summary for s, summary in zip(sessions, summaries) if s is active), None)

    members = sorted(group.members, key=lambda m: m.joined_at)

    return GroupState(
        slug=group.slug,
        name=group.name,
        created_at=group.created_at,
        members=[MemberOut.model_validate(m) for m in members],
        rounds=summaries,
        active_round=active_summary,
        # Surfaced on the group page too, so an allergy nobody can verify is
        # visible before a round starts rather than only inside one.
        advisories=feas.advisories(members),
        you=(
            GroupYou(member_id=member.id, display_name=member.display_name, is_founder=member.is_founder)
            if member
            else None
        ),
    )


# --------------------------------------------------------------------------
# group lifecycle
# --------------------------------------------------------------------------


@router.post("", response_model=GroupCreated)
async def create_group(body: GroupCreate, db: DbSession) -> GroupCreated:
    group = None
    for _ in range(8):
        group = Group(slug=new_slug(), name=body.name.strip())
        db.add(group)
        try:
            await db.flush()
            break
        except IntegrityError:
            await db.rollback()
            group = None

    if group is None:
        raise HTTPException(503, detail={"code": "slug_exhausted", "message": "Could not allocate a link. Try again."})

    token = new_token()
    founder = Member(
        group_id=group.id,
        token=token,
        display_name=body.founder.name.strip(),
        lat=body.founder.lat,
        lon=body.founder.lon,
        hard_constraints=body.founder.hard_constraints.model_dump(),
        is_founder=True,
    )
    db.add(founder)
    await db.commit()
    await db.refresh(founder)

    return GroupCreated(slug=group.slug, member_id=founder.id, token=token)


@router.get("/{slug}", response_model=GroupState)
async def read_group(group: CurrentGroup, db: DbSession, member: OptionalMember) -> GroupState:
    return await _build_group_state(db, group, member)


@router.post("/{slug}/members", response_model=GroupCreated)
async def join_group(body: ParticipantIn, group: CurrentGroup, db: DbSession) -> GroupCreated:
    """Join a group. Unlike joining a session, this has no closing time, that's the point of a group."""
    token = new_token()
    member = Member(
        group_id=group.id,
        token=token,
        display_name=await _unique_member_name(db, group.id, body.name.strip()),
        lat=body.lat,
        lon=body.lon,
        hard_constraints=body.hard_constraints.model_dump(),
        is_founder=False,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    return GroupCreated(slug=group.slug, member_id=member.id, token=token)


@router.patch("/{slug}/members/me", response_model=MemberOut)
async def update_me(body: MemberUpdate, group: CurrentGroup, db: DbSession, member: CurrentMember) -> MemberOut:
    """Change your own details.

    Rounds snapshot constraints when they start, so this never rewrites a
    decision the group already made, it only affects the next one.
    """
    if body.name is not None:
        stripped = body.name.strip()
        if stripped != member.display_name:
            member.display_name = await _unique_member_name(db, group.id, stripped)
    if body.lat is not None:
        member.lat = body.lat
    if body.lon is not None:
        member.lon = body.lon
    if body.hard_constraints is not None:
        member.hard_constraints = body.hard_constraints.model_dump()

    await db.commit()
    await db.refresh(member)
    return MemberOut.model_validate(member)


@router.delete("/{slug}/members/me", status_code=204, response_class=Response)
async def leave_group(group: CurrentGroup, db: DbSession, member: CurrentMember) -> Response:
    """Leave. Past rounds keep the snapshot, so old results stay readable."""
    await db.delete(member)
    await db.commit()
    return Response(status_code=204)


# --------------------------------------------------------------------------
# rounds
# --------------------------------------------------------------------------


@router.post("/{slug}/rounds", response_model=RoundCreated)
async def start_round(body: RoundCreate, group: CurrentGroup, db: DbSession, member: CurrentMember) -> RoundCreated:
    """Start a round for whoever's eating.

    Everyone's constraints are already known, so this both creates the round
    and runs the solve setup, asking someone to tap "start" afterwards would
    be re-asking a question the group already answered.
    """
    now = datetime.now(UTC)
    existing = await db.execute(
        select(Session).where(
            Session.group_id == group.id,
            Session.status.in_(LIVE_STATUSES),
            Session.expires_at > now,
        )
    )
    if (live := existing.scalars().first()) is not None:
        raise HTTPException(
            409,
            detail={
                "code": "round_in_progress",
                "message": "This group already has a round going.",
                "slug": live.slug,
            },
        )

    roster = sorted(group.members, key=lambda m: m.joined_at)
    if body.member_ids is not None:
        wanted = set(body.member_ids)
        roster = [m for m in roster if m.id in wanted]

    if not roster:
        raise HTTPException(
            422,
            detail={"code": "nobody_eating", "message": "Pick at least one person who's actually eating."},
        )

    session = None
    for _ in range(8):
        session = Session(
            slug=new_slug(),
            group_id=group.id,
            status="collecting",
            radius_m=body.radius_m,
            expires_at=now + timedelta(hours=settings.session_ttl_hours),
        )
        db.add(session)
        try:
            await db.flush()
            break
        except IntegrityError:
            await db.rollback()
            session = None

    if session is None:
        raise HTTPException(503, detail={"code": "slug_exhausted", "message": "Could not allocate a link. Try again."})

    for person in roster:
        db.add(
            Participant(
                session_id=session.id,
                member_id=person.id,
                # The member's group token *is* their round token, so nobody
                # re-authenticates and no second string is stored anywhere.
                token=person.token,
                display_name=person.display_name,
                lat=person.lat,
                lon=person.lon,
                # Snapshot, not a join, see Participant.member_id.
                hard_constraints=dict(person.hard_constraints or {}),
                is_creator=person.id == member.id,
            )
        )

    await db.commit()
    await db.refresh(session)

    started = await run_start(db, session)
    return RoundCreated(
        slug=session.slug,
        status=started.status,
        candidates=started.candidates,
        advisories=started.advisories,
        unverified_used=started.unverified_used,
    )
