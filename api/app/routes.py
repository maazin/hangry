"""Every endpoint. One file, because six endpoints across three files is
harder to follow than six endpoints in one."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app import feasibility as feas
from app import osm
from app.aggregation import annotate, borda_scores, comparison, decide
from app.config import settings
from app.deps import CurrentParticipant, CurrentSession, Creator, DbSession
from app.geo import centroid, haversine_m
from app.models import Candidate, Participant, Ranking, Result, Session
from app.schemas import (
    CandidateOut,
    ParticipantJoined,
    ParticipantIn,
    ParticipantOut,
    RankingAccepted,
    RankingIn,
    ResultOut,
    SessionCreate,
    SessionCreated,
    SessionState,
    StartResult,
    You,
)
from app.slug import new_slug, new_token

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


async def _unique_display_name(db: DbSession, session_id: uuid.UUID, wanted: str) -> str:
    """Names are the identity in every result string, so they must be unique
    within a session. Two people called Sam get "Sam" and "Sam (2)" rather
    than one silently absorbing the other's rankings."""
    rows = await db.execute(select(Participant.display_name).where(Participant.session_id == session_id))
    taken = set(rows.scalars().all())

    if wanted not in taken:
        return wanted
    for n in range(2, 100):
        candidate = f"{wanted} ({n})"
        if candidate not in taken:
            return candidate
    return f"{wanted} ({uuid.uuid4().hex[:4]})"


def _candidate_out(candidate: Candidate, participants: list[Participant]) -> CandidateOut:
    distance = max(
        (haversine_m(p.lat, p.lon, candidate.place.lat, candidate.place.lon) for p in participants),
        default=0.0,
    )
    return CandidateOut(
        id=candidate.id,
        place_id=candidate.place_id,
        name=candidate.place.name,
        lat=candidate.place.lat,
        lon=candidate.place.lon,
        cuisine=candidate.place.cuisine or [],
        tier=candidate.tier,
        locked=candidate.locked,
        distance_m=round(distance, 1),
        cut_reasons=candidate.cut_reasons or [],
    )


async def _build_state(db: DbSession, session: Session, viewer_token: str | None = None) -> SessionState:
    participants = sorted(session.participants, key=lambda p: p.joined_at)

    submitted = await db.execute(
        select(func.count(func.distinct(Ranking.participant_id))).where(
            Ranking.participant_id.in_([p.id for p in participants] or [uuid.uuid4()])
        )
    )

    stored = await db.get(Result, session.id)
    result = None
    if stored is not None:
        result = ResultOut(
            ranked=stored.ranked,
            alternates=stored.alternates,
            # Recomputed on read rather than stored twice; it is pure
            # presentation over `ranked` and `alternates`.
            comparison=stored.alternates.get("comparison", {}),
            rule=stored.rule,
            computed_at=stored.computed_at,
        )

    # Eliminated candidates are returned too: the UI needs them to say "three
    # places were cut because Sam can't eat there".
    candidates = sorted(
        session.candidates,
        key=lambda c: (not c.locked, {"feasible": 0, "unverified": 1, "eliminated": 2}.get(c.tier, 3), c.place.name),
    )

    you = None
    viewer = next((p for p in participants if viewer_token and p.token == viewer_token), None)
    if viewer is not None:
        ranked = await db.execute(select(func.count()).select_from(Ranking).where(Ranking.participant_id == viewer.id))
        you = You(
            participant_id=viewer.id,
            display_name=viewer.display_name,
            is_creator=viewer.is_creator,
            has_ranked=(ranked.scalar_one() or 0) > 0,
        )

    return SessionState(
        slug=session.slug,
        status=session.status,
        group_slug=session.group.slug if session.group else None,
        radius_m=session.radius_m,
        center_lat=session.center_lat,
        center_lon=session.center_lon,
        created_at=session.created_at,
        expires_at=session.expires_at,
        participants=[ParticipantOut.model_validate(p) for p in participants],
        candidates=[_candidate_out(c, participants) for c in candidates],
        advisories=feas.advisories(participants),
        submitted=submitted.scalar_one() or 0,
        result=result,
        you=you,
    )


# --------------------------------------------------------------------------
# sessions and joining
# --------------------------------------------------------------------------


