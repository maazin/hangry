"""Stage 1, the feasibility filter, against the table in hangry-algorithm.md.

    | Candidate           | GF  | Veg | Halal   | Result           |
    | Ramen House         | no  | yes | yes     | cut - Sam        |
    | Taqueria Sol        | yes | yes | no      | cut - Dev        |
    | Burger Joint        | no  | yes | yes     | cut - Sam        |
    | Thai Garden         | yes | yes | unknown | unverified tier  |
    | Mediterranean Grill | yes | yes | yes     | feasible         |
    | Indian Kitchen      | yes | yes | yes     | feasible         |
    | Sushi Bar           | yes | yes | yes     | feasible         |
"""

import uuid
from datetime import UTC, datetime

import pytest

from app import feasibility as feas
from app.constraints import Status
from app.models import Participant, Place
from tests.fixtures import make_participants, make_places

NOW = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)  # a Wednesday evening


@pytest.fixture
def verdicts():
    return {v.place.name: v for v in feas.filter_places(make_places(), make_participants(), NOW)}


# --------------------------------------------------------------------------
# the tiering table
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,tier",
    [
        ("Ramen House", feas.TIER_ELIMINATED),
        ("Taqueria Sol", feas.TIER_ELIMINATED),
        ("Burger Joint", feas.TIER_ELIMINATED),
        ("Thai Garden", feas.TIER_UNVERIFIED),
        ("Mediterranean Grill", feas.TIER_FEASIBLE),
        ("Indian Kitchen", feas.TIER_FEASIBLE),
        ("Sushi Bar", feas.TIER_FEASIBLE),
    ],
)
def test_seven_candidates_tier_as_the_doc_says(verdicts, name, tier):
    assert verdicts[name].tier == tier


def test_seven_candidates_become_three(verdicts):
    feasible = [v for v in verdicts.values() if v.tier == feas.TIER_FEASIBLE]
    assert sorted(v.place.name for v in feasible) == ["Indian Kitchen", "Mediterranean Grill", "Sushi Bar"]


def test_thai_garden_is_flagged_not_admitted(verdicts):
    """Thai Garden's halal status is *missing*, not confirmed false.

    Missing is not satisfied. It goes to a visibly flagged tier rather than
    into the feasible set, anyone who actually manages a food restriction
    abandons a product that guesses on this once.
    """
    thai = verdicts["Thai Garden"]
    assert thai.tier == feas.TIER_UNVERIFIED
    assert thai.tier != feas.TIER_FEASIBLE

    reason = next(r for r in thai.reasons if r.constraint == "halal")
    assert reason.kind == "unknown"
    assert reason.participant == "Dev"


def test_an_unknown_never_eliminates(verdicts):
    """Unverified is shown, not deleted. A sparse tag is a data gap, not a
    reason to hide a restaurant from the group."""
    assert all(r.kind != "eliminated" for r in verdicts["Thai Garden"].reasons)


# --------------------------------------------------------------------------
# every cut names a person and a constraint
# --------------------------------------------------------------------------


def test_cuts_name_the_participant_and_the_constraint(verdicts):
    ramen = verdicts["Ramen House"]
    cut = [r for r in ramen.reasons if r.kind == "eliminated"]
    assert [(r.participant, r.constraint) for r in cut] == [("Sam", "gluten_free")]
    assert "Sam" in cut[0].detail

    taqueria = [r for r in verdicts["Taqueria Sol"].reasons if r.kind == "eliminated"]
    assert [(r.participant, r.constraint) for r in taqueria] == [("Dev", "halal")]


def test_no_reason_is_ever_a_bare_boolean(verdicts):
    for verdict in verdicts.values():
        for reason in verdict.reasons:
            assert reason.participant and reason.constraint and reason.detail
            assert reason.kind in ("eliminated", "unknown")


def test_reasons_survive_serialisation(verdicts):
    payload = verdicts["Ramen House"].as_json()
    assert payload[0]["participant"] == "Sam"
    assert payload[0]["constraint"] == "gluten_free"


def test_the_ui_can_say_three_places_were_cut_because_sam_cant_eat_there(verdicts):
    """The exact sentence the PRD requires the UI to be able to produce."""
    by_sam = [
        v.place.name
        for v in verdicts.values()
        if any(r.participant == "Sam" and r.kind == "eliminated" for r in v.reasons)
    ]
    assert sorted(by_sam) == ["Burger Joint", "Ramen House"]

    binding = feas.binding_constraints(list(verdicts.values()))
    assert {"participant": "Sam", "constraint": "gluten_free", "label": "gluten-free", "eliminated": 2} in binding
    assert {"participant": "Dev", "constraint": "halal", "label": "halal", "eliminated": 1} in binding


