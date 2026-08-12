# Hangry — Product Requirements & Build Plan

**Status:** ready to build
**Owner:** Maazin Shaikh
**Target:** v1 shipped and deployed in one weekend, public launch within 8 weeks

---

## 1. Problem

A group of friends wants to eat. Somebody asks where. Forty minutes of "idk, what do you want?" follows, three restaurants get suggested and abandoned, and one person eventually decides out of exhaustion. Every group has this problem, weekly.

The reason it doesn't get solved is not that deciding is hard. It's that the fair answer and the popular answer are different, and group chats can only produce the popular one. Majority preference systematically overrides minority need, so the person with celiac disease or the person who's vegetarian either speaks up repeatedly or eats badly.

## 2. What Hangry is

One person creates a session and drops a link in the group chat. Everyone opens it, sets their location and dietary constraints, and ranks the handful of places that actually work for the whole group. Hangry returns a ranked shortlist of three with explicit reasoning about what each option costs whom.

No signup. No download. One link.

## 3. Non-goals

- **Not a discovery product.** Hangry does not help you find new restaurants or save ones you liked. It decides among what's nearby right now.
- **Not a reservation product.** No booking, no waitlist integration in v1.
- **Not a social network.** No profiles, no follows, no feed. Sessions are ephemeral.
- **Not a review platform.** Hangry consumes place data, it does not collect opinions about restaurants beyond a single session.

## 4. The constraint everything is subordinate to

> **No signup. No download. One link. Under 30 seconds per person.**

This idea has a graveyard behind it — Pluck, Nibbl, and a dozen others. They died because getting six people to install a new app is harder than arguing in the group chat. Any feature that adds a step to the joiner's flow is presumed guilty. The creator can absorb friction; joiners cannot.

**Design rule:** if a change adds a tap for the five people who didn't start the session, it needs to earn it explicitly.

## 5. Users

| Role | Does | Friction budget |
|---|---|---|
| **Creator** | Starts session, sets radius, shares link, triggers the solve | ~45 seconds, high tolerance |
| **Joiner** | Opens link, sets location + constraints, ranks candidates | ~30 seconds, near-zero tolerance |

There are no accounts. A participant is identified by an opaque token stored in `localStorage`, scoped to the session slug.

## 6. Core loop

```
1. Creator  POST /sessions              → slug, creator token
2. Creator  shares hangry.app/s/{slug}
3. Joiners  POST /sessions/{slug}/participants   (name, location, hard constraints)
4. Creator  POST /sessions/{slug}/start
            → fetch places near centroid
            → apply feasibility filter across ALL participants
            → lock candidate set at 6–8 survivors
            → status: collecting → ranking
5. Everyone POST /sessions/{slug}/rankings        (ordered candidate ids)
6. Auto     when all have ranked (or creator forces)
            → compute scores, run minimax regret
            → status: ranking → decided
7. Everyone sees ranked shortlist with tradeoff annotations
```

**Late joiners.** In v1, joining after `start` is rejected with a clear message. Handling mid-round joins correctly means re-running the feasibility filter and potentially invalidating rankings already submitted. Do not attempt it this weekend.

## 7. The algorithm

Full walkthrough with worked numbers is in `hangry-algorithm.md`. Canonical implementation is `aggregate.py`. Summary:

**Stage 1 — feasibility filter.** Hard constraints (dietary, price ceiling, max distance, open now) eliminate candidates outright. They never down-weight.

Missing data is `unknown`, never `satisfied`. Candidates with unknown status on someone's hard constraint go to an `unverified` tier — shown, visibly flagged, excluded from the primary ranking. This is a product requirement, not a data caveat. A user with celiac disease abandons the product permanently after one bad guess.

Every elimination stores its reason. The UI must be able to say "three places were cut because Sam can't eat there."

**Stage 2 — ordinal scoring.** Participants rank the surviving candidates. Rank converts to score via normalized Borda:

```
score = (m - rank) / (m - 1)     # m = number of candidates, rank 1-indexed
```