@router.post("/sessions", response_model=SessionCreated)
async def create_session(body: SessionCreate, db: DbSession) -> SessionCreated:
    """Create a session and enrol the creator in one round trip.

    One call, because the creator's first tap should produce a shareable
    link rather than an empty session they then have to join.
    """
    session = None
    for _ in range(8):  # 30^6 keyspace; collisions are rare but not impossible
        session = Session(
            slug=new_slug(),
            status="collecting",
            radius_m=body.radius_m,
            center_lat=body.center_lat if body.center_lat is not None else body.creator.lat,
            center_lon=body.center_lon if body.center_lon is not None else body.creator.lon,
            expires_at=datetime.now(UTC) + timedelta(hours=settings.session_ttl_hours),
        )
        db.add(session)
        try:
            await db.flush()
            break
        except IntegrityError:
            await db.rollback()
            session = None

    if session is None:
        raise HTTPException(503, detail={"code": "slug_exhausted", "message": "Could not allocate a link. Try again."})

    token = new_token()
    participant = Participant(
        session_id=session.id,
        token=token,
        display_name=body.creator.name.strip(),
        lat=body.creator.lat,
        lon=body.creator.lon,
        hard_constraints=body.creator.hard_constraints.model_dump(),
        is_creator=True,
    )
    db.add(participant)
    await db.commit()
    await db.refresh(participant)

    return SessionCreated(slug=session.slug, participant_id=participant.id, token=token, status=session.status)


@router.get("/sessions/{slug}", response_model=SessionState)
async def read_session(
    session: CurrentSession,
    db: DbSession,
    x_participant_token: Annotated[str | None, Header()] = None,
) -> SessionState:
    """Full state. The token is optional here, someone who hasn't joined yet
    still needs to see who's waiting before deciding to."""
    return await _build_state(db, session, x_participant_token)


@router.post("/sessions/{slug}/participants", response_model=ParticipantJoined)
async def join_session(body: ParticipantIn, session: CurrentSession, db: DbSession) -> ParticipantJoined:
    """Join before the solve starts.

    Joining after `start` is rejected outright in v1. Handling mid-round
    joins correctly means re-running the feasibility filter and potentially
    invalidating rankings people already submitted, and a half-correct
    version of that is worse than a clear "too late".
    """
    if session.status != "collecting":
        raise HTTPException(
            409,
            detail={
                "code": "already_started",
                "message": "This group already started picking. Ask them to start a new session.",
            },
        )

    token = new_token()
    participant = Participant(
        session_id=session.id,
        token=token,
        display_name=await _unique_display_name(db, session.id, body.name.strip()),
        lat=body.lat,
        lon=body.lon,
        hard_constraints=body.hard_constraints.model_dump(),
        is_creator=False,
    )
    db.add(participant)
    await db.commit()
    await db.refresh(participant)

    return ParticipantJoined(participant_id=participant.id, token=token)


# --------------------------------------------------------------------------
# the solve
# --------------------------------------------------------------------------


@router.post("/sessions/{slug}/start", response_model=StartResult)
async def start_session(session: CurrentSession, db: DbSession, creator: Creator) -> StartResult:
    """Fetch places, run the feasibility filter, lock the candidate set."""
    return await run_start(db, session)