# --------------------------------------------------------------------------
# distance
# --------------------------------------------------------------------------


def test_distance_eliminates_outright():
    """Distance is known data, so exceeding it is a violation, not an unknown."""
    places = make_places()
    far = Participant(
        id=uuid.uuid4(),
        token="t",
        display_name="Faraway Fran",
        lat=41.5,
        lon=-74.0,
        hard_constraints={"diets": [], "max_distance_m": 5000},
    )
    verdict = feas.evaluate(places[0], [far], NOW)
    assert verdict.tier == feas.TIER_ELIMINATED
    reason = verdict.reasons[0]
    assert reason.constraint == "max_distance_m" and reason.participant == "Faraway Fran"
    assert "km" in reason.detail


def test_distance_is_measured_from_each_person_not_the_centroid():
    """A restaurant next door to one person can still be too far for another."""
    place = make_places()[0]
    near = Participant(id=uuid.uuid4(), token="a", display_name="Near", lat=place.lat, lon=place.lon, hard_constraints={"diets": [], "max_distance_m": 1000})
    far = Participant(id=uuid.uuid4(), token="b", display_name="Far", lat=place.lat + 0.5, lon=place.lon, hard_constraints={"diets": [], "max_distance_m": 1000})

    assert feas.evaluate(place, [near], NOW).tier == feas.TIER_FEASIBLE
    assert feas.evaluate(place, [near, far], NOW).tier == feas.TIER_ELIMINATED


# --------------------------------------------------------------------------
# opening hours
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hours,expected",
    [
        ("Mo-Su 11:00-23:00", Status.SATISFIED),
        ("Mo-Su 11:00-14:00", Status.VIOLATED),
        (None, Status.UNKNOWN),
        ("", Status.UNKNOWN),
        ("this is not opening_hours syntax ((", Status.UNKNOWN),
    ],
)
def test_hours_status(hours, expected):
    assert feas.hours_status(hours, NOW) is expected


def test_hours_are_evaluated_in_local_time_not_utc():
    """A restaurant's opening_hours string is local time. Comparing it to UTC
    calls the same place closed in London and open in Los Angeles."""
    nyc = feas.local_time(NOW, -74.0060)
    assert nyc.tzinfo is None
    assert nyc.hour == 14  # 19:30 UTC is mid-afternoon in New York

    tokyo = feas.local_time(NOW, 139.69)
    assert tokyo.hour == 4  # and the small hours in Tokyo

    # Same instant, same hours string, opposite answers.
    assert feas.hours_status("Mo-Su 11:00-23:00", nyc) is Status.SATISFIED
    assert feas.hours_status("Mo-Su 11:00-23:00", tokyo) is Status.VIOLATED


def test_missing_hours_flag_rather_than_delete():
    """A stale or absent hours tag should flag a place, not silently remove it
    from the group's options."""
    place = make_places()[4]
    place.hours = None
    person = Participant(id=uuid.uuid4(), token="t", display_name="Ana", lat=place.lat, lon=place.lon, hard_constraints={"diets": [], "open_now": True})

    verdict = feas.evaluate(place, [person], NOW)
    assert verdict.tier == feas.TIER_UNVERIFIED
    assert verdict.reasons[0].constraint == "open_now" and verdict.reasons[0].kind == "unknown"


def test_closed_now_eliminates():
    place = make_places()[4]
    place.hours = "Mo-Su 08:00-10:00"
    person = Participant(id=uuid.uuid4(), token="t", display_name="Ana", lat=place.lat, lon=place.lon, hard_constraints={"diets": [], "open_now": True})
    assert feas.evaluate(place, [person], NOW).tier == feas.TIER_ELIMINATED


# --------------------------------------------------------------------------
# allergens: the data cannot answer, and the product says so
# --------------------------------------------------------------------------


