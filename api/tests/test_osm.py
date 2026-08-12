"""Phase 2 — OSM tag mapping, the null-vs-no distinction, and tile caching."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app import osm
from app.constraints import Status, diet_status
from app.geo import covering_tiles, geohash_encode, haversine_m
from app.models import Place, TileCache


# --------------------------------------------------------------------------
# tag mapping, table-driven
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tags,expected",
    [
        ({"diet:vegetarian": "yes"}, "yes"),
        ({"diet:vegetarian": "only"}, "only"),
        ({"diet:vegetarian": "no"}, "no"),
        ({"diet:vegetarian": "limited"}, "limited"),
        ({"diet:vegetarian": "  YES  "}, "yes"),
        ({"diet:vegetarian": ""}, None),
        ({}, None),
        ({"diet:vegan": "yes"}, None),  # a different key must not fill this one in
    ],
)
def test_diet_tag_mapping(tags, expected):
    assert osm.parse_diet_flags(tags)["vegetarian"] == expected


def test_absent_tags_are_stored_as_explicit_null():
    """The null has to survive to the filter. An omitted key would let a
    `.get(..., "yes")` somewhere downstream quietly invent an answer."""
    flags = osm.parse_diet_flags({})
    assert set(flags) == {"vegetarian", "vegan", "gluten_free", "halal", "kosher"}
    assert all(value is None for value in flags.values())


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("pizza;italian;pasta", ["pizza", "italian", "pasta"]),
        ("Sushi", ["sushi"]),
        ("indian; curry ", ["indian", "curry"]),
        ("", []),
        (None, []),
    ],
)
def test_cuisine_is_semicolon_delimited(raw, expected):
    assert osm.parse_cuisine(raw) == expected


# --------------------------------------------------------------------------
# null vs no — the invariant
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("yes", Status.SATISFIED),
        ("only", Status.SATISFIED),
        ("no", Status.VIOLATED),
        # "limited options" is not a confident yes, and this is exactly where
        # guessing hurts someone.
        ("limited", Status.UNKNOWN),
        (None, Status.UNKNOWN),
    ],
)
def test_missing_is_never_satisfied(value, expected):
    assert diet_status({"gluten_free": value}, "gluten_free") is expected


def test_unknown_and_violated_are_distinct():
    assert diet_status({"halal": None}, "halal") is not diet_status({"halal": "no"}, "halal")


def test_vegan_kitchen_satisfies_a_vegetarian_but_not_the_reverse():
    assert diet_status({"vegan": "only", "vegetarian": None}, "vegetarian") is Status.SATISFIED
    assert diet_status({"vegetarian": "yes", "vegan": None}, "vegan") is Status.UNKNOWN


def test_a_declared_no_beats_the_vegan_implication():
    assert diet_status({"vegetarian": "no", "vegan": "yes"}, "vegetarian") is Status.VIOLATED


def test_allergen_constraints_are_always_unknown():
    """OSM has no allergen schema at all, so nothing can ever satisfy these."""
    assert diet_status({"nut_allergy": "yes"}, "nut_allergy") is Status.UNKNOWN
    assert diet_status({}, "shellfish_allergy") is Status.UNKNOWN


# --------------------------------------------------------------------------
# element parsing
# --------------------------------------------------------------------------


def test_parses_a_node():
    place = osm.parse_element(
        {
            "type": "node",
            "id": 42,
            "lat": 40.7,
            "lon": -74.0,
            "tags": {"name": "Indian Kitchen", "cuisine": "indian", "diet:halal": "yes", "opening_hours": "Mo-Su 11:00-22:00"},
        }
    )
    assert place.osm_id == "node/42"
    assert place.name == "Indian Kitchen"
    assert place.cuisine == ["indian"]
    assert place.diet_flags["halal"] == "yes"
    assert place.diet_flags["gluten_free"] is None
    assert place.hours == "Mo-Su 11:00-22:00"
    # OSM has no price data; faking a tier would be inventing the filter.
    assert place.price_tier is None


def test_parses_a_way_via_its_center():
    place = osm.parse_element({"type": "way", "id": 7, "center": {"lat": 1.0, "lon": 2.0}, "tags": {"name": "Cafe"}})
    assert place.osm_id == "way/7" and (place.lat, place.lon) == (1.0, 2.0)


@pytest.mark.parametrize(
    "element",
    [
        {"type": "node", "id": 1, "lat": 1.0, "lon": 2.0, "tags": {}},  # unnamed
        {"type": "node", "id": 2, "lat": 1.0, "lon": 2.0, "tags": {"name": "   "}},  # blank name
        {"type": "way", "id": 3, "tags": {"name": "No centre"}},  # no resolved centre
    ],
)
def test_unusable_elements_are_dropped(element):
    """A nameless pin is not something six people can vote on."""
    assert osm.parse_element(element) is None


def test_query_targets_the_three_amenity_types():
    query = osm.build_query(1.0, 2.0, 3.0, 4.0)
    assert "restaurant|fast_food|cafe" in query
    assert "out center tags" in query


# --------------------------------------------------------------------------
# geo helpers
# --------------------------------------------------------------------------


def test_geohash_precision_and_stability():
    assert len(geohash_encode(40.7128, -74.0060, 5)) == 5
    assert geohash_encode(40.7128, -74.0060, 5) == geohash_encode(40.7128, -74.0060, 5)
    assert geohash_encode(40.7128, -74.0060, 5) != geohash_encode(51.5074, -0.1278, 5)


def test_covering_tiles_include_the_centre_and_spill_into_neighbours():
    tiles = covering_tiles(40.7128, -74.0060, 5000, 5)
    assert geohash_encode(40.7128, -74.0060, 5) in tiles
    # A 5km radius near a cell edge spills over; one tile would silently miss
    # half the candidates.
    assert len(tiles) > 1


def test_haversine_against_a_known_distance():
    # NYC -> London, ~5,570 km.
    metres = haversine_m(40.7128, -74.0060, 51.5074, -0.1278)
    assert 5_560_000 < metres < 5_590_000
    assert haversine_m(1.0, 2.0, 1.0, 2.0) == 0.0


# --------------------------------------------------------------------------
# tile cache hit and miss
# --------------------------------------------------------------------------


async def test_cache_miss_fetches_and_stores(db, monkeypatch):
    calls = []

    async def fake_fetch(client, tile):
        calls.append(tile)
        return [
            osm.ParsedPlace(
                osm_id=f"node/{tile}",
                name=f"Place {tile}",
                lat=40.7128,
                lon=-74.0060,
                geohash5=tile,
                cuisine=["thai"],
                price_tier=None,
                diet_flags={"halal": None},
                hours=None,
            )
        ]

    monkeypatch.setattr(osm, "fetch_tile", fake_fetch)
    await osm.ensure_tiles_cached(db, 40.7128, -74.0060, 2000)

    assert calls, "a cold tile must hit Overpass"
    cached = (await db.execute(select(TileCache.geohash5))).scalars().all()
    assert set(cached) == set(calls)
    assert (await db.execute(select(Place))).scalars().all()


async def test_warm_tiles_never_touch_the_network(db, monkeypatch):
    """Overpass is slow and rate-limited, so it must never be on the request
    path when the tiles are fresh."""
    tiles = covering_tiles(40.7128, -74.0060, 2000, 5)
    for tile in tiles:
        db.add(TileCache(geohash5=tile, fetched_at=datetime.now(UTC)))
    await db.commit()

    async def explode(client, tile):
        raise AssertionError(f"hit Overpass for a warm tile: {tile}")

    monkeypatch.setattr(osm, "fetch_tile", explode)
    assert await osm.ensure_tiles_cached(db, 40.7128, -74.0060, 2000) == tiles


async def test_stale_tiles_are_refetched(db, monkeypatch):
    tiles = covering_tiles(40.7128, -74.0060, 2000, 5)
    for tile in tiles:
        db.add(TileCache(geohash5=tile, fetched_at=datetime.now(UTC) - timedelta(days=31)))
    await db.commit()

    calls = []

    async def fake_fetch(client, tile):
        calls.append(tile)
        return []

    monkeypatch.setattr(osm, "fetch_tile", fake_fetch)
    await osm.ensure_tiles_cached(db, 40.7128, -74.0060, 2000)
    assert set(calls) == set(tiles), "a tile past its 30-day TTL must be refetched"


async def test_a_failing_tile_degrades_instead_of_failing_the_solve(db, monkeypatch):
    import httpx

    async def boom(client, tile):
        raise httpx.ConnectError("overpass down")

    monkeypatch.setattr(osm, "fetch_tile", boom)
    await osm.ensure_tiles_cached(db, 40.7128, -74.0060, 2000)

    # Nothing cached, nothing raised — and the tile stays unmarked so the next
    # solve retries it rather than trusting an empty result for 30 days.
    assert (await db.execute(select(TileCache))).scalars().all() == []


async def test_places_near_enforces_the_radius_not_just_the_tile(db):
    """Tiles are square, the search area is a circle."""
    near = Place(osm_id="node/near", name="Near", lat=40.7128, lon=-74.0060, geohash5=geohash_encode(40.7128, -74.0060, 5), cuisine=[], diet_flags={})
    far_lat = 40.7128 + 0.05  # ~5.5 km north, same tile neighbourhood
    far = Place(osm_id="node/far", name="Far", lat=far_lat, lon=-74.0060, geohash5=geohash_encode(far_lat, -74.0060, 5), cuisine=[], diet_flags={})
    db.add_all([near, far])
    await db.commit()

    found = await osm.places_near(db, 40.7128, -74.0060, 1000)
    assert [p.name for p in found] == ["Near"]