async def run_start(db: DbSession, session: Session) -> StartResult:
    """The solve setup, callable outside the request that owns the session.

    A group round starts itself the moment it is created, everyone's
    constraints are already known, so making someone tap "start" again would
    be asking a question the group already answered.
    """
    if session.status != "collecting":
        raise HTTPException(409, detail={"code": "already_started", "message": "Already started."})

    participants = list(session.participants)
    if not participants:
        raise HTTPException(422, detail={"code": "no_participants", "message": "Nobody has joined yet."})

    # Geographic centroid is the naive origin and is frequently wrong, the
    # midpoint of six addresses is often a highway interchange. It is the
    # stated v1 proxy; Phase 6 replaces it with intersected isochrones.
    center_lat, center_lon = centroid([(p.lat, p.lon) for p in participants])
    session.center_lat, session.center_lon = center_lat, center_lon

    try:
        await osm.ensure_area_cached(db, center_lat, center_lon, session.radius_m)
    except osm.OverpassUnavailable as exc:
        # Say what happened rather than leaving the button spinning. The cache
        # may still hold enough from an earlier search, so this only fails the
        # round when there is nothing to fall back on.
        log.warning("overpass unavailable: %s", exc)
        if not await osm.places_near(db, center_lat, center_lon, session.radius_m):
            raise HTTPException(
                503,
                detail={
                    "code": "places_unavailable",
                    "message": f"Could not load restaurants right now, {exc}. Try again in a minute.",
                },
            ) from exc

    places = await osm.places_near(db, center_lat, center_lon, session.radius_m)

    if not places:
        raise HTTPException(
            422,
            detail={
                "code": "no_places",
                "message": "No restaurants found nearby. Try a wider radius.",
                "binding_constraints": [],
            },
        )

    now = datetime.now(UTC)
    verdicts = feas.filter_places(places, participants, now)
    feasible = [v for v in verdicts if v.tier == feas.TIER_FEASIBLE]
    relaxations: list[str] = []

    def usable(vs: list[feas.Verdict]) -> int:
        return sum(1 for v in vs if v.tier != feas.TIER_ELIMINATED)

    # Relax in a fixed, stated order: distance, then price. Never dietary.
    #
    # A relaxation is adopted only if it actually produces more options. When
    # the shortage is missing tags rather than distance, widening the radius
    # changes nothing, and telling the group "we doubled the distance limit"
    # when their distance was never the binding factor is simply false.
    for multiplier, label in (
        (1.5, "widened the distance limit by 50%"),
        (2.0, "doubled the distance limit"),
    ):
        if len(feasible) >= settings.candidate_minimum:
            break
        candidate_verdicts = feas.filter_places(places, feas.relax(participants, distance_multiplier=multiplier), now)
        if usable(candidate_verdicts) > usable(verdicts):
            verdicts = candidate_verdicts
            feasible = [v for v in verdicts if v.tier == feas.TIER_FEASIBLE]
            relaxations = [label]

    if len(feasible) < settings.candidate_minimum:
        candidate_verdicts = feas.filter_places(
            places, feas.relax(participants, distance_multiplier=2.0, drop_price=True), now
        )
        if usable(candidate_verdicts) > usable(verdicts):
            verdicts = candidate_verdicts
            feasible = [v for v in verdicts if v.tier == feas.TIER_FEASIBLE]
            relaxations = [*relaxations, "ignored the price ceiling"]

    unverified = [v for v in verdicts if v.tier == feas.TIER_UNVERIFIED]
    eliminated = [v for v in verdicts if v.tier == feas.TIER_ELIMINATED]

    # OSM dietary coverage runs 1-6% even in dense cities, so for any group
    # with a restriction the fully-verified set is usually empty. Refusing to
    # proceed there means refusing nearly every real group. Instead the vote
    # runs on unverified candidates with the gap made loud: never presented
    # as satisfied, still carrying the per-person reason, and flagged on both
    # the ranking screen and the result.
    unverified_used = len(feasible) < settings.candidate_minimum and bool(unverified)
    pool = feasible + unverified if unverified_used else feasible

    if not pool:
        # Name whose constraints are binding. "No results" is useless; "no
        # options work for both Sam and Dev within 20 minutes" is actionable.
        raise HTTPException(
            422,
            detail={
                "code": "no_feasible_candidates",
                # A real conflict and an absence of data need completely
                # different things from the group, so they can't share copy.
                "message": (
                    "Nothing nearby works for everyone's requirements."
                    if eliminated
                    else "No restaurants nearby had enough information to check against your requirements."
                ),
                "binding_constraints": feas.binding_constraints(verdicts),
            },
        )

    pool.sort(key=lambda v: v.distance_m)
    chosen = pool[: settings.candidate_target]
    chosen_ids = {v.place.osm_id for v in chosen}

    # Every place gets a row: the locked set to be ranked, the rest to explain
    # a cut. `locked` is what separates the two, tier can't, since an
    # unverified place is sometimes in the vote and a feasible one beyond the
    # locked 6-8 never is.
    leftovers = [v for v in unverified + eliminated if v.place.osm_id not in chosen_ids][: settings.candidate_target * 3]
    for verdict in chosen + leftovers:
        db.add(
            Candidate(
                session_id=session.id,
                place_id=verdict.place.osm_id,
                tier=verdict.tier,
                locked=verdict.place.osm_id in chosen_ids,
                cut_reasons=verdict.as_json() or None,
            )
        )

    session.status = "ranking"
    await db.commit()
    await db.refresh(session)

    participants = sorted(session.participants, key=lambda p: p.joined_at)
    candidates = [c for c in session.candidates if c.locked]

    notes = feas.advisories(participants)
    notes += [{"constraint": "relaxed", "detail": f"Not much fit, so we {r}."} for r in relaxations]
    if unverified_used:
        notes.append(
            {
                "constraint": "unverified_data",
                "detail": (
                    "The map data couldn't confirm everyone's dietary requirements at these places, so they're in "
                    "the vote flagged rather than left out. Nothing here is confirmed safe, check with the "
                    "restaurant before you commit."
                ),
            }
        )

    return StartResult(
        status=session.status,
        candidates=[_candidate_out(c, participants) for c in candidates],
        advisories=notes,
        eliminated_count=len(eliminated),
        unverified_used=unverified_used,
    )


