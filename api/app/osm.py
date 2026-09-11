"""Overpass client and OSM tag mapping.

Overpass is free and unlimited but slow and rate-limited, so it is never on
the request path when the covering geohash tiles are fresh. Places land in a
global cache shared across every session.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.constraints import FILTERABLE_DIETS
from app.geo import bbox, covering_tiles, geohash_encode, haversine_m
from app.models import Place, TileCache

log = logging.getLogger(__name__)

AMENITIES = ("restaurant", "fast_food", "cafe")

# Overpass returns 406 to clients sending a generic library User-Agent, and
# its usage policy asks for an identifiable one regardless.
USER_AGENT = "Hangry/0.4 (group dining decider; https://github.com/hangry)"

_QUERY = """
[out:json][timeout:{timeout}];
(
  node["amenity"~"^({amenities})$"]({s},{w},{n},{e});
  way["amenity"~"^({amenities})$"]({s},{w},{n},{e});
);
out center tags;
"""


@dataclass
class ParsedPlace:
    osm_id: str
    name: str
    lat: float
    lon: float
    geohash5: str
    cuisine: list[str]
    price_tier: int | None
    diet_flags: dict[str, str | None]
    hours: str | None


def parse_element(element: dict) -> ParsedPlace | None:
    """Map one Overpass element onto a Place row.

    Returns None for anything unusable, unnamed venues and ways without a
    resolved centre. A nameless pin is not something you can put in a group
    chat and ask six people to vote on.
    """
    tags = element.get("tags") or {}
    name = (tags.get("name") or "").strip()
    if not name:
        return None

    if element.get("type") == "node":
        lat, lon = element.get("lat"), element.get("lon")
    else:
        center = element.get("center") or {}
        lat, lon = center.get("lat"), center.get("lon")
    if lat is None or lon is None:
        return None

    return ParsedPlace(
        osm_id=f"{element['type']}/{element['id']}",
        name=name,
        lat=float(lat),
        lon=float(lon),
        geohash5=geohash_encode(float(lat), float(lon), 5),
        cuisine=parse_cuisine(tags.get("cuisine")),
        # OSM carries no price data. Left null rather than faked; the price
        # filter is hidden in v1 for exactly this reason.
        price_tier=None,
        diet_flags=parse_diet_flags(tags),
        hours=tags.get("opening_hours"),
    )


def parse_cuisine(raw: str | None) -> list[str]:
    """`cuisine` is semicolon-delimited: "pizza;italian;pasta"."""
    if not raw:
        return []
    return [part.strip().lower() for part in raw.split(";") if part.strip()]


def parse_diet_flags(tags: dict[str, str]) -> dict[str, str | None]:
    """Pull `diet:*` tags into our constraint vocabulary.

    Absent tags are stored as explicit `None`, not omitted and not defaulted.
    The null has to survive all the way to the feasibility filter, because
    "we don't know" is a different answer from "no" and from "yes".
    """
    flags: dict[str, str | None] = {}
    for key, osm_tag in FILTERABLE_DIETS.items():
        raw = tags.get(osm_tag)
        flags[key] = raw.strip().lower() if isinstance(raw, str) and raw.strip() else None
    return flags


def build_query(south: float, west: float, north: float, east: float) -> str:
    return _QUERY.format(
        timeout=int(settings.overpass_timeout_s),
        amenities="|".join(AMENITIES),
        s=south,
        w=west,
        n=north,
        e=east,
    )


class OverpassUnavailable(RuntimeError):
    """Overpass did not answer in time, or answered with an error."""


async def fetch_area(
    client: httpx.AsyncClient, south: float, west: float, north: float, east: float
) -> list[ParsedPlace]:
    """Every eatery in one bounding box, in a single request.

    This used to run per geohash tile, which meant a 5km search made 25
    sequential requests and a 10km search made 42. Each was allowed 30
    seconds, so a first search in a new city could sit there for minutes
    while Overpass rate-limited the burst. The whole area is one query now.
    """
    try:
        response = await client.post(
            settings.overpass_url,
            # Form-encoded `data=`, not a raw body. Overpass rejects the latter.
            data={"data": build_query(south, west, north, east)},
            headers={"User-Agent": USER_AGENT},
            timeout=settings.overpass_timeout_s,
        )
        response.raise_for_status()
        elements = response.json().get("elements", [])
    except httpx.TimeoutException as exc:
        raise OverpassUnavailable("the map service took too long") from exc
    except httpx.HTTPStatusError as exc:
        # 429 and 504 are Overpass under load, which is common and temporary.
        raise OverpassUnavailable(f"the map service returned {exc.response.status_code}") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise OverpassUnavailable("the map service could not be reached") from exc

    parsed = [p for p in (parse_element(e) for e in elements) if p is not None]
    log.info("overpass area fetch: %d elements -> %d usable places", len(elements), len(parsed))
    return parsed


async def _fresh_tiles(db: AsyncSession, tiles: list[str]) -> set[str]:
    cutoff = datetime.now(UTC) - timedelta(days=settings.tile_ttl_days)
    rows = await db.execute(
        select(TileCache.geohash5).where(TileCache.geohash5.in_(tiles), TileCache.fetched_at >= cutoff)
    )
    return set(rows.scalars().all())


# Postgres allows 32767 bind parameters in one statement. Each place binds 11
# columns, so batches stay well under that. Fetching per tile kept batches
# small by accident; fetching a whole city at once does not.
UPSERT_BATCH = 1000


async def _upsert_places(db: AsyncSession, places: list[ParsedPlace]) -> None:
    for start in range(0, len(places), UPSERT_BATCH):
        await _upsert_batch(db, places[start : start + UPSERT_BATCH])


async def _upsert_batch(db: AsyncSession, places: list[ParsedPlace]) -> None:
    if not places:
        return
    # Places are shared global cache rows; a re-fetch should refresh them
    # rather than collide with a row another session already inserted.
    stmt = pg_insert(Place).values(
        [
            {
                "osm_id": p.osm_id,
                "name": p.name,
                "lat": p.lat,
                "lon": p.lon,
                "geohash5": p.geohash5,
                "cuisine": p.cuisine,
                "price_tier": p.price_tier,
                "diet_flags": p.diet_flags,
                "hours": p.hours,
                "source": "osm",
                "fetched_at": datetime.now(UTC),
            }
            for p in places
        ]
    )
    await db.execute(
        stmt.on_conflict_do_update(
            index_elements=[Place.osm_id],
            set_={
                "name": stmt.excluded.name,
                "lat": stmt.excluded.lat,
                "lon": stmt.excluded.lon,
                "geohash5": stmt.excluded.geohash5,
                "cuisine": stmt.excluded.cuisine,
                "diet_flags": stmt.excluded.diet_flags,
                "hours": stmt.excluded.hours,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
    )


async def ensure_area_cached(db: AsyncSession, lat: float, lon: float, radius_m: int) -> list[str]:
    """Make sure the search area has been fetched, in one request if not.

    Tiles remain the unit of bookkeeping, because they are what makes the
    cache reusable across groups searching overlapping areas. They are no
    longer the unit of fetching. If any tile covering the area is stale, one
    query covers the whole box and every tile in it is marked fresh.
    """
    tiles = covering_tiles(lat, lon, radius_m, precision=5)
    fresh = await _fresh_tiles(db, tiles)
    stale = [t for t in tiles if t not in fresh]

    if not stale:
        log.info("all %d tiles warm, skipping overpass", len(tiles))
        return tiles

    log.info("%d of %d tiles stale, fetching the area in one request", len(stale), len(tiles))
    south, west, north, east = bbox(lat, lon, radius_m)

    async with httpx.AsyncClient() as client:
        places = await fetch_area(client, south, west, north, east)

    await _upsert_places(db, places)

    # Only now are the tiles fresh. A failed fetch raises above and leaves
    # them stale, so the next attempt tries again rather than trusting an
    # empty area for 30 days.
    now = datetime.now(UTC)
    for tile in tiles:
        await db.execute(
            pg_insert(TileCache)
            .values(geohash5=tile, fetched_at=now)
            .on_conflict_do_update(index_elements=[TileCache.geohash5], set_={"fetched_at": now})
        )
    await db.commit()

    return tiles


async def places_near(db: AsyncSession, lat: float, lon: float, radius_m: int) -> list[Place]:
    """Cached places within the radius, nearest first.

    Tiles are square and the search area is a circle, so the tile query is a
    coarse prefilter and the haversine cut is what actually enforces radius.
    """
    tiles = covering_tiles(lat, lon, radius_m, precision=5)
    rows = await db.execute(select(Place).where(Place.geohash5.in_(tiles)))
    candidates = rows.scalars().all()

    within = [(p, haversine_m(lat, lon, p.lat, p.lon)) for p in candidates]
    within = [(p, d) for p, d in within if d <= radius_m]
    within.sort(key=lambda pair: pair[1])
    return [p for p, _ in within]
