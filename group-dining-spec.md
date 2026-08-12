# Group Dining Decider — Project Spec

**One line:** Six people, one link, fifteen seconds each, and the group chat stops arguing about where to eat.

---

## Why this project

**The annoyance is real and recurring.** Every group has had the forty-minute "I don't know, what do you want?" spiral. Unlike most side project problems, this one repeats weekly.

**Distribution is built into the mechanic.** You cannot use it alone. Every session puts the product in front of five to twenty people who have the same problem in their own groups. That's the same loop that made When2Meet and Doodle spread with zero marketing budget.

**The technical core is genuinely hard.** Not CRUD with a map on top. Preference aggregation across people with conflicting hard and soft constraints is social choice theory, and the naive answer is provably bad in a way you can demonstrate.

---

## The honest risks

**This idea has a graveyard.** Pluck, Nibbl, and a dozen others died. They died because getting six people to open a *new app* is harder than just arguing in the group chat. Everything below is subordinate to one constraint:

> No signup. No download. One link. Under fifteen seconds per person.

If any step of the flow takes longer than complaining in the group chat, the product loses to the group chat.

**Restaurant dietary data is unreliable.** OpenStreetMap tags are sparse and stale. Never present unknown as safe. This is a product decision, not just a data one.

**A ranked shortlist can recreate the paralysis you're solving.** Mitigation is presentational: rank three, make #1 visually dominant, and annotate the runners-up with what they cost and who they exclude.

---

## The mechanic

1. One person creates a session, gets a link, drops it in the group chat.
2. Each person opens it, sets location and constraints in a few taps. No account.
3. The system pulls candidate restaurants, filters by hard constraints, and proposes a set.
4. Everyone votes. Votes land live so people watch the group converge, which creates the urgency to finish.
5. Ranked shortlist of three, with reasoning and explicit tradeoffs.

Session state lives in the URL. Sessions expire after 24 hours.

---

## The core algorithm

This is the part that makes it a resume project. Three stages.

### Stage 1: Feasibility filter (hard constraints)

Any candidate violating *any* participant's hard constraint is eliminated. Not down-weighted, eliminated.

Hard constraints: dietary requirements (vegan, vegetarian, halal, kosher, gluten-free, nut and shellfish allergies), maximum travel time, maximum price tier, currently open.

**The subtlety that matters:** restaurant dietary data is frequently missing. Treat missing as `unknown`, never as `satisfied`. Candidates with unknown status for someone's hard constraint go into a separate "unverified" tier that's shown but visibly flagged. This is the difference between a product an allergic person trusts and one they abandon after a bad experience.

### Stage 2: Individual scoring (soft preferences)

Each participant scores each feasible candidate in [0,1] over cuisine preference, price fit, and travel time.

**Collect preferences ordinally, not cardinally.** Ask people to rank cuisines rather than rate them 1 to 5. Cardinal input invites strategic inflation, where everyone rates their favorite 5 and everything else 1, and the aggregation degenerates.

### Stage 3: Aggregation — the interesting decision

Implement several rules, show where each fails, and defend the choice. This is the part you walk an interviewer through.

**Utilitarian (maximize mean).** The obvious choice and the wrong one. If one person can't eat sushi and three mildly prefer it, the mean picks sushi and excludes someone entirely. Majority preference systematically overrides minority need.

**Egalitarian / maximin (maximize the minimum individual score).** Nobody has a terrible time. Fails differently: it converges on the option that's mediocre for everyone, which is how you end up at the chain restaurant nobody wanted.

**Minimax regret (recommended primary rule).** Minimize the maximum individual *regret*, where regret is the gap between what a person got and the best they could have gotten from the feasible set. This is fair relative to what was actually available, which correctly handles the case where someone's favorite cuisine simply doesn't exist nearby. They shouldn't be compensated for an option that was never on the table.

**Borda count** as a tiebreak and a robustness check against score inflation.

**Ship the comparison as a feature.** Show the user what pure majority vote would have picked and who it would have left out. That's the shareable insight, the launch content, and the interview story, all from the same code.

---

## Data sources

| Need | Source | Notes |
|---|---|---|
| Places, cuisine, hours | OpenStreetMap via Overpass API | Free, unlimited, no key. Cuisine tags decent, price and dietary sparse. |
| Better metadata | Foursquare Places | Free tier exists. Upgrade path if v1 gets traction. |
| Travel time / isochrones | OpenRouteService | Free tier includes isochrones. Only needed once you add travel fairness. |
| Best data, real cost | Google Places | Only if the thing actually takes off. |

Cache aggressively in Postgres keyed by geohash tile. Overpass is free but slow and rate-limited, so never call it on the request path if a cached tile is fresh.

---

## Data model

```
places          osm_id, name, lat, lon, cuisine[], price_tier,
                dietary_flags jsonb, hours jsonb, source, fetched_at
                -- global cache, shared across sessions

sessions        id, slug, created_at, expires_at, center_point,
                radius_m, status

participants    id, session_id, display_name, lat, lon,
                hard_constraints jsonb, preferences jsonb, joined_at

candidates      id, session_id, place_id, feasibility jsonb
                -- per-session snapshot, with why-eliminated reasons

votes           participant_id, candidate_id, rank, created_at
```

Store the *reason* a candidate was eliminated, not just the fact. The UI needs to say "three places were cut because Sam can't eat there," which is what makes the tool feel trustworthy rather than arbitrary.

---

## API surface

```
POST   /sessions                        create, returns slug
GET    /sessions/{slug}                 full state
POST   /sessions/{slug}/participants    join
PATCH  /participants/{id}               set location and constraints
POST   /sessions/{slug}/solve           fetch candidates, filter, rank
POST   /votes                           submit ranking
WS     /sessions/{slug}/live            live participant and vote updates
```

---

## Weekend scope

**Day 1**
- Session create and join, no auth, slug in URL
- Constraint input UI (dietary, price, distance)
- Overpass fetch with Postgres tile cache
- Feasibility filter with elimination reasons

**Day 2**
- Ordinal preference collection
- Three aggregation rules, minimax regret as default
- Ranked shortlist UI with tradeoff annotations
- WebSocket live updates
- Deploy to Fly.io or Render

**Cut from v1**
- Travel-time isochrones. Use haversine distance as the proxy. Add real isochrones in week two, since that's the most visual upgrade.
- Accounts, history, saved groups
- Native mobile. Mobile web only.

---

## Launch plan

Lead with the idea, not the app.

Write up why averaging group preferences systematically excludes people with dietary restrictions, with worked examples and the comparison between aggregation rules. Working title: *Why your group chat can't pick a restaurant.* Put the live app at the bottom as the demo.

Post to Hacker News, r/programming, and food subreddits. A technical writeup with a demo gets meaningfully more traction than "check out my app," draws exactly the audience who'd try it, and doubles as your interview story.

Instrument from day one: sessions created, participants per session, completion rate, and repeat sessions per creator. Repeat rate is the only number that tells you whether this is real.

---

## Resume bullets this produces

**Technical framing**

> Built a group decision engine implementing three social-choice aggregation rules (utilitarian, maximin, minimax regret) over conflicting hard and soft constraints, eliminating the minority-exclusion failure mode where majority preference overrides participants' dietary restrictions.

> Designed a two-tier feasibility model that distinguishes unverified from satisfied dietary data across sparse OpenStreetMap coverage, with per-candidate elimination reasoning surfaced to users.

**Entrepreneurial framing** (fill in after launch)

> Launched [name], a group dining decision tool that reached N users across M sessions in its first eight weeks through organic sharing, with zero paid acquisition.