@router.post("/sessions/{slug}/rankings", response_model=RankingAccepted)
async def submit_ranking(
    body: RankingIn, session: CurrentSession, db: DbSession, participant: CurrentParticipant
) -> RankingAccepted:
    """Submit an ordering. Auto-solves once everyone has.

    Watching the count climb is what creates the urgency to finish, which is
    why the response carries submitted/total rather than a bare 200.
    """
    if session.status == "decided":
        raise HTTPException(409, detail={"code": "already_decided", "message": "The group already decided."})
    if session.status != "ranking":
        raise HTTPException(409, detail={"code": "not_ranking", "message": "This session isn't taking rankings yet."})

    rankable = {c.id for c in session.candidates if c.locked}
    submitted_ids = set(body.ordered_candidate_ids)

    if submitted_ids != rankable:
        raise HTTPException(
            422,
            detail={
                "code": "incomplete_ranking",
                "message": "Rank every option, and only the options offered.",
                "expected": sorted(str(c) for c in rankable),
            },
        )

    # Re-submission replaces rather than accumulates.
    await db.execute(delete(Ranking).where(Ranking.participant_id == participant.id))
    for index, candidate_id in enumerate(body.ordered_candidate_ids, start=1):
        db.add(Ranking(participant_id=participant.id, candidate_id=candidate_id, rank=index))
    await db.commit()

    participant_ids = [p.id for p in session.participants]
    count = await db.execute(
        select(func.count(func.distinct(Ranking.participant_id))).where(Ranking.participant_id.in_(participant_ids))
    )
    submitted = count.scalar_one() or 0
    total = len(participant_ids)

    if submitted >= total:
        await _solve(db, session)
        await db.refresh(session)

    return RankingAccepted(submitted=submitted, total=total, status=session.status)


async def _solve(db: DbSession, session: Session) -> Result:
    """Score, aggregate, annotate, persist."""
    participants = {p.id: p for p in session.participants}
    candidates = {c.id: c for c in session.candidates if c.locked}

    rows = await db.execute(
        select(Ranking).where(Ranking.participant_id.in_(list(participants))).order_by(Ranking.rank)
    )
    by_person: dict[str, list[str]] = {}
    for ranking in rows.scalars().all():
        if ranking.candidate_id not in candidates:
            continue
        by_person.setdefault(participants[ranking.participant_id].display_name, []).append(str(ranking.candidate_id))

    # Participants who never ranked are simply absent from the matrix. They
    # expressed no preference, so representing them with a made-up one would
    # be inventing an opinion the product does not have.
    by_person = {name: order for name, order in by_person.items() if len(order) == len(candidates)}
    if not by_person:
        raise HTTPException(422, detail={"code": "no_rankings", "message": "Nobody has ranked yet."})

    scores = borda_scores(by_person)

    all_participants = list(participants.values())
    distances = {
        str(cid): max((haversine_m(p.lat, p.lon, c.place.lat, c.place.lon) for p in all_participants), default=0.0)
        for cid, c in candidates.items()
    }

    decision = decide(scores, distances)
    ranked = annotate(decision, scores)
    for row in ranked:
        candidate = candidates[uuid.UUID(row["option"])]
        row["candidate_id"] = row["option"]
        row["name"] = candidate.place.name
        row["cuisine"] = candidate.place.cuisine or []
        row["lat"], row["lon"] = candidate.place.lat, candidate.place.lon
        row["distance_m"] = round(distances[row["option"]], 1)

    compare = comparison(decision, scores)
    for key in ("utilitarian", "maximin", "minimax_regret"):
        compare[key]["name"] = candidates[uuid.UUID(compare[key]["option"])].place.name
    compare["headline"] = compare["headline"].replace(
        decision.alternates["utilitarian"], candidates[uuid.UUID(decision.alternates["utilitarian"])].place.name
    )

    alternates = {
        "utilitarian": decision.alternates["utilitarian"],
        "maximin": decision.alternates["maximin"],
        "comparison": compare,
        "voters": sorted(by_person),
        "non_voters": sorted(p.display_name for p in all_participants if p.display_name not in by_person),
    }

    await db.execute(delete(Result).where(Result.session_id == session.id))
    result = Result(session_id=session.id, ranked=ranked, alternates=alternates, rule=decision.rule)
    db.add(result)
    session.status = "decided"
    await db.commit()
    await db.refresh(result)
    return result


@router.post("/sessions/{slug}/solve", response_model=ResultOut)
async def solve_session(session: CurrentSession, db: DbSession, creator: Creator) -> ResultOut:
    """Force the solve before everyone has ranked. Creator only."""
    if session.status == "collecting":
        raise HTTPException(409, detail={"code": "not_started", "message": "Start the session first."})

    existing = await db.get(Result, session.id)
    if existing is not None and session.status == "decided":
        result = existing
    else:
        result = await _solve(db, session)

    return ResultOut(
        ranked=result.ranked,
        alternates=result.alternates,
        comparison=result.alternates.get("comparison", {}),
        rule=result.rule,
        computed_at=result.computed_at,
    )
