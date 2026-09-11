"""Deleting what the product promised to delete.

Three places in the interface tell people their data goes away: the location
note on the join form, the round history on the group page, and the expired
round screen, which says rounds "delete themselves. Nothing to recover."

Expiry alone only made those sentences true from the outside. A session past
`expires_at` stopped serving, and every row stayed in the database. This
module is what makes the copy accurate.

What goes:

  rounds and standalone sessions once `expires_at` has passed, taking their
  participants, candidates, rankings and results with them

  groups nobody has opened inside the retention window, taking their members
  and any remaining rounds

What stays: `places` and `tile_cache`. Those hold no personal data, they are
a shared cache of public map data, and throwing them away would send every
group back to Overpass for results it already paid for.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.models import Group, Session

log = logging.getLogger(__name__)


@dataclass
class Swept:
    sessions: int = 0
    groups: int = 0

    def __str__(self) -> str:
        return f"{self.sessions} expired rounds, {self.groups} dormant groups"


async def purge(db: AsyncSession, now: datetime | None = None) -> Swept:
    """Delete what is past its life. Safe to run as often as you like.

    Both deletes lean on `ON DELETE CASCADE` in the schema, so the children
    go with the parent in one statement rather than being walked in Python.
    """
    now = now or datetime.now(UTC)

    expired = await db.execute(delete(Session).where(Session.expires_at <= now))

    dormant_cutoff = now - timedelta(days=settings.group_retention_days)
    dormant = await db.execute(delete(Group).where(Group.last_active_at <= dormant_cutoff))

    await db.commit()
    return Swept(sessions=expired.rowcount or 0, groups=dormant.rowcount or 0)


async def pending(db: AsyncSession, now: datetime | None = None) -> Swept:
    """How much a purge would remove. Used by tests and by the health probe."""
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=settings.group_retention_days)

    sessions = await db.execute(select(func.count()).select_from(Session).where(Session.expires_at <= now))
    groups = await db.execute(select(func.count()).select_from(Group).where(Group.last_active_at <= cutoff))
    return Swept(sessions=sessions.scalar_one(), groups=groups.scalar_one())


async def purge_loop() -> None:
    """Background sweep.

    Runs in the API process because there is one machine and the work is a
    pair of indexed deletes. A separate scheduler would be more moving parts
    than the job deserves. If that stops being true, the same function is
    runnable as `python -m app.retention`.

    A failed sweep is logged and retried on the next tick rather than being
    allowed to take the process down with it.
    """
    interval = timedelta(minutes=settings.purge_interval_minutes).total_seconds()

    while True:
        try:
            async with SessionLocal() as db:
                swept = await purge(db)
            if swept.sessions or swept.groups:
                log.info("retention sweep removed %s", swept)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("retention sweep failed, retrying next tick")

        await asyncio.sleep(interval)


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    async with SessionLocal() as db:
        print(f"removed {await purge(db)}")


if __name__ == "__main__":
    asyncio.run(_main())
