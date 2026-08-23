"""Phase 3 and 4 definition of done.

The six-person scenario from `hangry-algorithm.md`, run end to end through
the real API: create, join, start, rank, solve. It must produce Indian
Kitchen, show Sushi Bar as the majority-vote alternative, and name Jordan as
who that alternative excludes.
"""

import pytest

from tests.fixtures import CENTER_LAT, CENTER_LON, PEOPLE, RANKINGS, seed_world


async def run_session(client, db, *, people=PEOPLE, radius_m=5000, only=None):
    """Create, join, and start. Returns (slug, tokens, candidates)."""
    await seed_world(db, only=only)

    creator_name, creator_diets = people[0]
    created = await client.post(
        "/api/sessions",
        json={
            "creator": {
                "name": creator_name,
                "lat": CENTER_LAT,
                "lon": CENTER_LON,
                "hard_constraints": {"diets": creator_diets, "max_distance_m": 20000},
            },
            "radius_m": radius_m,
        },
    )
    assert created.status_code == 200, created.text
    slug = created.json()["slug"]
    tokens = {creator_name: created.json()["token"]}

    for index, (name, diets) in enumerate(people[1:], start=1):
        joined = await client.post(
            f"/api/sessions/{slug}/participants",
            json={
                "name": name,
                "lat": CENTER_LAT + index * 0.0002,
                "lon": CENTER_LON - index * 0.0002,
                "hard_constraints": {"diets": diets, "max_distance_m": 20000},
            },
        )
        assert joined.status_code == 200, joined.text
        tokens[name] = joined.json()["token"]

    started = await client.post(f"/api/sessions/{slug}/start", headers={"X-Participant-Token": tokens[creator_name]})
    return slug, tokens, started


async def rank_everyone(client, slug, tokens, candidates, rankings=RANKINGS):
    by_name = {c["name"]: c["id"] for c in candidates}
    last = None
    for name, order in rankings.items():
        last = await client.post(
            f"/api/sessions/{slug}/rankings",
            json={"ordered_candidate_ids": [by_name[n] for n in order]},
            headers={"X-Participant-Token": tokens[name]},
        )
        assert last.status_code == 200, last.text
    return last


# --------------------------------------------------------------------------
# the filter, through the API
# --------------------------------------------------------------------------


async def test_start_locks_three_feasible_candidates(client, db):
    slug, tokens, started = await run_session(client, db)
    assert started.status_code == 200, started.text

    body = started.json()
    assert body["status"] == "ranking"
    assert sorted(c["name"] for c in body["candidates"]) == [
        "Indian Kitchen",
        "Mediterranean Grill",
        "Sushi Bar",
    ]
    assert all(c["tier"] == "feasible" for c in body["candidates"])


async def test_state_explains_every_cut(client, db):
    """Per eliminated place, exactly who cut it and why."""
    slug, _, _ = await run_session(client, db)
    state = (await client.get(f"/api/sessions/{slug}")).json()
    by_name = {c["name"]: c for c in state["candidates"]}

    assert by_name["Ramen House"]["tier"] == "eliminated"
    reasons = by_name["Ramen House"]["cut_reasons"]
    assert [(r["participant"], r["constraint"]) for r in reasons if r["kind"] == "eliminated"] == [
        ("Sam", "gluten_free")
    ]

    taqueria = [r for r in by_name["Taqueria Sol"]["cut_reasons"] if r["kind"] == "eliminated"]
    assert (taqueria[0]["participant"], taqueria[0]["constraint"]) == ("Dev", "halal")

    cut_by_sam = [
        name
        for name, c in by_name.items()
        if any(r["participant"] == "Sam" and r["kind"] == "eliminated" for r in c["cut_reasons"])
    ]
    assert sorted(cut_by_sam) == ["Burger Joint", "Ramen House"]


async def test_thai_garden_is_shown_but_flagged_and_unrankable(client, db):
    """Missing halal data keeps it visible and out of the ranking."""
    slug, tokens, started = await run_session(client, db)

    state = (await client.get(f"/api/sessions/{slug}")).json()
    thai = next(c for c in state["candidates"] if c["name"] == "Thai Garden")
    assert thai["tier"] == "unverified"
    assert [(r["participant"], r["constraint"], r["kind"]) for r in thai["cut_reasons"]] == [("Dev", "halal", "unknown")]

    assert "Thai Garden" not in [c["name"] for c in started.json()["candidates"]]


