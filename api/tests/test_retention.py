"""Retention sweep.

This module deletes things, so the tests care as much about what survives as
about what goes. A bug here is unrecoverable by definition.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app import retention
from app.config import settings
from app.models import Candidate, Group, Member, Participant, Place, Ranking, Result, Session, TileCache
from tests.fixtures import CENTER_LAT, CENTER_LON, PEOPLE, RANKINGS, seed_world

FOUNDER = {
    "name": "Maazin",
    "lat": CENTER_LAT,
    "lon": CENTER_LON,
    "hard_constraints": {"diets": [], "max_distance_m": 20000},
}


def auth(token: str) -> dict:
    return {"X-Participant-Token": token}


async def count(db, model) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def build_group(client, db, people=PEOPLE):
    """A group with one decided round, through the real API."""
    await seed_world(db)
    name, diets = people[0]
    created = await client.post(
        "/api/groups",
        json={"name": "Thursday", "founder": {**FOUNDER, "name": name, "hard_constraints": {"diets": diets, "max_distance_m": 20000}}},
    )
    group = created.json()
    tokens = {name: group["token"]}
    for index, (member, member_diets) in enumerate(people[1:], start=1):
        joined = await client.post(
            f"/api/groups/{group['slug']}/members",
            json={
                "name": member,
                "lat": CENTER_LAT + index * 0.0002,
                "lon": CENTER_LON - index * 0.0002,
                "hard_constraints": {"diets": member_diets, "max_distance_m": 20000},
            },
        )
        tokens[member] = joined.json()["token"]

    started = await client.post(f"/api/groups/{group['slug']}/rounds", json={}, headers=auth(tokens[name]))
    ids = [c["id"] for c in started.json()["candidates"]]
    for token in tokens.values():
        await client.post(
            f"/api/sessions/{started.json()['slug']}/rankings",
            json={"ordered_candidate_ids": ids},
            headers=auth(token),
        )
    return group["slug"], started.json()["slug"], tokens


# --------------------------------------------------------------------------
# what goes
# --------------------------------------------------------------------------


async def test_an_expired_round_takes_its_whole_subtree(client, db):
    """The expired round screen says "delete themselves. Nothing to recover."
    Everything attached has to go, or that sentence is a lie."""
    group_slug, round_slug, _ = await build_group(client, db)

    assert await count(db, Session) == 1
    assert await count(db, Participant) == 6
    assert await count(db, Candidate) > 0
    assert await count(db, Ranking) > 0
    assert await count(db, Result) == 1

    # Push the round past its expiry.
    session = (await db.execute(select(Session).where(Session.slug == round_slug))).scalar_one()
    session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db.commit()

    swept = await retention.purge(db)
    assert swept.sessions == 1

    assert await count(db, Session) == 0
    assert await count(db, Participant) == 0
    assert await count(db, Candidate) == 0
    assert await count(db, Ranking) == 0
    assert await count(db, Result) == 0


async def test_a_dormant_group_takes_its_members(client, db):
    group_slug, _, _ = await build_group(client, db)

    group = (await db.execute(select(Group).where(Group.slug == group_slug))).scalar_one()
    group.last_active_at = datetime.now(UTC) - timedelta(days=settings.group_retention_days + 1)
    await db.commit()

    swept = await retention.purge(db)
    assert swept.groups == 1
    assert await count(db, Group) == 0
    assert await count(db, Member) == 0


# --------------------------------------------------------------------------
# what stays
# --------------------------------------------------------------------------


async def test_a_live_round_survives(client, db):
    await build_group(client, db)
    swept = await retention.purge(db)

    assert swept.sessions == 0
    assert await count(db, Session) == 1
    assert await count(db, Result) == 1


async def test_an_active_group_survives_its_expired_rounds(client, db):
    """The group page says a round expires and "the group stays"."""
    group_slug, round_slug, _ = await build_group(client, db)

    session = (await db.execute(select(Session).where(Session.slug == round_slug))).scalar_one()
    session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db.commit()

    await retention.purge(db)

    assert await count(db, Session) == 0
    assert await count(db, Group) == 1
    assert await count(db, Member) == 6
    assert (await client.get(f"/api/groups/{group_slug}")).status_code == 200


async def test_the_place_cache_is_left_alone(client, db):
    """Places and tiles hold no personal data. Dropping them would send every
    group back to Overpass for results it already fetched."""
    await build_group(client, db)
    places_before = await count(db, Place)
    tiles_before = await count(db, TileCache)
    assert places_before > 0 and tiles_before > 0

    session = (await db.execute(select(Session))).scalars().first()
    session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db.commit()

    await retention.purge(db)
    assert await count(db, Place) == places_before
    assert await count(db, TileCache) == tiles_before


# --------------------------------------------------------------------------
# behaviour of the sweep itself
# --------------------------------------------------------------------------


async def test_purge_is_safe_to_run_on_an_empty_database(db):
    swept = await retention.purge(db)
    assert swept.sessions == 0 and swept.groups == 0


async def test_purge_is_idempotent(client, db):
    _, round_slug, _ = await build_group(client, db)
    session = (await db.execute(select(Session).where(Session.slug == round_slug))).scalar_one()
    session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db.commit()

    first = await retention.purge(db)
    second = await retention.purge(db)
    assert first.sessions == 1
    assert second.sessions == 0


async def test_pending_reports_without_deleting(client, db):
    _, round_slug, _ = await build_group(client, db)
    session = (await db.execute(select(Session).where(Session.slug == round_slug))).scalar_one()
    session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db.commit()

    due = await retention.pending(db)
    assert due.sessions == 1
    assert await count(db, Session) == 1, "pending must not delete anything"