def test_allergen_constraints_become_a_named_advisory():
    people = make_participants()
    people[1].hard_constraints = {"diets": ["nut_allergy"], "max_distance_m": 20000}

    notes = feas.advisories(people)
    assert len(notes) == 1
    assert notes[0]["participant"] == "Ana"
    assert notes[0]["constraint"] == "nut_allergy"
    # Never "safe": it names the gap, the person, and what to do about it.
    assert "no allergen data" in notes[0]["detail"]
    assert "confirm with the restaurant" in notes[0]["detail"]


def test_an_allergy_does_not_silently_pass_as_satisfied():
    """It must not read as a met constraint anywhere in the verdict."""
    place = make_places()[5]
    person = Participant(id=uuid.uuid4(), token="t", display_name="Ana", lat=place.lat, lon=place.lon, hard_constraints={"diets": ["nut_allergy"]})
    verdict = feas.evaluate(place, [person], NOW)

    assert not any(r.constraint == "nut_allergy" for r in verdict.reasons)
    assert feas.advisories([person])[0]["constraint"] == "nut_allergy"


# --------------------------------------------------------------------------
# relaxation
# --------------------------------------------------------------------------


def test_relaxation_widens_distance():
    people = make_participants()
    relaxed = feas.relax(people, distance_multiplier=2.0)
    assert relaxed[0].hard_constraints["max_distance_m"] == 40000


def test_relaxation_drops_price():
    people = make_participants()
    people[0].hard_constraints = {"diets": [], "max_price_tier": 2}
    assert "max_price_tier" not in feas.relax(people, drop_price=True)[0].hard_constraints


def test_relaxation_never_touches_dietary_constraints():
    """The one invariant with real-world consequences. Distance and price
    bend; what someone can eat does not."""
    people = make_participants()
    for relaxed, original in zip(feas.relax(people, distance_multiplier=4.0, drop_price=True), people):
        assert relaxed.hard_constraints["diets"] == original.hard_constraints["diets"]

    places = make_places()
    verdicts = feas.filter_places(places, feas.relax(people, distance_multiplier=10.0, drop_price=True), NOW)
    by_name = {v.place.name: v for v in verdicts}
    # Sam's and Dev's cuts must survive any amount of relaxation.
    assert by_name["Ramen House"].tier == feas.TIER_ELIMINATED
    assert by_name["Taqueria Sol"].tier == feas.TIER_ELIMINATED
    assert by_name["Thai Garden"].tier == feas.TIER_UNVERIFIED


def test_relaxation_does_not_mutate_the_stored_participants():
    people = make_participants()
    feas.relax(people, distance_multiplier=3.0, drop_price=True)
    assert people[0].hard_constraints["max_distance_m"] == 20000


# --------------------------------------------------------------------------
# empty feasible set
# --------------------------------------------------------------------------


def test_impossible_group_names_whose_constraints_are_binding():
    """"No results" is useless. "No options work for both Sam and Dev" is
    something a group can act on."""
    places = make_places()
    sam = Participant(id=uuid.uuid4(), token="a", display_name="Sam", lat=places[0].lat, lon=places[0].lon, hard_constraints={"diets": ["gluten_free"]})
    dev = Participant(id=uuid.uuid4(), token="b", display_name="Dev", lat=places[0].lat, lon=places[0].lon, hard_constraints={"diets": ["halal"]})

    # Only the two places that each cut one of them.
    verdicts = feas.filter_places([places[0], places[1]], [sam, dev], NOW)
    assert all(v.tier == feas.TIER_ELIMINATED for v in verdicts)

    binding = feas.binding_constraints(verdicts)
    assert {b["participant"] for b in binding} == {"Sam", "Dev"}


def test_a_group_with_no_constraints_eliminates_nothing():
    people = [Participant(id=uuid.uuid4(), token="t", display_name="Ana", lat=40.7128, lon=-74.0060, hard_constraints={})]
    verdicts = feas.filter_places(make_places(), people, NOW)
    assert all(v.tier == feas.TIER_FEASIBLE for v in verdicts)
    assert feas.binding_constraints(verdicts) == []


def test_a_place_with_no_diet_data_at_all_is_unverified_not_feasible():
    blank = Place(osm_id="node/x", name="Mystery Diner", lat=40.7128, lon=-74.0060, geohash5="dr5re", cuisine=[], diet_flags={})
    person = Participant(id=uuid.uuid4(), token="t", display_name="Sam", lat=40.7128, lon=-74.0060, hard_constraints={"diets": ["gluten_free"]})
    assert feas.evaluate(blank, [person], NOW).tier == feas.TIER_UNVERIFIED