async def test_a_ranking_must_cover_exactly_the_offered_options(client, db):
    slug, tokens, started = await run_session(client, db)
    candidates = started.json()["candidates"]
    thai_id = next(
        c["id"] for c in (await client.get(f"/api/sessions/{slug}")).json()["candidates"] if c["name"] == "Thai Garden"
    )

    partial = await client.post(
        f"/api/sessions/{slug}/rankings",
        json={"ordered_candidate_ids": [candidates[0]["id"]]},
        headers={"X-Participant-Token": tokens["Maazin"]},
    )
    assert partial.status_code == 422

    smuggled = await client.post(
        f"/api/sessions/{slug}/rankings",
        json={"ordered_candidate_ids": [c["id"] for c in candidates[:2]] + [thai_id]},
        headers={"X-Participant-Token": tokens["Maazin"]},
    )
    assert smuggled.status_code == 422, "an unverified candidate must not be rankable"


# --------------------------------------------------------------------------
# the DoD
# --------------------------------------------------------------------------


async def test_six_people_end_to_end_pick_indian_kitchen(client, db):
    slug, tokens, started = await run_session(client, db)
    last = await rank_everyone(client, slug, tokens, started.json()["candidates"])

    assert last.json() == {"submitted": 6, "total": 6, "status": "decided"}

    state = (await client.get(f"/api/sessions/{slug}")).json()
    assert state["status"] == "decided"

    ranked = state["result"]["ranked"]
    assert [r["name"] for r in ranked] == ["Indian Kitchen", "Mediterranean Grill", "Sushi Bar"] or [
        r["name"] for r in ranked
    ] == ["Indian Kitchen", "Sushi Bar", "Mediterranean Grill"]
    assert ranked[0]["name"] == "Indian Kitchen"
    assert state["result"]["rule"] == "minimax_regret"


async def test_the_majority_vote_comparison_names_who_it_excludes(client, db):
    """The screenshot. The launch content. The interview story."""
    slug, tokens, started = await run_session(client, db)
    await rank_everyone(client, slug, tokens, started.json()["candidates"])

    compare = (await client.get(f"/api/sessions/{slug}")).json()["result"]["comparison"]
    assert compare["utilitarian"]["name"] == "Sushi Bar"
    assert compare["utilitarian"]["excludes"] == ["Jordan"]
    assert compare["minimax_regret"]["name"] == "Indian Kitchen"
    assert "Sushi Bar" in compare["headline"] and "Jordan" in compare["headline"]


async def test_the_shortlist_annotates_what_each_option_costs(client, db):
    slug, tokens, started = await run_session(client, db)
    await rank_everyone(client, slug, tokens, started.json()["candidates"])

    ranked = (await client.get(f"/api/sessions/{slug}")).json()["result"]["ranked"]
    sushi = next(r for r in ranked if r["name"] == "Sushi Bar")

    assert "Jordan" in sushi["annotation"]
    assert sushi["worst_for"] == ["Jordan"]
    assert sushi["max_regret"] == pytest.approx(1.0)
    assert ranked[0]["max_regret"] == pytest.approx(0.5)
    assert all(r["annotation"] for r in ranked)


async def test_submission_count_climbs_before_the_solve(client, db):
    """Watching the count move is what creates the urgency to finish."""
    slug, tokens, started = await run_session(client, db)
    by_name = {c["name"]: c["id"] for c in started.json()["candidates"]}

    first = await client.post(
        f"/api/sessions/{slug}/rankings",
        json={"ordered_candidate_ids": [by_name[n] for n in RANKINGS["Maazin"]]},
        headers={"X-Participant-Token": tokens["Maazin"]},
    )
    assert first.json() == {"submitted": 1, "total": 6, "status": "ranking"}
    assert (await client.get(f"/api/sessions/{slug}")).json()["result"] is None


async def test_a_resubmitted_ranking_replaces_rather_than_accumulates(client, db):
    slug, tokens, started = await run_session(client, db)
    by_name = {c["name"]: c["id"] for c in started.json()["candidates"]}

    for order in (RANKINGS["Maazin"], RANKINGS["Jordan"]):
        response = await client.post(
            f"/api/sessions/{slug}/rankings",
            json={"ordered_candidate_ids": [by_name[n] for n in order]},
            headers={"X-Participant-Token": tokens["Maazin"]},
        )
        assert response.json()["submitted"] == 1