Never collect 1–5 ratings. Cardinal input invites inflation and the aggregation degenerates into "whoever cared loudest wins."

**Stage 3 — aggregation.** Implement all three. Ship minimax regret.

```
regret(p, o) = max_over_options(score[p]) - score[p][o]
winner       = argmin_o ( max_over_people regret(p, o) )
tiebreak     = utilitarian mean, then travel distance
```

The other two rules stay in the codebase because the **comparison is a shipped feature**: the results page shows what pure majority vote would have picked and who it would have excluded. That comparison is the launch content, the screenshot people share, and the interview story.

**Empty feasible set.** Relax in a fixed, stated order: distance, then price. **Never silently relax a dietary constraint.** If still empty, name whose constraints are binding: *"No options work for both Sam and Dev within 20 minutes. Widen the radius?"*

## 8. Architecture

```
Next.js (Vercel)  ──HTTP/WS──▶  FastAPI (Fly.io)  ──▶  Postgres
                                       │
                                       └──▶  Overpass API (cached by geohash tile)
```

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI, Python 3.11+ | Already on your resume, matches RecallRadar |
| ORM | SQLAlchemy 2.0 async + Alembic | Standard, migration story for later phases |
| Validation | Pydantic v2 | Request/response contracts |
| DB | Postgres 16 | PostGIS deferred to Phase 4 |
| Realtime | FastAPI WebSockets, in-process pub/sub | Single instance in v1. Redis pub/sub when you scale out. |
| Frontend | Next.js App Router, TypeScript, Tailwind | On your resume, deploys in minutes |
| Ranking UI | `dnd-kit` | Drag-to-reorder on desktop, touch-friendly on mobile |
| Places | Overpass API | Free, unlimited, no key |
| Tests | pytest + httpx AsyncClient | |

**Why in-process pub/sub in v1:** a WebSocket broadcast layer backed by Redis is the correct long-term answer and the wrong weekend answer. A dict of `session_id → set[WebSocket]` works perfectly on one instance. Phase 6 swaps it.

## 9. Data model

```sql
-- global place cache, shared across all sessions
create table places (
  osm_id       text primary key,
  name         text not null,
  lat          double precision not null,
  lon          double precision not null,
  geohash5     text not null,
  cuisine      text[] not null default '{}',
  price_tier   smallint,                          -- 1..4, null = unknown
  diet_flags   jsonb not null default '{}',       -- {"vegetarian":"yes","gluten_free":null}
  hours        text,                              -- raw OSM opening_hours string
  source       text not null default 'osm',
  fetched_at   timestamptz not null default now()
);
create index places_geohash5_idx on places (geohash5);

-- which tiles we've already pulled, so we never hit Overpass on the request path
create table tile_cache (
  geohash5     text primary key,
  fetched_at   timestamptz not null default now()
);

create table sessions (
  id           uuid primary key default gen_random_uuid(),
  slug         text unique not null,
  status       text not null default 'collecting',   -- collecting|ranking|decided|expired
  center_lat   double precision,
  center_lon   double precision,
  radius_m     int not null default 5000,
  created_at   timestamptz not null default now(),
  expires_at   timestamptz not null default now() + interval '24 hours'
);

create table participants (
  id                uuid primary key default gen_random_uuid(),
  session_id        uuid not null references sessions(id) on delete cascade,
  token             text not null,                  -- opaque, client-stored
  display_name      text not null,
  lat               double precision not null,
  lon               double precision not null,
  hard_constraints  jsonb not null default '{}',
  is_creator        boolean not null default false,
  joined_at         timestamptz not null default now()
);
create unique index participants_session_token_idx on participants (session_id, token);

create table candidates (
  id             uuid primary key default gen_random_uuid(),
  session_id     uuid not null references sessions(id) on delete cascade,
  place_id       text not null references places(osm_id),
  tier           text not null,        -- feasible|unverified|eliminated
  cut_reasons    jsonb,                -- [{"participant":"Sam","constraint":"gluten_free"}]
  unique (session_id, place_id)
);

create table rankings (
  participant_id uuid not null references participants(id) on delete cascade,
  candidate_id   uuid not null references candidates(id) on delete cascade,
  rank           int not null,
  created_at     timestamptz not null default now(),
  primary key (participant_id, candidate_id)
);

create table results (
  session_id   uuid primary key references sessions(id) on delete cascade,
  ranked       jsonb not null,      -- [{candidate_id, max_regret, mean, annotation}]
  alternates   jsonb not null,      -- what utilitarian and maximin would have picked
  rule         text not null default 'minimax_regret',
  computed_at  timestamptz not null default now()
);
```

