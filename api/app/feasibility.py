"""Stage 1 — the feasibility filter.

Hard constraints eliminate. They never down-weight. A candidate violating
*any* participant's hard constraint is gone, however many other people would
have loved it.

Three tiers come out:

    feasible     every hard constraint answered, none violated
    unverified   nothing violated, but the data cannot answer someone's
                 constraint — shown, visibly flagged, kept out of the ranking
    eliminated   at least one hard constraint provably violated

The unverified tier is the product, not defensive engineering. Someone who
manages a food restriction abandons a tool permanently the first time it
guesses on their behalf, so "we don't know" has to be a visible answer rather
than rounding to yes.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta

from opening_hours import OpeningHours, ParserError

from app.constraints import ADVISORY_DIETS, FILTERABLE_DIETS, HUMAN_LABELS, Status, diet_status
from app.geo import haversine_m
from app.models import Participant, Place

log = logging.getLogger(__name__)

TIER_FEASIBLE = "feasible"
TIER_UNVERIFIED = "unverified"
TIER_ELIMINATED = "eliminated"


@dataclass
class Reason:
    """Why a candidate was cut or flagged.

    Always names a participant and a constraint. Never a bare boolean — the
    UI has to be able to say "three places were cut because Sam can't eat
    there", and that sentence needs both halves.
    """

    participant: str
    participant_id: str
    constraint: str
    kind: str  # "eliminated" | "unknown"
    detail: str


@dataclass
class Verdict:
    place: Place
    tier: str
    reasons: list[Reason] = field(default_factory=list)
    distance_m: float = 0.0

    def as_json(self) -> list[dict]:
        return [asdict(r) for r in self.reasons]


def local_time(now: datetime, lon: float) -> datetime:
    """Approximate wall-clock time at a longitude, as a naive datetime.

    `opening_hours` strings are local time, so comparing them against UTC
    would call a restaurant closed in London and open in Los Angeles at the
    same instant. Resolving a true timezone needs a coordinates-to-timezone
    database; the 15-degrees-per-hour approximation is within an hour almost
    everywhere and needs no dependency.

    It is wrong near timezone boundaries and ignores DST, which is why
    `open_now` is opt-in and an unparseable or borderline result flags rather
    than eliminates wherever it can.
    """
    if now.tzinfo is not None:
        now = now.astimezone(UTC).replace(tzinfo=None)
    return now + timedelta(hours=lon / 15.0)


def hours_status(hours: str | None, now: datetime) -> Status:
    """Is this place open at `now` (naive local time)?

    `opening_hours` is its own grammar with real edge cases, so it is parsed
    by the dedicated package. Absent or unparseable hours are UNKNOWN — never
    assumed open, and never assumed closed either, since a stale tag should
    flag a place rather than silently delete it from the group's options.
    """
    if not hours:
        return Status.UNKNOWN

    # The parser only accepts naive or zoneinfo-keyed datetimes.
    if now.tzinfo is not None:
        now = now.astimezone(UTC).replace(tzinfo=None)

    try:
        parsed = OpeningHours(hours)
        if parsed.is_unknown(now):
            return Status.UNKNOWN
        return Status.SATISFIED if parsed.is_open(now) else Status.VIOLATED
    except (ParserError, ValueError, TypeError) as exc:
        log.debug("unparseable opening_hours %r: %s", hours, exc)
        return Status.UNKNOWN


def _diets_of(participant: Participant) -> list[str]:
    return list((participant.hard_constraints or {}).get("diets") or [])


def evaluate(place: Place, participants: list[Participant], now: datetime) -> Verdict:
    """Run every participant's hard constraints against one place."""
    reasons: list[Reason] = []
    constraints = {p.id: (p.hard_constraints or {}) for p in participants}

    # Distance is measured from each participant's own location, so the
    # verdict's own distance is reported from the group centroid's nearest
    # participant view — see `worst_distance` below.
    distances = {p.id: haversine_m(p.lat, p.lon, place.lat, place.lon) for p in participants}

    for participant in participants:
        name = participant.display_name
        pid = str(participant.id)
        hard = constraints[participant.id]

        for diet in _diets_of(participant):
            if diet in ADVISORY_DIETS:
                # No OSM schema exists for allergens. Surfaced as a standing
                # advisory on every candidate instead of tiering everything
                # into unverified — see constraints.ADVISORY_DIETS.
                continue
            if diet not in FILTERABLE_DIETS:
                continue

            status = diet_status(place.diet_flags or {}, diet)
            label = HUMAN_LABELS.get(diet, diet)
            if status is Status.VIOLATED:
                reasons.append(
                    Reason(name, pid, diet, "eliminated", f"listed as not {label}, and {name} needs {label}")
                )
            elif status is Status.UNKNOWN:
                reasons.append(
                    Reason(name, pid, diet, "unknown", f"no {label} information in the data, and {name} needs {label}")
                )

        max_distance = hard.get("max_distance_m")
        if max_distance and distances[participant.id] > max_distance:
            km = distances[participant.id] / 1000
            reasons.append(
                Reason(
                    name,
                    pid,
                    "max_distance_m",
                    "eliminated",
                    f"{km:.1f} km from {name}, past their {max_distance / 1000:.0f} km limit",
                )
            )

        # Price stays wired up but unused in v1: OSM has no price data, so the
        # filter is hidden in the UI rather than run against nulls.
        max_price = hard.get("max_price_tier")
        if max_price:
            if place.price_tier is None:
                reasons.append(Reason(name, pid, "max_price_tier", "unknown", f"no price data, and {name} capped at {'$' * max_price}"))
            elif place.price_tier > max_price:
                reasons.append(
                    Reason(name, pid, "max_price_tier", "eliminated", f"{'$' * place.price_tier} is over {name}'s {'$' * max_price} limit")
                )

        if hard.get("open_now"):
            status = hours_status(place.hours, local_time(now, place.lon))
            if status is Status.VIOLATED:
                reasons.append(Reason(name, pid, "open_now", "eliminated", "closed right now"))
            elif status is Status.UNKNOWN:
                reasons.append(Reason(name, pid, "open_now", "unknown", "no opening hours in the data"))

    if any(r.kind == "eliminated" for r in reasons):
        tier = TIER_ELIMINATED
    elif reasons:
        tier = TIER_UNVERIFIED
    else:
        tier = TIER_FEASIBLE

    # The binding number for a group is the furthest anyone has to travel.
    return Verdict(place=place, tier=tier, reasons=reasons, distance_m=max(distances.values()) if distances else 0.0)