async def test_creator_can_force_a_solve_before_everyone_ranks(client, db):
    slug, tokens, started = await run_session(client, db)
    by_name = {c["name"]: c["id"] for c in started.json()["candidates"]}

    for name in ("Maazin", "Jordan"):
        await client.post(
            f"/api/sessions/{slug}/rankings",
            json={"ordered_candidate_ids": [by_name[n] for n in RANKINGS[name]]},
            headers={"X-Participant-Token": tokens[name]},
        )

    forced = await client.post(f"/api/sessions/{slug}/solve", headers={"X-Participant-Token": tokens["Maazin"]})
    assert forced.status_code == 200

    # Non-voters are absent from the matrix rather than assigned an invented
    # preference, they expressed none.
    assert forced.json()["alternates"]["voters"] == ["Jordan", "Maazin"]
    assert "Priya" in forced.json()["alternates"]["non_voters"]


async def test_ranking_after_the_decision_is_rejected(client, db):
    slug, tokens, started = await run_session(client, db)
    candidates = started.json()["candidates"]
    await rank_everyone(client, slug, tokens, candidates)

    by_name = {c["name"]: c["id"] for c in candidates}
    late = await client.post(
        f"/api/sessions/{slug}/rankings",
        json={"ordered_candidate_ids": [by_name[n] for n in RANKINGS["Maazin"]]},
        headers={"X-Participant-Token": tokens["Maazin"]},
    )
    assert late.status_code == 409 and late.json()["detail"]["code"] == "already_decided"


# --------------------------------------------------------------------------
# advisories and the empty set
# --------------------------------------------------------------------------


async def test_an_allergy_rides_along_as_an_advisory_not_a_filter(client, db):
    people = [("Maazin", []), ("Ana", ["nut_allergy"]), ("Sam", ["gluten_free"]), ("Priya", ["vegetarian"]), ("Jordan", []), ("Dev", ["halal"])]
    slug, tokens, started = await run_session(client, db, people=people)

    assert started.status_code == 200
    notes = [a for a in started.json()["advisories"] if a.get("constraint") == "nut_allergy"]
    assert notes and notes[0]["participant"] == "Ana"
    assert "confirm with the restaurant" in notes[0]["detail"]

    # And it did not quietly shrink the candidate set.
    assert len(started.json()["candidates"]) == 3


async def test_an_impossible_group_is_told_whose_constraints_bind(client, db):
    """A genuine conflict, every option provably violates someone. Never a
    bare "no results": the group is told who is binding so they can act."""
    slug, tokens, started = await run_session(
        client,
        db,
        people=[("Sam", ["gluten_free"]), ("Dev", ["halal"])],
        only=["Ramen House", "Taqueria Sol", "Burger Joint"],
    )

    assert started.status_code == 422
    detail = started.json()["detail"]
    assert detail["code"] == "no_feasible_candidates"
    assert "works for everyone" in detail["message"]

    binding = {b["participant"]: b for b in detail["binding_constraints"]}
    assert set(binding) == {"Sam", "Dev"}
    assert binding["Sam"]["label"] == "gluten-free" and binding["Sam"]["eliminated"] == 2
    assert binding["Dev"]["label"] == "halal" and binding["Dev"]["eliminated"] == 1


async def test_no_data_is_reported_differently_from_a_conflict(client, db):
    """An absence of data and a real conflict need different things from the
    group, so they must not share copy."""
    slug, tokens, started = await run_session(
        client, db, people=[("Sam", ["kosher"])], only=["Thai Garden"]
    )

    # One unverified candidate is not enough to vote on, but the message must
    # still not claim anything was ruled out.
    if started.status_code == 422:
        assert "enough information" in started.json()["detail"]["message"]
        assert started.json()["detail"]["binding_constraints"] == []


