# Hangry

Six people, one link, dinner sorted. No signup, no download.

Hangry picks somewhere a group can eat by minimising the worst individual
*regret* rather than maximising the group average, then shows the group
what the popular answer would have cost, and whom.

```
web (Next.js)  ──HTTP──▶  api (FastAPI)  ──▶  Postgres 16
                               │
                               └──▶  Overpass API (cached by geohash tile)
```

---

## Running it

Postgres, then migrations, then both apps.

```bash
docker compose up -d
```

```bash
cd api && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/alembic upgrade head
```

```bash
cd api && .venv/bin/uvicorn app.main:app --reload --port 8000
```

```bash
cd web && npm install && npm run dev
```

Then open http://localhost:3000. `GET /api/health` should return
`{"api":"ok","db":"ok"}`.

## Tests

```bash
cd api && .venv/bin/python -m pytest -q
```

147 tests, against a real Postgres (`hangry_test`, created automatically)
rather than SQLite. The schema leans on JSONB, `text[]` and native uuid, and a filter
whose entire job is keeping `null` distinct from `"no"` should not be
validated on a database with different null semantics than production.

The one that matters is `tests/test_aggregation.py`. It pins every worked
number from `hangry-algorithm.md` and asserts that `api/app/aggregation.py`
has not drifted from the canonical `aggregate.py`.

```bash
python3 aggregate.py    # runs the six-person fixture standalone, no deps
```

---

## Groups and rounds

A **group** is a set of people and a permanent link. A **round** is one meal.

```
group  (permanent link, remembers who and what they can't eat)
  └── round  (24h, one decision)  ×  as many meals as you like
```

The first version had only rounds, and it showed: a session evaporated after
24 hours, so every meal began by re-collecting six names, six locations and
six sets of dietary constraints. That is the difference between a demo and
something a group actually uses on a Thursday.

**Still no accounts.** The group *is* its link. Membership is the same opaque
`localStorage` token used for participants, and deliberately the *same
token*, so a member's group token authenticates them inside every round and a
phone stores exactly one string per group.

**The payoff is round two.** Everyone's constraints are already known, so
starting a round skips joining and the constraint form entirely and goes
straight to ranking. Any member can start one, not just whoever created the
group. The people who eat together are peers.

**Who's eating.** A round defaults to the whole group, and the starter can
drop anyone who isn't coming. This is not cosmetic: applying an absent
member's dietary constraint would narrow the options for a meal they aren't
at. It also cuts the other way. With a celiac and a halal member excluded
from a test round, the candidate set went from *entirely unverified* to
fully verified, because there were fewer questions the sparse OSM data had to
answer.

**Constraints are snapshotted, not joined.** A round copies each member's
constraints when it starts, so editing your diet later never rewrites a
decision the group already made. Past results stay readable as they were
actually decided.

One round runs at a time per group. Two concurrent rounds would split the
group across two ballots, which is the failure this product exists to end.

## The algorithm

Three stages. Full walkthrough in `hangry-algorithm.md`.

