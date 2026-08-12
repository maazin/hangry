# Hangry

Six people, one link, dinner sorted. No signup, no download.

Hangry picks somewhere a group can eat by minimising the worst individual
*regret* rather than maximising the group average — and then shows the group
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

126 tests, against a real Postgres (`hangry_test`, created automatically) —
not SQLite. The schema leans on JSONB, `text[]` and native uuid, and a filter
whose entire job is keeping `null` distinct from `"no"` should not be
validated on a database with different null semantics than production.

The one that matters is `tests/test_aggregation.py`. It pins every worked
number from `hangry-algorithm.md` and asserts that `api/app/aggregation.py`
has not drifted from the canonical `aggregate.py`.

```bash
python3 aggregate.py    # runs the six-person fixture standalone, no deps
```

---

## The algorithm

Three stages. Full walkthrough in `hangry-algorithm.md`.

**Stage 1 — feasibility.** Hard constraints eliminate; they never
down-weight. Three tiers come out: `feasible`, `unverified` (nothing
violated, but the data cannot answer someone's constraint), `eliminated`.
Every cut stores *why*, naming a participant and a constraint.

**Stage 2 — ordinal scoring.** People rank; rank converts to score via
normalised Borda, `(m - rank) / (m - 1)`. Never 1–5 ratings — cardinal input
invites inflation and every rule degenerates into "whoever cared loudest
wins".

**Stage 3 — aggregation.** All three rules are implemented; minimax regret
ships.

```
regret(p, o) = max_over_options(score[p]) - score[p][o]
winner       = argmin_o ( max_over_people regret(p, o) )
tiebreak     = utilitarian mean, then travel distance
```

The other two stay because the *comparison is a shipped feature*: the results
page shows what a straight majority vote would have picked and who it would
have excluded.

On the doc's six-person fixture all three rules pick differently — Sushi Bar,
Mediterranean Grill, Indian Kitchen — which is the entire argument.

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
Manhattan — one of the densest restaurant districts anywhere:

| constraint | tagged yes/only | tagged no | absent | coverage |
|---|---:|---:|---:|---:|
| vegetarian | 125 | 2 | 1905 | **6.3%** |
| vegan | 108 | 2 | 1921 | **5.5%** |
| gluten-free | 35 | 1 | 1997 | **1.8%** |
| halal | 29 | 0 | 2004 | **1.4%** |
| kosher | 15 | 0 | 2018 | **0.7%** |

2,033 named places. `opening_hours` on 61%, `cuisine` on 81%.

This is not a bug and not a tuning problem — it is the finding. For any group
containing a dietary restriction, the *fully verified* candidate set is
essentially always empty. A strict reading of "unverified is excluded from
the ranking" therefore means refusing to answer nearly every real group.

**How this build handles it.** When there aren't enough verified candidates,
the vote runs on unverified ones instead of dead-ending — flagged, never
softened. Each is labelled `unverified` on the ranking screen and the result,
carries the per-person reason ("no gluten-free information in the data, and
Sam needs gluten-free"), and the winner card says *Not verified — call
ahead*. Nothing is ever presented as safe. `unverified_used` on
`POST /start` says which mode you're in, and verified candidates always win
when enough exist.

This is the one deliberate departure from the PRD, and it is the difference
between a demo and something usable. It is easy to reverse: drop the
`unverified_used` branch in `start_session` to restore strict behaviour.

**Allergens are worse.** OSM has no allergen schema at all — not sparse,
absent. Nut and shellfish allergies therefore cannot be filtered on, and
routing them through the unverified tier would tip *every* candidate into it
and destroy the signal the tier carries. They become a standing advisory
naming the person instead: *"OpenStreetMap has no allergen data, so nut
allergy could not be checked for any of these places. Jordan should confirm
with the restaurant."*

---

## Design

Delivery apps are loud because they are selling you a hundred restaurants.
Hangry sells one decision, so the borrowing from DoorDash, Uber Eats and
Grubhub is structural rather than visual — full-width primary actions,
generous list rows, one saturated brand colour doing all the work. The rest
is restraint: hairline borders, one type family, real whitespace, and no
shadow doing a border's job.

**The rule the palette may not break.** `unverified` is amber, and stays
amber in both themes. It is the only thing on screen that can hurt someone,
so it never gets absorbed into the brand green. Anything that reads as a
safety state — the ranking banner, the winner card's *call ahead* block, the
per-row badge — uses `--warn`, never `--brand`.

**Tokens.** Everything lives in [`web/app/globals.css`](web/app/globals.css)
as custom properties, with a dark theme under `prefers-color-scheme`. The
same names are mirrored into `tailwind.config.ts` so utility classes and
component classes cannot drift into two different palettes. Change a colour
in one place and both follow.

| role | light | dark |
|---|---|---|
| `--bg` / `--surface` | `#f7f9f7` / `#ffffff` | `#0a0f0c` / `#111815` |
| `--text` / `--text-2` | `#0e1512` / `#59665f` | `#ecf2ee` / `#93a099` |
| `--brand` | `#099250` | `#24c67c` |
| `--warn` | `#b54708` | `#fdb022` |
| `--danger` | `#b42318` | `#fda29b` |

**Type.** Inter via `next/font`, self-hosted at build time — there is no
third-party request on the joiner's first paint, which is the only paint most
of them will wait for. Headings run `-0.028em` tracking, body `-0.011em`.
One family, four weights.

**Component classes.** `.card`, `.btn` (`-primary` / `-secondary` / `-quiet`),
`.chip`, `.field`, `.label`, `.badge`, `.panel-warn`, `.row`. Prefer these
over ad-hoc utilities so a restyle stays a one-file change. Interactive
targets are ≥52px on the primary path; every joiner is assumed to be on a
phone, one-handed, in a doorway.

**Accessibility.** One `:focus-visible` treatment everywhere. Drag-to-reorder
has arrow-button and keyboard equivalents — dragging is hard one-handed and
impossible with a screen reader, so the arrows are a parallel path rather
than a fallback. `prefers-reduced-motion` is honoured.

## Assets

All generated from source in the repo; there are no binary design files to
keep in sync.

| file | what it is |
|---|---|
| [`web/app/icon.svg`](web/app/icon.svg) | favicon and app icon |
| [`web/components/Logo.tsx`](web/components/Logo.tsx) | the same mark in-product, plus wordmark |
| [`web/components/icons.tsx`](web/components/icons.tsx) | line icons — one 24px grid, 1.75 stroke, round caps |
| [`web/app/opengraph-image.tsx`](web/app/opengraph-image.tsx) | 1200×630 link preview, rendered by `next/og` |
| [`web/app/apple-icon.tsx`](web/app/apple-icon.tsx) | 180×180 iOS home-screen icon |

**The mark** is a fork with a tick. A fork alone says "food app"; the tick is
what makes it this one, since the product's whole claim is that the argument
is over. Drawn as solid paths rather than strokes so it stays crisp at 16px.

**The link preview is a growth surface, not decoration.** The only way Hangry
spreads is one person pasting a link into a group chat, and a bare URL gets
scrolled past. Both generated images draw the mark as inline SVG rather than
a 🍴 emoji — Satori ships no colour emoji font and renders it as a grey
glyph, which quietly breaks the brand in the one place it is most visible.

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
    routes.py             every endpoint
    models.py schemas.py deps.py db.py config.py slug.py main.py
  alembic/versions/       0001 sessions · 0002 places · 0003 rankings · 0004 locked
  tests/                  126 tests
web/
  app/
    page.tsx              / — create a session
    s/[slug]/page.tsx     everything else, driven by session status
    globals.css           design tokens and component classes
    layout.tsx            font, metadata, theme colour
    icon.svg  opengraph-image.tsx  apple-icon.tsx
  components/
    SessionView.tsx       the state machine: join → lobby → rank → result
    ConstraintForm.tsx    the joiner's entire flow
    Lobby.tsx  RankingList.tsx  Results.tsx
    Logo.tsx  icons.tsx  ui.tsx
  lib/                    api client, types, constraint vocabulary
```

## API

```
GET    /api/health
POST   /api/sessions                     create + enrol creator
GET    /api/sessions/{slug}              full state; X-Participant-Token optional
POST   /api/sessions/{slug}/participants join            409 once started
POST   /api/sessions/{slug}/start        creator only    422 + binding_constraints
POST   /api/sessions/{slug}/rankings     participant     auto-solves on the last one
POST   /api/sessions/{slug}/solve        creator only, forces an early decision
```

Auth is one opaque token per participant per session, in `localStorage`,
sent as `X-Participant-Token`. Not real auth — it stops accidental
cross-writes between six people in a group chat, which is the correct level
for an ephemeral session holding no personal data.

Two deviations from the PRD's contract, both deliberate:

- **410, not 404, for an expired session.** Phase 4 requires a dedicated
  expired-session page, which needs the two cases distinguishable.
- **`you` block on `GET /sessions/{slug}`.** Without it the client cannot
  tell which row in `participants` is itself, and a page reload would ask
  someone to rank again after they already had.

## Not built

- **Deploy.** Phase 0 asks for both apps live on day zero. That needs
  Vercel/Fly accounts, so it is yours to run — nothing else is blocking it.
- **WebSockets** (Phase 5). Polling every 3s, as the PRD specifies for v1.
- **Isochrones, PostGIS, Foursquare, saved groups** (Phases 6–8).
- **Analytics.** No third-party script was added without asking. The numbers
  the PRD wants are all derivable from `sessions`, `participants` and
  `results`.
- **Price filtering.** OSM has no price data. Wired through the model,
  hidden in the UI, never filtered against nulls.