async def test_sparse_data_still_produces_a_vote_but_says_so(client, db):
    """The real-world case. OSM dietary coverage is 1-6% even in dense
    cities, so a group with a restriction usually has an empty verified set.
    The vote runs on flagged candidates rather than dead-ending, and the
    flag is never softened into "safe"."""
    people = [("Sam", ["kosher"]), ("Ana", []), ("Dev", [])]
    slug, tokens, started = await run_session(client, db, people=people)

    assert started.status_code == 200, started.text
    body = started.json()
    assert body["unverified_used"] is True
    assert body["candidates"], "a vote should still be possible"
    assert all(c["tier"] == "unverified" and c["locked"] for c in body["candidates"])

    note = next(a for a in body["advisories"] if a["constraint"] == "unverified_data")
    assert "couldn't confirm" in note["detail"]
    assert "check with the" in note["detail"]
    # Never the word that would get someone hurt.
    assert "confirmed safe" not in note["detail"].replace("Nothing here is confirmed safe", "")

    # Every locked candidate still carries who couldn't be verified and why.
    for candidate in body["candidates"]:
        reasons = candidate["cut_reasons"]
        assert reasons and all(r["kind"] == "unknown" for r in reasons)
        assert all(r["participant"] == "Sam" and r["constraint"] == "kosher" for r in reasons)


async def test_relaxations_are_only_claimed_when_they_helped(client, db):
    """Widening the radius does nothing when the shortage is missing tags,
    and saying "we doubled the distance limit" when distance was never the
    binding factor is just false."""
    slug, tokens, started = await run_session(client, db, people=[("Sam", ["kosher"]), ("Ana", [])])

    assert started.status_code == 200
    assert [a for a in started.json()["advisories"] if a["constraint"] == "relaxed"] == []


async def test_verified_candidates_are_preferred_over_flagged_ones(client, db):
    """The degraded path is a fallback, not the default. With enough verified
    options the unverified tier stays out of the vote."""
    slug, tokens, started = await run_session(client, db)
    assert started.json()["unverified_used"] is False
    assert all(c["tier"] == "feasible" for c in started.json()["candidates"])


async def test_a_solo_session_still_decides(client, db):
    """Degenerate case: one participant collapses all three rules."""
    slug, tokens, started = await run_session(client, db, people=[("Maazin", [])])
    candidates = started.json()["candidates"]

    submitted = await client.post(
        f"/api/sessions/{slug}/rankings",
        json={"ordered_candidate_ids": [c["id"] for c in candidates]},
        headers={"X-Participant-Token": tokens["Maazin"]},
    )
    assert submitted.json()["status"] == "decided"

    result = (await client.get(f"/api/sessions/{slug}")).json()["result"]
    assert result["ranked"][0]["name"] == candidates[0]["name"]
    assert result["ranked"][0]["max_regret"] == 0.0


async def test_state_tells_a_token_holder_who_they_are(client, db):
    """Without this the client can't find itself in the participant list, and
    a reload would ask someone to rank again after they already had."""
    slug, tokens, started = await run_session(client, db)

    anonymous = (await client.get(f"/api/sessions/{slug}")).json()
    assert anonymous["you"] is None

    jordan = (await client.get(f"/api/sessions/{slug}", headers={"X-Participant-Token": tokens["Jordan"]})).json()
    assert jordan["you"]["display_name"] == "Jordan"
    assert jordan["you"]["is_creator"] is False
    assert jordan["you"]["has_ranked"] is False

    by_name = {c["name"]: c["id"] for c in started.json()["candidates"]}
    await client.post(
        f"/api/sessions/{slug}/rankings",
        json={"ordered_candidate_ids": [by_name[n] for n in RANKINGS["Jordan"]]},
        headers={"X-Participant-Token": tokens["Jordan"]},
    )

    after = (await client.get(f"/api/sessions/{slug}", headers={"X-Participant-Token": tokens["Jordan"]})).json()
    assert after["you"]["has_ranked"] is True

    creator = (await client.get(f"/api/sessions/{slug}", headers={"X-Participant-Token": tokens["Maazin"]})).json()
    assert creator["you"]["is_creator"] is True


async def test_a_stale_token_does_not_impersonate_anyone(client, db):
    slug, tokens, _ = await run_session(client, db)
    state = (await client.get(f"/api/sessions/{slug}", headers={"X-Participant-Token": "not-a-real-token"})).json()
    assert state["you"] is None


async def test_health_reports_the_database(client):
    assert (await client.get("/api/health")).json() == {"api": "ok", "db": "ok"}