**Note on `cut_reasons`:** storing why a candidate was eliminated is not optional. It is the difference between a result that reads as reasoned and one that reads as arbitrary.

## 10. API contract

```
POST   /api/sessions
       body   { center: {lat, lon}, radius_m, creator: {name, lat, lon, hard_constraints} }
       200    { slug, participant_id, token, status }

GET    /api/sessions/{slug}
       200    { status, participants[], candidates[], result? }
       404    unknown or expired slug

POST   /api/sessions/{slug}/participants
       body   { name, lat, lon, hard_constraints }
       200    { participant_id, token }
       409    session already started

POST   /api/sessions/{slug}/start          [creator only]
       200    { candidates[], status: "ranking" }
       422    no feasible candidates + { binding_constraints[] }

POST   /api/sessions/{slug}/rankings       [auth: participant token]
       body   { ordered_candidate_ids: [...] }
       200    { submitted: n, total: m }

POST   /api/sessions/{slug}/solve          [creator only, or auto when all submitted]
       200    { ranked[], alternates, status: "decided" }

WS     /api/sessions/{slug}/live
       server→client events:
         participant_joined  { name, count }
         ranking_submitted   { submitted, total }
         session_started     { candidates[] }
         result_ready        { ranked[], alternates }
```

Participant auth is the opaque token in an `X-Participant-Token` header. Not real auth. It stops accidental cross-writes, nothing more, and that is the correct level of security for an ephemeral session with no personal data.

---

# Build phases

Each phase has a **definition of done**. Do not start phase N+1 until phase N's DoD passes. This matters more than usual if you're driving with Claude Code, which will happily scaffold all six phases at once and leave you with a codebase you can't debug.

## Phase 0 — Skeleton (1 hour)

Repo, both apps running locally, one endpoint responding, deploy pipeline proven.

- Monorepo: `/api` (FastAPI), `/web` (Next.js)
- `docker-compose.yml` with Postgres only
- Alembic initialized, empty migration applied
- `GET /api/health` returns 200
- Next.js page fetches health and renders the status
- **Deploy both to production now, on day zero, with nothing in them**

**DoD:** a live URL renders "api: ok". Deploying an empty app on day zero costs 45 minutes. Discovering your deploy is broken on Sunday at 10pm costs the project.

## Phase 1 — Sessions and joining (3–4 hours)

- Migration for `sessions`, `participants`
- `POST /api/sessions`, `GET /api/sessions/{slug}`, `POST /api/sessions/{slug}/participants`
- Slug generation: 6-char base32, collision-retry
- Token generation and `X-Participant-Token` dependency
- Frontend: create page, `/s/{slug}` join page
- Constraint input: dietary chips (vegetarian, vegan, halal, kosher, gluten-free, nut allergy, shellfish allergy), price ceiling, max distance
- Location via browser geolocation, with manual address fallback
- Participant list rendering, polled every 3s (WebSockets come in Phase 5)

**DoD:** create a session on your laptop, open the link on your phone, join with different constraints, see both participants listed on both devices.

## Phase 2 — Places and feasibility (4–5 hours)

The most annoying phase. Budget accordingly.

