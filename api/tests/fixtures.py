"""The seven-restaurant, six-person scenario from `hangry-algorithm.md`.

Shared by the feasibility tests and the end-to-end test so both are arguing
about the same dinner.
"""

from __future__ import annotations

import uuid

from datetime import UTC, datetime

from app.geo import covering_tiles, geohash_encode
from app.models import Participant, Place, TileCache

CENTER_LAT, CENTER_LON = 40.7128, -74.0060

# (name, dlat, dlon, gluten_free, vegetarian, halal)
# None means the tag is absent from OSM, which is not "no".
RESTAURANTS = [
    ("Ramen House", 0.001, 0.001, "no", "yes", "yes"),
    ("Taqueria Sol", 0.002, -0.001, "yes", "yes", "no"),
    ("Burger Joint", -0.001, 0.002, "no", "yes", "yes"),
    ("Thai Garden", 0.003, 0.001, "yes", "yes", None),
    ("Mediterranean Grill", 0.001, -0.002, "yes", "yes", "yes"),
    ("Indian Kitchen", -0.002, -0.001, "yes", "yes", "yes"),
    ("Sushi Bar", 0.002, 0.002, "yes", "yes", "yes"),
]

CUISINES = {
    "Ramen House": ["ramen", "japanese"],
    "Taqueria Sol": ["mexican"],
    "Burger Joint": ["burger", "american"],
    "Thai Garden": ["thai"],
    "Mediterranean Grill": ["mediterranean", "greek"],
    "Indian Kitchen": ["indian"],
    "Sushi Bar": ["sushi", "japanese"],
}

# (name, diets), matches the hard-constraint table in the doc.
PEOPLE = [
    ("Maazin", []),
    ("Ana", []),
    ("Sam", ["gluten_free"]),
    ("Priya", ["vegetarian"]),
    ("Jordan", []),
    ("Dev", ["halal"]),
]

# Jordan does not eat sushi. Not an allergy, he just hates it, so it is a
# soft preference expressed in the ranking and eliminates nothing.
RANKINGS = {
    "Maazin": ["Sushi Bar", "Indian Kitchen", "Mediterranean Grill"],
    "Ana": ["Sushi Bar", "Indian Kitchen", "Mediterranean Grill"],
    "Sam": ["Sushi Bar", "Indian Kitchen", "Mediterranean Grill"],
    "Priya": ["Indian Kitchen", "Sushi Bar", "Mediterranean Grill"],
    "Jordan": ["Mediterranean Grill", "Indian Kitchen", "Sushi Bar"],
    "Dev": ["Sushi Bar", "Indian Kitchen", "Mediterranean Grill"],
}


def make_places() -> list[Place]:
    places = []
    for index, (name, dlat, dlon, gf, veg, halal) in enumerate(RESTAURANTS):
        lat, lon = CENTER_LAT + dlat, CENTER_LON + dlon
        places.append(
            Place(
                osm_id=f"node/{1000 + index}",
                name=name,
                lat=lat,
                lon=lon,
                geohash5=geohash_encode(lat, lon, 5),
                cuisine=CUISINES[name],
                price_tier=None,
                diet_flags={
                    "gluten_free": gf,
                    "vegetarian": veg,
                    "halal": halal,
                    "vegan": None,
                    "kosher": None,
                },
                hours=None,
                source="osm",
            )
        )
    return places


async def seed_world(db, only: list[str] | None = None) -> None:
    """Put the restaurants in the cache and mark the tiles warm.

    Warm tiles are what keep the API tests off the network, Overpass is
    never on the request path, so the tests shouldn't be either. `only`
    narrows the world by name, for scenarios that need a specific shape.
    """
    for place in make_places():
        if only is not None and place.name not in only:
            continue
        db.add(place)
    for tile in covering_tiles(CENTER_LAT, CENTER_LON, 25_000, 5):
        db.add(TileCache(geohash5=tile, fetched_at=datetime.now(UTC)))
    await db.commit()


def make_participants(session_id: uuid.UUID | None = None) -> list[Participant]:
    people = []
    for index, (name, diets) in enumerate(PEOPLE):
        people.append(
            Participant(
                id=uuid.uuid4(),
                session_id=session_id,
                token=f"token-{name.lower()}",
                display_name=name,
                # Everyone starts within a few hundred metres of the centre so
                # distance never binds and the dietary logic is what's tested.
                lat=CENTER_LAT + index * 0.0002,
                lon=CENTER_LON - index * 0.0002,
                hard_constraints={"diets": diets, "max_distance_m": 20000, "open_now": False},
                is_creator=index == 0,
            )
        )
    return people
