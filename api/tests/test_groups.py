"""Groups, the durable layer.

The point of a group is that the *second* meal is cheap: nobody re-enters a
name, a location, or a dietary constraint. Most of these tests are really
asserting that.
"""

import pytest

from tests.fixtures import CENTER_LAT, CENTER_LON, PEOPLE, seed_world

FOUNDER = {
    "name": "Maazin",
    "lat": CENTER_LAT,
    "lon": CENTER_LON,
    "hard_constraints": {"diets": [], "max_distance_m": 20000},
}


def auth(token: str) -> dict:
    return {"X-Participant-Token": token}


async def make_group(client, name="Thursday Dinner", founder=FOUNDER):
    response = await client.post("/api/groups", json={"name": name, "founder": founder})
    assert response.status_code == 200, response.text
    return response.json()


async def add_member(client, slug, name, diets=(), lat=CENTER_LAT, lon=CENTER_LON):
    response = await client.post(
        f"/api/groups/{slug}/members",
        json={"name": name, "lat": lat, "lon": lon, "hard_constraints": {"diets": list(diets), "max_distance_m": 20000}},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def full_group(client, db, people=PEOPLE):
    """The six-person group from the fixture, as a group rather than a session."""
    await seed_world(db)
    founder_name, founder_diets = people[0]
    group = await make_group(
        client,
        founder={**FOUNDER, "name": founder_name, "hard_constraints": {"diets": founder_diets, "max_distance_m": 20000}},
    )
    tokens = {founder_name: group["token"]}
    for index, (name, diets) in enumerate(people[1:], start=1):
        joined = await add_member(client, group["slug"], name, diets, CENTER_LAT + index * 0.0002, CENTER_LON - index * 0.0002)
        tokens[name] = joined["token"]
    return group["slug"], tokens


# --------------------------------------------------------------------------
# membership
# --------------------------------------------------------------------------


async def test_creating_a_group_enrols_the_founder(client):
    group = await make_group(client)
    assert group["slug"] and group["token"]

    state = (await client.get(f"/api/groups/{group['slug']}")).json()
    assert state["name"] == "Thursday Dinner"
    assert [m["display_name"] for m in state["members"]] == ["Maazin"]
    assert state["members"][0]["is_founder"] is True
    assert state["rounds"] == [] and state["active_round"] is None


async def test_anyone_with_the_link_can_join_and_invite(client):
    """There is no invite list, the link is the invite, so a joiner can pass
    it on without the founder being involved."""
    group = await make_group(client)
    await add_member(client, group["slug"], "Sam", ["gluten_free"])
    await add_member(client, group["slug"], "Priya", ["vegetarian"])

    state = (await client.get(f"/api/groups/{group['slug']}")).json()
    assert [m["display_name"] for m in state["members"]] == ["Maazin", "Sam", "Priya"]
    assert state["members"][1]["hard_constraints"]["diets"] == ["gluten_free"]


async def test_a_group_link_does_not_expire(client):
    """Unlike a session. A group lives in the chat's pinned messages."""
    group = await make_group(client)
    assert (await client.get(f"/api/groups/{group['slug']}")).status_code == 200


async def test_unknown_group_is_404(client):
    assert (await client.get("/api/groups/NOPE12")).status_code == 404


async def test_duplicate_names_are_disambiguated(client):
    group = await make_group(client)
    for _ in range(2):
        await add_member(client, group["slug"], "Sam")

    state = (await client.get(f"/api/groups/{group['slug']}")).json()
    assert [m["display_name"] for m in state["members"]] == ["Maazin", "Sam", "Sam (2)"]


async def test_the_group_tells_a_token_holder_who_they_are(client):
    group = await make_group(client)
    sam = await add_member(client, group["slug"], "Sam")

    anonymous = (await client.get(f"/api/groups/{group['slug']}")).json()
    assert anonymous["you"] is None

    mine = (await client.get(f"/api/groups/{group['slug']}", headers=auth(sam["token"]))).json()
    assert mine["you"]["display_name"] == "Sam" and mine["you"]["is_founder"] is False


async def test_members_can_correct_their_own_details(client):
    group = await make_group(client)
    sam = await add_member(client, group["slug"], "Sam")

    updated = await client.patch(
        f"/api/groups/{group['slug']}/members/me",
        json={"hard_constraints": {"diets": ["gluten_free", "halal"], "max_distance_m": 3000}},
        headers=auth(sam["token"]),
    )
    assert updated.status_code == 200
    assert updated.json()["hard_constraints"]["diets"] == ["gluten_free", "halal"]


async def test_a_partial_update_leaves_the_rest_alone(client):
    """Moving location before dinner shouldn't require resending your diet."""
    group = await make_group(client)
    sam = await add_member(client, group["slug"], "Sam", ["gluten_free"])

    response = await client.patch(
        f"/api/groups/{group['slug']}/members/me",
        json={"lat": 41.0, "lon": -74.5},
        headers=auth(sam["token"]),
    )
    assert response.json()["hard_constraints"]["diets"] == ["gluten_free"]


async def test_a_stranger_cannot_edit_the_group(client):
    group = await make_group(client)
    response = await client.patch(
        f"/api/groups/{group['slug']}/members/me",
        json={"name": "Impostor"},
        headers=auth("not-a-real-token"),
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "not_a_member"


async def test_leaving_removes_you_from_the_roster(client):
    group = await make_group(client)
    sam = await add_member(client, group["slug"], "Sam")

    assert (await client.delete(f"/api/groups/{group['slug']}/members/me", headers=auth(sam["token"]))).status_code == 204

    state = (await client.get(f"/api/groups/{group['slug']}")).json()
    assert [m["display_name"] for m in state["members"]] == ["Maazin"]


# --------------------------------------------------------------------------
# rounds, the payoff
# --------------------------------------------------------------------------


async def test_a_round_starts_with_nobody_re_entering_anything(client, db):
    """The whole point. Six people, and the round is ready to rank
    immediately, no join step, no constraint form, no waiting."""
    slug, tokens = await full_group(client, db)

    started = await client.post(f"/api/groups/{slug}/rounds", json={}, headers=auth(tokens["Maazin"]))
    assert started.status_code == 200, started.text

    body = started.json()
    assert body["status"] == "ranking"
    assert body["candidates"]

    # And every member is already a participant, with their diet applied.
    round_state = (await client.get(f"/api/sessions/{body['slug']}")).json()
    assert sorted(p["display_name"] for p in round_state["participants"]) == sorted(n for n, _ in PEOPLE)


async def test_the_group_token_works_inside_the_round(client, db):
    """One string per group on the phone, not one per round."""
    slug, tokens = await full_group(client, db)
    started = (await client.post(f"/api/groups/{slug}/rounds", json={}, headers=auth(tokens["Maazin"]))).json()

    me = (await client.get(f"/api/sessions/{started['slug']}", headers=auth(tokens["Jordan"]))).json()
    assert me["you"]["display_name"] == "Jordan"
    assert me["you"]["has_ranked"] is False


async def test_a_round_can_exclude_people_who_arent_coming(client, db):
    """Applying an absent member's dietary constraint would narrow the options
    for a meal they aren't at."""
    slug, tokens = await full_group(client, db)
    state = (await client.get(f"/api/groups/{slug}")).json()
    coming = [m["id"] for m in state["members"] if m["display_name"] in ("Maazin", "Ana", "Jordan")]

    started = await client.post(
        f"/api/groups/{slug}/rounds", json={"member_ids": coming}, headers=auth(tokens["Maazin"])
    )
    assert started.status_code == 200

    round_state = (await client.get(f"/api/sessions/{started.json()['slug']}")).json()
    assert sorted(p["display_name"] for p in round_state["participants"]) == ["Ana", "Jordan", "Maazin"]
    # Nobody's dietary constraint is in play, so nothing is flagged for one.
    assert round_state["advisories"] == []


async def test_excluding_everyone_is_refused(client, db):
    slug, tokens = await full_group(client, db)
    response = await client.post(
        f"/api/groups/{slug}/rounds", json={"member_ids": []}, headers=auth(tokens["Maazin"])
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "nobody_eating"


async def test_only_members_can_start_a_round(client, db):
    slug, _ = await full_group(client, db)
    response = await client.post(f"/api/groups/{slug}/rounds", json={}, headers=auth("outsider"))
    assert response.status_code == 403


async def test_two_rounds_cannot_run_at_once(client, db):
    """Otherwise half the group ranks one round and half the other."""
    slug, tokens = await full_group(client, db)
    first = (await client.post(f"/api/groups/{slug}/rounds", json={}, headers=auth(tokens["Maazin"]))).json()

    second = await client.post(f"/api/groups/{slug}/rounds", json={}, headers=auth(tokens["Ana"]))
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "round_in_progress"
    # And it points at the one already going, so the UI can just send them there.
    assert second.json()["detail"]["slug"] == first["slug"]


async def test_the_group_page_points_at_the_live_round(client, db):
    slug, tokens = await full_group(client, db)
    started = (await client.post(f"/api/groups/{slug}/rounds", json={}, headers=auth(tokens["Maazin"]))).json()

    state = (await client.get(f"/api/groups/{slug}")).json()
    assert state["active_round"]["slug"] == started["slug"]
    assert state["active_round"]["status"] == "ranking"
    assert state["active_round"]["participants"] == 6
    assert state["active_round"]["submitted"] == 0


async def test_a_decided_round_shows_its_winner_in_the_group_history(client, db):
    slug, tokens = await full_group(client, db)
    started = (await client.post(f"/api/groups/{slug}/rounds", json={}, headers=auth(tokens["Maazin"]))).json()
    ids = [c["id"] for c in started["candidates"]]

    for name in tokens:
        response = await client.post(
            f"/api/sessions/{started['slug']}/rankings",
            json={"ordered_candidate_ids": ids},
            headers=auth(tokens[name]),
        )
        assert response.status_code == 200, response.text

    state = (await client.get(f"/api/groups/{slug}")).json()
    assert state["active_round"] is None, "a decided round is not live"
    assert len(state["rounds"]) == 1
    assert state["rounds"][0]["status"] == "decided"
    assert state["rounds"][0]["winner"]


async def test_a_second_round_reuses_everything(client, db):
    """The retention mechanic: round two costs one call and no data entry."""
    slug, tokens = await full_group(client, db)
    first = (await client.post(f"/api/groups/{slug}/rounds", json={}, headers=auth(tokens["Maazin"]))).json()
    ids = [c["id"] for c in first["candidates"]]
    for name in tokens:
        await client.post(
            f"/api/sessions/{first['slug']}/rankings", json={"ordered_candidate_ids": ids}, headers=auth(tokens[name])
        )

    second = await client.post(f"/api/groups/{slug}/rounds", json={}, headers=auth(tokens["Priya"]))
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "ranking"
    assert second.json()["slug"] != first["slug"]

    state = (await client.get(f"/api/groups/{slug}")).json()
    assert len(state["rounds"]) == 2


async def test_editing_a_diet_does_not_rewrite_a_past_round(client, db):
    """Rounds snapshot constraints. A decision has to stay readable as it was
    actually made."""
    slug, tokens = await full_group(client, db)
    started = (await client.post(f"/api/groups/{slug}/rounds", json={}, headers=auth(tokens["Maazin"]))).json()

    before = (await client.get(f"/api/sessions/{started['slug']}")).json()
    sam_before = next(p for p in before["participants"] if p["display_name"] == "Sam")
    assert sam_before["hard_constraints"]["diets"] == ["gluten_free"]

    await client.patch(
        f"/api/groups/{slug}/members/me",
        json={"hard_constraints": {"diets": ["vegan"]}},
        headers=auth(tokens["Sam"]),
    )

    after = (await client.get(f"/api/sessions/{started['slug']}")).json()
    sam_after = next(p for p in after["participants"] if p["display_name"] == "Sam")
    assert sam_after["hard_constraints"]["diets"] == ["gluten_free"]


async def test_group_surfaces_unverifiable_allergies_before_a_round(client, db):
    """Better to learn the data can't check your allergy on the group page
    than halfway through ranking."""
    people = [("Maazin", []), ("Jordan", ["nut_allergy"])]
    slug, _ = await full_group(client, db, people=people)

    state = (await client.get(f"/api/groups/{slug}")).json()
    assert state["advisories"] and state["advisories"][0]["participant"] == "Jordan"
    assert "no allergen data" in state["advisories"][0]["detail"]