- Migration for `places`, `tile_cache`, `candidates`
- Overpass client: query `amenity=restaurant|fast_food|cafe` within a bounding box
- Geohash-5 tiling (~5km cells), cache tiles in Postgres, TTL 30 days
- OSM tag mapping — the fiddly part:
  - `diet:vegetarian` / `diet:vegan` / `diet:gluten_free` / `diet:halal` / `diet:kosher` → `yes`, `no`, `only`, or **null for absent**
  - `cuisine` is semicolon-delimited, split it
  - `opening_hours` is its own grammar; use the `opening-hours` Python package, don't parse it yourself
  - No price data in OSM. Leave `price_tier` null and hide the price filter in v1 rather than faking it.
- Feasibility filter with `cut_reasons` populated
- Unverified tier for null-on-a-required-flag
- `POST /start`: fetch → filter → select 6–8 → lock → status `ranking`

**DoD:** start a session with two conflicting dietary constraints and get a candidate list where you can explain, per eliminated place, exactly who cut it and why.

**Expect OSM data to be worse than you hope.** Dietary tags are sparse outside dense urban areas. If your test area returns almost nothing, that's real, and it's a finding worth writing about, not a bug to fix.

## Phase 3 — Ranking and the solve (3–4 hours)

- Migration for `rankings`, `results`
- Port `aggregate.py` into `api/app/aggregation.py` unchanged in logic
- Borda rank→score conversion
- `POST /rankings`, `POST /solve`
- Auto-solve when submission count reaches participant count
- Frontend: drag-to-reorder candidate list (`dnd-kit`), submit
- Results page: ranked three, tradeoff annotations, and the "what majority vote would have picked" comparison

**DoD:** the six-person scenario in `hangry-algorithm.md` runs end to end through the real API and produces Indian Kitchen, with Sushi Bar shown as the majority-vote alternative and Jordan named as who it excludes.

## Phase 4 — Ship it (2 hours)

- Empty states, loading states, error states
- Expired session page
- OG tags so the link previews properly in iMessage, WhatsApp, and Discord — **this is a growth feature, not polish.** A link that renders as a bare URL in a group chat gets ignored.
- Mobile layout pass. Assume 100% of joiners are on phones.
- Basic analytics: sessions created, participants per session, completion rate, repeat sessions per creator

**DoD:** you run a real session with real friends at a real mealtime, on phones, and it works.

---

# Later phases

## Phase 5 — Realtime (post-weekend)

Replace polling with WebSockets. In-process `dict[session_id, set[WebSocket]]` pub/sub. Broadcast joins, submissions, and results. Handle reconnect by re-fetching full state on open rather than replaying events.

Watching other people's rankings land live is what creates the urgency to finish. Polling works but feels dead.

## Phase 6 — Travel fairness

The most visually impressive upgrade and the reason to add PostGIS.

- OpenRouteService isochrones per participant (free tier)
- Intersect polygons in PostGIS, restrict candidates to the shared reachable area
- Fairness bound: nobody's travel time exceeds 1.4× the group median
- Map UI with the overlapping reachable regions shading in as people join

This is where the product becomes screenshot-worthy. Geographic centroid is the naive answer and is frequently wrong — the midpoint of six addresses is often a highway interchange.

## Phase 7 — Data quality

- Foursquare Places for price tier and better dietary coverage
- Crowdsourced verification: after a session, ask "could everyone eat there?" and use the answers to fill the gaps OSM leaves. This is the only defensible data moat available to you, and it compounds with usage.
- Confidence scoring per place, surfaced in the UI

## Phase 8 — Retention

Everything above is single-session. These make it recur:

- Saved groups: same six people, one tap, constraints remembered
- "Not there again" — soft penalty on places the group chose recently
- Post-meal one-tap feedback feeding the group's preference priors

## Phase 9 — If it actually works

- Native app or PWA with push
- Reservation handoff (Resy, OpenTable affiliate links) — the only obvious revenue path
- Restaurant-side tooling — pay to surface when you fit a group's constraints, which is honest advertising because it's constraint-matched rather than bid-ranked

---

# Instructions for Claude Code

**Work one phase at a time.** Do not let it scaffold ahead. The failure mode is a plausible-looking six-phase codebase that doesn't run and that you can't debug because you didn't write it.

