"""Shared route dependencies: session lookup and participant identification."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Participant, Session

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


async def require_creator(participant: CurrentParticipant) -> Participant:
    if not participant.is_creator:
        raise HTTPException(
            403,
            detail={"code": "creator_only", "message": "Only whoever started the session can do that."},
        )
    return participant


Creator = Annotated[Participant, Depends(require_creator)]
