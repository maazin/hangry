"""Geohash tiling and haversine distance.

Both are ~20 lines, so they're written out rather than pulled in as
dependencies. Real travel-time isochrones (OpenRouteService + PostGIS) are
Phase 6; haversine is the stated v1 proxy.
"""

from __future__ import annotations

import math

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

EARTH_RADIUS_M = 6_371_000.0


def geohash_encode(lat: float, lon: float, precision: int = 5) -> str:
    """Standard geohash. Precision 5 is roughly a 5km x 5km cell."""
    lat_range, lon_range = [-90.0, 90.0], [-180.0, 180.0]
    out: list[str] = []
    bit = 0
    ch = 0
    even = True  # geohash alternates lon, lat starting with lon

    while len(out) < precision:
        if even:
            mid = (lon_range[0] + lon_range[1]) / 2
            if lon > mid:
                ch = (ch << 1) | 1
                lon_range[0] = mid
            else:
                ch <<= 1
                lon_range[1] = mid
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat > mid:
                ch = (ch << 1) | 1
                lat_range[0] = mid
            else:
                ch <<= 1
                lat_range[1] = mid

        even = not even
        bit += 1
        if bit == 5:
            out.append(_BASE32[ch])
            bit = 0
            ch = 0

    return "".join(out)


def geohash_bounds(gh: str) -> tuple[float, float, float, float]:
    """Decode a geohash to (south, west, north, east)."""
    lat_range, lon_range = [-90.0, 90.0], [-180.0, 180.0]
    even = True
    for char in gh:
        idx = _BASE32.index(char)
        for mask in (16, 8, 4, 2, 1):
            target = lon_range if even else lat_range
            mid = (target[0] + target[1]) / 2
            if idx & mask:
                target[0] = mid
            else:
                target[1] = mid
            even = not even
    return lat_range[0], lon_range[0], lat_range[1], lon_range[1]


def bbox(lat: float, lon: float, radius_m: int) -> tuple[float, float, float, float]:
    """The (south, west, north, east) box that contains the search circle."""
    d_lat = radius_m / 111_320.0
    # Longitude degrees shrink as you move away from the equator.
    d_lon = radius_m / (111_320.0 * max(math.cos(math.radians(lat)), 0.01))
    return lat - d_lat, lon - d_lon, lat + d_lat, lon + d_lon


def covering_tiles(lat: float, lon: float, radius_m: int, precision: int = 5) -> list[str]:
    """Every geohash tile the search circle touches.

    A circle near a cell edge spills into its neighbours, so the whole box is
    walked rather than just the centre.

    The step is half a precision-5 cell, which is small enough that no cell
    between the corners is skipped and large enough that the walk stays
    cheap. An earlier version stepped a fixed 0.04 degrees out to twice the
    box width, which reported 25 tiles for a 5km radius that touches nine.
    """
    south, west, north, east = bbox(lat, lon, radius_m)

    # A precision-5 cell is roughly 0.044 by 0.044 degrees.
    step = 0.02
    tiles: set[str] = set()

    y = south
    while True:
        x = west
        while True:
            tiles.add(geohash_encode(y, x, precision))
            if x >= east:
                break
            x = min(x + step, east)
        if y >= north:
            break
        y = min(y + step, north)

    return sorted(tiles)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_phi = p2 - p1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Mean of lat/lon pairs.

    Naive, and frequently wrong, the midpoint of six addresses is often a
    highway interchange. Good enough as a search origin in v1; Phase 6
    replaces it with intersected isochrones.
    """
    if not points:
        raise ValueError("no points")
    return (
        sum(p[0] for p in points) / len(points),
        sum(p[1] for p in points) / len(points),
    )
