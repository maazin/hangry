"""Shared route dependencies: session lookup and participant identification."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Group, Member, Participant, Session

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_session(slug: Annotated[str, Path()], db: DbSession) -> Session:
    """Load a session by slug, refusing expired ones.

    Expired returns 410 rather than 404 so the frontend can render "this
    session has expired, start a new one" instead of a generic not-found.
    Sessions are ephemeral by design; a dead link is an expected state, not
    an error the joiner did something wrong to reach.
    """
    result = await db.execute(select(Session).where(Session.slug == slug.upper()))
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(404, detail={"code": "unknown_session", "message": "No session with that link."})

    if session.expires_at <= datetime.now(UTC):
        if session.status != "expired":
            session.status = "expired"
            await db.commit()
        raise HTTPException(
            410,
            detail={"code": "session_expired", "message": "This session has expired. Sessions last 24 hours."},
        )

    return session


CurrentSession = Annotated[Session, Depends(get_session)]


async def get_participant(
    session: CurrentSession,
    db: DbSession,
    x_participant_token: Annotated[str | None, Header()] = None,
) -> Participant:
    """Identify the caller within this session.

    Not real auth. It stops accidental cross-writes between the six people in
    a group chat and nothing more, which is the correct level of security for
    an ephemeral session holding no personal data. The token is scoped to the
    session, so a token from session A is simply unknown in session B.
    """
    if not x_participant_token:
        raise HTTPException(401, detail={"code": "missing_token", "message": "Missing X-Participant-Token."})

    result = await db.execute(
        select(Participant).where(
            Participant.session_id == session.id,
            Participant.token == x_participant_token,
        )
    )
    participant = result.scalar_one_or_none()
    if participant is None:
        raise HTTPException(403, detail={"code": "unknown_token", "message": "Not a participant in this session."})

    return participant


CurrentParticipant = Annotated[Participant, Depends(get_participant)]


async def get_group(slug: Annotated[str, Path()], db: DbSession) -> Group:
    """Load a group by slug.

    Unlike a session, a group does not expire on a clock. It is the thing the
    group chat keeps in its pinned messages, so a link that dies after a
    weekend would defeat the point.
    """
    result = await db.execute(select(Group).where(Group.slug == slug.upper()))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(404, detail={"code": "unknown_group", "message": "No group with that link."})

    group.last_active_at = datetime.now(UTC)
    await db.commit()
    return group


CurrentGroup = Annotated[Group, Depends(get_group)]


async def get_member_optional(
    group: CurrentGroup,
    db: DbSession,
    x_participant_token: Annotated[str | None, Header()] = None,
) -> Member | None:
    """Resolve the caller within a group, if they're in it.

    Deliberately the same header as the participant token: a member's group
    token *is* their token in every round, so a phone stores one string per
    group and never has to reconcile two identities.
    """
    if not x_participant_token:
        return None

    result = await db.execute(
        select(Member).where(Member.group_id == group.id, Member.token == x_participant_token)
    )
    member = result.scalar_one_or_none()
    if member is not None:
        member.last_seen_at = datetime.now(UTC)
        await db.commit()
    return member


OptionalMember = Annotated[Member | None, Depends(get_member_optional)]


async def require_member(member: OptionalMember) -> Member:
    if member is None:
        raise HTTPException(
            403,
            detail={"code": "not_a_member", "message": "Join the group before doing that."},
        )
    return member


CurrentMember = Annotated[Member, Depends(require_member)]


async def require_creator(participant: CurrentParticipant) -> Participant:
    if not participant.is_creator:
        raise HTTPException(
            403,
            detail={"code": "creator_only", "message": "Only whoever started the session can do that."},
        )
    return participant


Creator = Annotated[Participant, Depends(require_creator)]
