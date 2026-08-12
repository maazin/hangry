"""Phase 1 — sessions, joining, and the participant token."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app import slug as slug_module
from app.models import Session
from tests.fixtures import CENTER_LAT, CENTER_LON, PEOPLE, seed_world

CREATOR = {
    "name": "Maazin",
    "lat": CENTER_LAT,
    "lon": CENTER_LON,
    "hard_constraints": {"diets": [], "max_distance_m": 20000},
}


async def create(client, **overrides):
    body = {"creator": CREATOR, "radius_m": 5000, **overrides}
    response = await client.post("/api/sessions", json=body)
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------
# creating
# --------------------------------------------------------------------------


async def test_create_returns_a_shareable_link_and_enrols_the_creator(client):
    body = await create(client)
    assert len(body["slug"]) == slug_module.SLUG_LENGTH
    assert body["status"] == "collecting"
    assert body["token"] and body["participant_id"]

    state = await client.get(f"/api/sessions/{body['slug']}")
    assert [p["display_name"] for p in state.json()["participants"]] == ["Maazin"]
    assert state.json()["participants"][0]["is_creator"] is True


async def test_slugs_avoid_ambiguous_characters(client):
    """Slugs get read aloud and retyped from a group chat."""
    for _ in range(20):
        assert not set(slug_module.new_slug()) & set("ILOU01")


async def test_slug_collision_retries_instead_of_failing(client, monkeypatch, db):
    """6 chars of a 30-char alphabet collides rarely, not never."""
    from app import routes

    taken = await create(client)
    sequence = iter([taken["slug"], taken["slug"], "FRESH1"])
    # routes imports the name directly, so the binding to patch is there.
    monkeypatch.setattr(routes, "new_slug", lambda: next(sequence))

    body = await create(client)
    assert body["slug"] == "FRESH1"

    rows = await db.execute(select(Session.slug))
    assert sorted(rows.scalars().all()) == sorted([taken["slug"], "FRESH1"])


async def test_creating_rejects_nonsense_coordinates(client):
    response = await client.post(
        "/api/sessions",
        json={"creator": {**CREATOR, "lat": 999.0}, "radius_m": 5000},
    )
    assert response.status_code == 422


async def test_unknown_diets_are_rejected(client):
    response = await client.post(
        "/api/sessions",
        json={"creator": {**CREATOR, "hard_constraints": {"diets": ["carnivore"]}}},
    )
    assert response.status_code == 422
    assert "carnivore" in response.text


# --------------------------------------------------------------------------
# joining
# --------------------------------------------------------------------------


async def test_joiner_needs_no_account(client):
    session = await create(client)
    response = await client.post(
        f"/api/sessions/{session['slug']}/participants",
        json={"name": "Sam", "lat": CENTER_LAT, "lon": CENTER_LON, "hard_constraints": {"diets": ["gluten_free"]}},
    )
    assert response.status_code == 200
    assert response.json()["token"]

    state = await client.get(f"/api/sessions/{session['slug']}")
    assert [p["display_name"] for p in state.json()["participants"]] == ["Maazin", "Sam"]


async def test_duplicate_names_are_disambiguated(client):
    """Names are the identity in every result string, so one Sam must not
    silently absorb the other's rankings."""
    session = await create(client)
    for _ in range(2):
        await client.post(
            f"/api/sessions/{session['slug']}/participants",
            json={"name": "Sam", "lat": CENTER_LAT, "lon": CENTER_LON, "hard_constraints": {}},
        )

    state = await client.get(f"/api/sessions/{session['slug']}")
    assert [p["display_name"] for p in state.json()["participants"]] == ["Maazin", "Sam", "Sam (2)"]


async def test_join_after_start_is_rejected(client, db):
    """v1 refuses mid-round joins outright. Handling them means re-running the
    feasibility filter and invalidating rankings already submitted."""
    await seed_world(db)
    session = await create(client)
    headers = {"X-Participant-Token": session["token"]}

    started = await client.post(f"/api/sessions/{session['slug']}/start", headers=headers)
    assert started.status_code == 200, started.text

    late = await client.post(
        f"/api/sessions/{session['slug']}/participants",
        json={"name": "Latecomer", "lat": CENTER_LAT, "lon": CENTER_LON, "hard_constraints": {}},
    )
    assert late.status_code == 409
    assert late.json()["detail"]["code"] == "already_started"


async def test_unknown_slug_is_404(client):
    assert (await client.get("/api/sessions/NOPE12")).status_code == 404


async def test_expired_session_is_gone_not_missing(client, db):
    """A dead link is an expected state, not something the joiner did wrong."""
    session = await create(client)
    row = (await db.execute(select(Session).where(Session.slug == session["slug"]))).scalar_one()
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db.commit()

    response = await client.get(f"/api/sessions/{session['slug']}")
    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "session_expired"


# --------------------------------------------------------------------------
# the participant token
# --------------------------------------------------------------------------


async def test_token_from_another_session_is_rejected(client, db):
    """Tokens are scoped to a session, so one from session A is simply
    unknown in session B."""
    await seed_world(db)
    a, b = await create(client), await create(client)

    response = await client.post(
        f"/api/sessions/{b['slug']}/start",
        headers={"X-Participant-Token": a["token"]},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "unknown_token"


async def test_missing_token_is_401(client, db):
    await seed_world(db)
    session = await create(client)
    response = await client.post(f"/api/sessions/{session['slug']}/start")
    assert response.status_code == 401


async def test_only_the_creator_can_start(client, db):
    await seed_world(db)
    session = await create(client)
    joiner = await client.post(
        f"/api/sessions/{session['slug']}/participants",
        json={"name": "Sam", "lat": CENTER_LAT, "lon": CENTER_LON, "hard_constraints": {}},
    )

    response = await client.post(
        f"/api/sessions/{session['slug']}/start",
        headers={"X-Participant-Token": joiner.json()["token"]},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "creator_only"