**Per-phase prompt shape:**

> Implement Phase N of HANGRY-PRD.md. Read the PRD and the existing code first. Only touch files this phase needs. Write tests alongside, not after. Stop when the phase DoD passes and report what you did and what you skipped.

**Standing rules to give it:**

1. `aggregate.py` is canonical. The API's aggregation module must produce identical output on the six-person fixture. Assert this in a test.
2. Never treat missing dietary data as satisfied. Anywhere. This is the one invariant with real-world consequences.
3. No auth beyond the participant token. Don't add users, sessions, JWTs, or OAuth.
4. No Redis, no Celery, no Kafka in v1. If it suggests them, decline.
5. Every `cut_reason` must name a participant and a constraint. Never a bare boolean.
6. Ask before adding a dependency.

**Testing expectations by phase:**

| Phase | Tests |
|---|---|
| 1 | slug collisions, token rejection on wrong session, join-after-start 409 |
| 2 | OSM tag mapping table-driven, null-vs-no distinction, tile cache hit and miss |
| 3 | full six-person fixture, all three rules, tie-break, empty feasible set, single participant |
| 4 | one end-to-end happy path via `httpx.AsyncClient` |

Phase 3's fixture test is the one that matters. It's the correctness core, it's what you'll be asked about in interviews, and it's the thing most likely to silently break during a refactor.

---

# Metrics

Instrument in Phase 4, before launch.

| Metric | Meaning |
|---|---|
| Sessions created | Top of funnel |
| Participants per session | Is the viral loop working? Below 3 means it isn't. |
| Completion rate | Sessions reaching `decided`. Below 50% means the flow is too long. |
| **Repeat sessions per creator** | **The only number that matters.** Everything else is a spike. |
| Time from create to decided | Target under 5 minutes |

## Success criteria

**Weekend:** deployed, works on phones, you used it with real friends and it produced a real answer.

**8 weeks:** 500+ sessions, 3+ average participants, and at least 20% of creators running a second session. If repeat rate is near zero, the product is a novelty and you should say so publicly in a writeup rather than quietly abandoning it. A candid postmortem of a failed launch reads better in interviews than an unmaintained repo.

---

# Launch

Lead with the idea, not the app.

Publish **"Why your group chat can't pick a restaurant"** — the aggregation walkthrough with the worked tables, arguing that the fair answer and the popular answer diverge and the fix is fifteen lines of math. Hangry sits at the bottom as the live demo.

Post to Hacker News, r/programming, and food subreddits. A technical writeup with a working demo outperforms "check out my app" by an order of magnitude, draws exactly the audience who will try it, and doubles as the story you tell in interviews.

---

# Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Group won't adopt a new tool | **High** | Zero-friction joiner flow is the entire design constraint |
| OSM dietary data too sparse | **High** | Unverified tier makes gaps visible instead of dangerous; Phase 7 fixes properly |
| Ranked shortlist recreates paralysis | Medium | #1 visually dominant, runners-up annotated with what they cost |
| Overpass rate limits or downtime | Medium | Tile cache means it's never on the request path |
| Someone eats something they shouldn't | **High** | Never say "safe." Say "no known conflicts in the listed data," show the source, flag unknowns |
| Public launch spikes and dies | Medium | Instrument repeat rate from day one so you know within two weeks |

---

# Resume bullets

**Technical**

> Built a group decision engine implementing three social-choice aggregation rules (utilitarian, maximin, minimax regret) over conflicting hard and soft constraints, eliminating the minority-exclusion failure mode where majority preference overrides participants' dietary restrictions.

> Designed a two-tier feasibility model distinguishing unverified from satisfied dietary data across sparse OpenStreetMap coverage, with per-candidate elimination reasoning surfaced to end users.

**Entrepreneurial** (fill in post-launch)

> Launched Hangry, a group dining decision tool that reached N users across M sessions in its first eight weeks through organic sharing, with zero paid acquisition.