def filter_places(places: list[Place], participants: list[Participant], now: datetime) -> list[Verdict]:
    return [evaluate(place, participants, now) for place in places]


@dataclass
class Actor:
    """A participant with relaxed constraints, for re-running the filter.

    Duck-types `Participant` so `evaluate` needs no branch for it, and keeps
    relaxation from mutating rows that are about to be committed.
    """

    id: object
    display_name: str
    lat: float
    lon: float
    hard_constraints: dict


def relax(participants: list[Participant], *, distance_multiplier: float = 1.0, drop_price: bool = False) -> list[Actor]:
    """Loosen constraints in the one order the product is allowed to loosen them.

    Distance first, then price. **Dietary constraints are never touched** —
    not here, not anywhere. `diets` is copied through verbatim on purpose:
    relaxing it would silently put someone in front of food they can't eat,
    which is the single failure this product cannot have.
    """
    actors = []
    for participant in participants:
        hard = dict(participant.hard_constraints or {})

        if distance_multiplier != 1.0 and hard.get("max_distance_m"):
            hard["max_distance_m"] = int(hard["max_distance_m"] * distance_multiplier)
        if drop_price:
            hard.pop("max_price_tier", None)

        actors.append(
            Actor(
                id=participant.id,
                display_name=participant.display_name,
                lat=participant.lat,
                lon=participant.lon,
                hard_constraints=hard,
            )
        )
    return actors


def advisories(participants: list[Participant]) -> list[dict]:
    """Constraints the data physically cannot answer.

    Shown on every candidate and on the result. This is the honest form of
    "we don't know": it names the person and tells the group to ask, which is
    the opposite of quietly passing the candidate as safe.
    """
    out = []
    for participant in participants:
        for diet in _diets_of(participant):
            if diet in ADVISORY_DIETS:
                out.append(
                    {
                        "participant": participant.display_name,
                        "participant_id": str(participant.id),
                        "constraint": diet,
                        "detail": (
                            f"OpenStreetMap has no allergen data, so {ADVISORY_DIETS[diet]} "
                            f"could not be checked for any of these places. "
                            f"{participant.display_name} should confirm with the restaurant."
                        ),
                    }
                )
    return out


def binding_constraints(verdicts: list[Verdict]) -> list[dict]:
    """Who is doing the eliminating, for the empty-feasible-set message.

    Produces the material for "No options work for both Sam and Dev within
    20 minutes" rather than a bare "no results".
    """
    tally: dict[tuple[str, str], int] = {}
    for verdict in verdicts:
        for reason in verdict.reasons:
            if reason.kind == "eliminated":
                key = (reason.participant, reason.constraint)
                tally[key] = tally.get(key, 0) + 1

    return [
        {"participant": participant, "constraint": constraint, "label": HUMAN_LABELS.get(constraint, constraint), "eliminated": count}
        for (participant, constraint), count in sorted(tally.items(), key=lambda kv: -kv[1])
    ]