**Stage 1, feasibility.** Hard constraints eliminate; they never
down-weight. Three tiers come out: `feasible`, `unverified` (nothing
violated, but the data cannot answer someone's constraint), `eliminated`.
Every cut stores *why*, naming a participant and a constraint.

**Stage 2, ordinal scoring.** People rank; rank converts to score via
normalised Borda, `(m - rank) / (m - 1)`. Never 1 to 5 ratings, since cardinal input
invites inflation and every rule degenerates into "whoever cared loudest
wins".

**Stage 3, aggregation.** All three rules are implemented; minimax regret
ships.

```
regret(p, o) = max_over_options(score[p]) - score[p][o]
winner       = argmin_o ( max_over_people regret(p, o) )
tiebreak     = utilitarian mean, then travel distance
```

The other two stay because the *comparison is a shipped feature*: the results
page shows what a straight majority vote would have picked and who it would
have excluded.

On the doc's six-person fixture all three rules pick differently: Sushi Bar,
Mediterranean Grill, Indian Kitchen. That divergence is the entire argument.

---

## The invariant

**Missing dietary data is never treated as satisfied.** Not anywhere.

`app/constraints.py` models this as a three-state `Status`
(`SATISFIED` / `VIOLATED` / `UNKNOWN`) rather than a boolean, because a
boolean forces `UNKNOWN` to collapse into one of the other two and whichever
way it collapses is wrong. `diet:*=limited` is `UNKNOWN`, not a quiet yes.
Relaxation loosens distance and price and **never** diets.

---

## What the real data actually looks like

Measured against live Overpass, one geohash-5 tile over the East Village,
Manhattan, one of the densest restaurant districts anywhere:

| constraint | tagged yes/only | tagged no | absent | coverage |
|---|---:|---:|---:|---:|
| vegetarian | 125 | 2 | 1905 | **6.3%** |
| vegan | 108 | 2 | 1921 | **5.5%** |
| gluten-free | 35 | 1 | 1997 | **1.8%** |
| halal | 29 | 0 | 2004 | **1.4%** |
| kosher | 15 | 0 | 2018 | **0.7%** |

2,033 named places. `opening_hours` on 61%, `cuisine` on 81%.

This is the finding rather than a bug or a tuning problem. For any group
containing a dietary restriction, the *fully verified* candidate set is
essentially always empty. A strict reading of "unverified is excluded from
the ranking" therefore means refusing to answer nearly every real group.

**How this build handles it.** When there aren't enough verified candidates,
the vote runs on unverified ones instead of dead-ending, flagged and never
softened. Each is labelled `unverified` on the ranking screen and the result,
carries the per-person reason ("no gluten-free information in the data, and
Sam needs gluten-free"), and the winner card says *Not verified, call
ahead*. Nothing is ever presented as safe. `unverified_used` on
`POST /start` says which mode you're in, and verified candidates always win
when enough exist.

This is the one deliberate departure from the PRD, and it is the difference
between a demo and something usable. It is easy to reverse: drop the
`unverified_used` branch in `start_session` to restore strict behaviour.

**Allergens are worse.** OSM has no allergen schema at all. The tags are
absent rather than sparse. Nut and shellfish allergies therefore cannot be filtered on, and
routing them through the unverified tier would tip *every* candidate into it
and destroy the signal the tier carries. They become a standing advisory
naming the person instead: *"OpenStreetMap has no allergen data, so nut
allergy could not be checked for any of these places. Jordan should confirm
with the restaurant."*

---

## Design

Built against Apple's Human Interface Guidelines, with three rules doing most
of the work.

**Hierarchy comes from size, weight and space before it comes from colour.**
Two typefaces, each with one job. Instrument Sans runs the interface, where
legibility at 13px matters more than personality. Instrument Serif appears
only on the lines that carry weight: the page headline and the name of the
restaurant the group is going to. Keeping the serif rare is what stops it
reading as decoration.

**Every pairing is measured, not judged by eye.** The previous palette had
three failures against WCAG, including the caption colour that carries the
cuisine and distance under every restaurant name (2.95:1, where 4.5:1 is the
floor). Every colour below clears 4.5:1 on both the canvas and the card
surface, in both themes.

| role | light | dark | worst ratio |
|---|---|---|---:|
| body text | `#1b1a16` | `#f0ece3` | 14.6:1 |
| secondary | `#565044` | `#aba396` | 6.9:1 |
| caption | `#6b6455` | `#938b7d` | 5.1:1 |
| brand | `#24503f` | `#7fa890` | 6.5:1 |
| caution | `#8c4a24` | `#cf9c3c` | 6.0:1 |

**Colour never carries meaning alone.** The unverified state always arrives
with an icon and the word beside it. This matters most in dark mode, where
the sage and the amber sit at almost identical luminance, so hue by itself
would separate them for nobody. Chip selection uses fill and weight rather
than a tick, which survives both colour blindness and a monochrome screen.

The palette is warm ivory, deep pine and aged brass. Saturation stays low so
the one thing on screen that can hurt someone has room to stand out. Nothing
is pure white; the lightest surface is `#fdfbf6`. Corners are cut close, 2px
to 6px. There are no gradients anywhere in the interface.

**Sizes are in rem**, so the browser text setting reaches the whole interface.
At 200 percent the body goes from 17px to 34px with no horizontal overflow,
which is the enlargement the HIG asks for and which the previous fixed-pixel
build could not do. Every interactive target clears 44pt, verified against
the live DOM rather than the stylesheet.

Labels are sentence case. The HIG writing guidance prefers it, and small
uppercase text is harder to read.

## Assets

All generated from source in the repo. There are no binary design files to
keep in sync.

| file | what it is |
|---|---|
| [`web/app/icon.svg`](web/app/icon.svg) | favicon and app icon |
| [`web/components/Logo.tsx`](web/components/Logo.tsx) | the same mark in product, plus the masthead |
| [`web/components/icons.tsx`](web/components/icons.tsx) | line icons on one 24px grid, 1.6 stroke |
| [`web/app/opengraph-image.tsx`](web/app/opengraph-image.tsx) | 1200x630 link preview, rendered by `next/og` |
| [`web/app/apple-icon.tsx`](web/app/apple-icon.tsx) | 180x180 iOS home screen icon |

The mark is a single fork, cut square, flat pine on ivory. The drag handle in
the ranking list is two horizontal rules, since a six dot grid reads as
texture at small sizes.

**The link preview is a distribution surface.** The only way Hangry travels is
one person pasting a link into a group chat, and a bare URL gets scrolled
past.

---

## Layout

```
aggregate.py              canonical algorithm, stdlib only, runs standalone
api/
  app/
    aggregation.py        port of the above + annotation/comparison glue
    constraints.py        the vocabulary and the three-state Status
    feasibility.py        Stage 1, tiers, cut reasons, relaxation
    osm.py                Overpass client, tag mapping, tile cache
    geo.py                geohash, haversine, centroid
    routes.py             sessions/rounds
    routes_groups.py      groups, members, starting rounds
    models.py schemas.py deps.py db.py config.py slug.py main.py
  alembic/versions/       0001 sessions · 0002 places · 0003 rankings
                          0004 locked   · 0005 groups and members
  tests/                  147 tests
web/
  app/
    page.tsx              /, create a group, and your groups list
    g/[slug]/page.tsx     the group: roster, invite, start a round
    s/[slug]/page.tsx     one round, driven by its status
    globals.css           design tokens and component classes
    layout.tsx            font, metadata, theme colour
    icon.svg  opengraph-image.tsx  apple-icon.tsx
  components/
    GroupView.tsx         roster, invite, start a round
    SessionView.tsx       one round: join → lobby → rank → result
    ConstraintForm.tsx    the joiner's entire flow
    Lobby.tsx  RankingList.tsx  Results.tsx
    Logo.tsx  icons.tsx  ui.tsx
  lib/                    api client, types, constraint vocabulary
```

## API

```
GET    /api/health

# groups, the durable layer
POST   /api/groups                       create + enrol founder
GET    /api/groups/{slug}                roster, history, live round
POST   /api/groups/{slug}/members        join; anyone with the link, no closing time
PATCH  /api/groups/{slug}/members/me     change your own details (partial)
DELETE /api/groups/{slug}/members/me     leave; past rounds keep the snapshot
POST   /api/groups/{slug}/rounds         start a round   409 if one is live
                                         → creates it *and* runs the solve setup

# rounds (also usable standalone, without a group)
POST   /api/sessions                     create + enrol creator
GET    /api/sessions/{slug}              full state; X-Participant-Token optional
POST   /api/sessions/{slug}/participants join            409 once started
POST   /api/sessions/{slug}/start        creator only    422 + binding_constraints
POST   /api/sessions/{slug}/rankings     participant     auto-solves on the last one
POST   /api/sessions/{slug}/solve        round creator, forces an early decision
```

`POST /rounds` both creates the round and runs the feasibility filter.
Everyone's constraints are already known, so making someone tap "start"
afterwards would re-ask a question the group already answered.

Auth is one opaque token per participant per session, in `localStorage`,
sent as `X-Participant-Token`. Not real auth, it stops accidental
cross-writes between six people in a group chat, which is the correct level
for an ephemeral session holding no personal data.

Two deviations from the PRD's contract, both deliberate:

- **410, not 404, for an expired session.** Phase 4 requires a dedicated
  expired-session page, which needs the two cases distinguishable.
- **`you` block on `GET /sessions/{slug}`.** Without it the client cannot
  tell which row in `participants` is itself, and a page reload would ask
  someone to rank again after they already had.

## Deploying

API on Fly.io, web on Vercel, Postgres wherever. The repo is configured for
it, `api/Dockerfile`, `api/fly.toml`, and the environment variables in the
two `.env.example` files are in place, and the container has been built and
run against Postgres to confirm it serves.

**[DEPLOY.md](DEPLOY.md) is the runbook.** It needs your accounts, so the
commands are yours to run. Three things in there are worth knowing before
you start:

- The **order is circular**. The web build bakes in the API's URL, and the
  API needs the web origin for CORS. Deploy the API first, then the web app,
  then set `CORS_ORIGINS`.
- Managed Postgres injects `DATABASE_URL` as `postgres://`, which SQLAlchemy
  resolves to psycopg2 and dies on. `app/config.py` rewrites the scheme, so
  paste the platform's value unchanged.
- `NEXT_PUBLIC_*` is compiled into the bundle. Setting it after the build
  does nothing until you redeploy.

## Not built
- **WebSockets** (Phase 5). Polling every 3s, as the PRD specifies for v1.
- **Isochrones, PostGIS, Foursquare** (Phases 6–7). Saved groups landed
  early, see *Groups and rounds*, because without them the product only
  worked once per set of friends.
- **Analytics.** No third-party script was added without asking. The numbers
  the PRD wants are all derivable from `sessions`, `participants` and
  `results`.
- **Price filtering.** OSM has no price data. Wired through the model,
  hidden in the UI, never filtered against nulls.
