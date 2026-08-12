# Hangry — the algorithm, walked through

Six friends. Seven nearby restaurants. Three ways to aggregate their preferences, and **all three pick a different restaurant**. That divergence is the product.

---

## The group

| Person | Hard constraint |
|---|---|
| Maazin | none |
| Ana | none |
| Sam | celiac, no gluten |
| Priya | vegetarian |
| Jordan | none |
| Dev | halal |

Everyone: within 20 minutes, `$$` or under.

---

## Stage 1 — feasibility filter

Hard constraints eliminate. They never down-weight.

| Candidate | Gluten-free | Vegetarian | Halal | Result |
|---|---|---|---|---|
| Ramen House | no | yes | yes | **cut** — Sam |
| Taqueria Sol | yes | yes | no | **cut** — Dev |
| Burger Joint | no | yes | yes | **cut** — Sam |
| Thai Garden | yes | yes | *unknown* | **unverified tier** |
| Mediterranean Grill | yes | yes | yes | feasible |
| Indian Kitchen | yes | yes | yes | feasible |
| Sushi Bar | yes | yes | yes | feasible |

Seven candidates become three.

**The design decision that matters here:** Thai Garden's halal status is missing from OpenStreetMap, not confirmed false. Missing is not the same as satisfied. It goes into a separate, visibly flagged tier rather than into the feasible set. Anyone who has actually managed a food restriction will abandon a product that guesses on this once, so the tiering is not defensive engineering, it's the product.

Store *why* each candidate was cut. The UI needs to say "three places were cut because Sam can't eat there," which is what makes the result feel reasoned instead of arbitrary.

---

## Stage 2 — individual scores

Each person scores each feasible option in [0,1] from cuisine ranking, price fit, and distance.

| | Mediterranean | Indian | Sushi |
|---|---|---|---|
| Maazin | 0.65 | 0.80 | 0.90 |
| Ana | 0.70 | 0.75 | 1.00 |
| Sam | 0.65 | 0.85 | 0.90 |
| Priya | 0.70 | 0.95 | 0.80 |
| Jordan | 0.70 | 0.40 | **0.10** |
| Dev | 0.65 | 0.80 | 0.90 |

Jordan does not eat sushi. Not an allergy, he just hates it, so it's a soft preference and it does not eliminate anything.

**Collect this ordinally.** Ask people to rank cuisines, then convert to scores internally. If you ask for 1-to-5 ratings directly, everyone rates their favorite 5 and everything else 1, and every aggregation rule degenerates into "whoever cared loudest wins."

---

## Stage 3 — aggregation, and why the obvious answer is wrong

### Utilitarian: maximize the mean

| Option | Mean |
|---|---|
| Mediterranean | 0.675 |
| Indian | 0.758 |
| **Sushi** | **0.767** |

**Picks Sushi Bar.** Highest group average. Jordan scores 0.10 and doesn't eat dinner.

This is the failure mode almost every group app ships. Five people mildly preferring something outweighs one person for whom it's unusable. The mean can't see the difference between "everyone is fine" and "most people are delighted and one person is excluded."

### Egalitarian (maximin): maximize the worst individual score

| Option | Minimum |
|---|---|
| **Mediterranean** | **0.650** |
| Indian | 0.400 |
| Sushi | 0.100 |

**Picks Mediterranean Grill.** Nobody scores below 0.65. Also nobody scores above 0.70.

Overcorrected. This is the rule that lands you at the chain restaurant nobody wanted but nobody objected to. It optimizes against disaster instead of toward a good dinner.

### Minimax regret: minimize the worst individual regret

Regret is what a person gave up **relative to the best they could have gotten from the feasible set**.

`regret(person, option) = best_available(person) − score(person, option)`

| | Mediterranean | Indian | Sushi |
|---|---|---|---|
| Maazin | 0.25 | 0.10 | 0.00 |
| Ana | 0.30 | 0.25 | 0.00 |
| Sam | 0.25 | 0.05 | 0.00 |
| Priya | 0.25 | 0.00 | 0.15 |
| Jordan | 0.00 | 0.30 | **0.60** |
| Dev | 0.25 | 0.10 | 0.00 |
| **max regret** | **0.30** | **0.30** | **0.60** |

Sushi is out: it costs Jordan 0.60, twice the worst case of either alternative. Mediterranean and Indian tie at 0.30, broken by utilitarian mean, and **Indian Kitchen wins**.

### The result

| Rule | Picks | Problem |
|---|---|---|
| Utilitarian | Sushi Bar | Jordan doesn't eat |
| Maximin | Mediterranean Grill | nobody's happy |
| **Minimax regret** | **Indian Kitchen** | — |

**Why regret is the right frame.** It measures against what was *actually achievable*, not against some ideal. If Jordan's real favorite was barbecue and barbecue got eliminated by Sam's celiac constraint, minimax regret does not try to compensate him for it. He never could have had it. That property is exactly why the output feels fair to a human rather than arbitrary, and it's the thing that's hard to arrive at by intuition alone.

---

## The shortlist you actually render

> **1. Indian Kitchen** — best balance. Nobody gives up more than a little.
> **2. Mediterranean Grill** — safest option, but nobody's first choice.
> **3. Sushi Bar** — four of you would love it. Jordan wouldn't eat.

That third line is the whole product. It shows the group what the popular answer would have cost them, which is both the fairness argument and the thing people screenshot.

---

## Implementation notes

**Complexity** is O(people × options). Irrelevant at this scale. Don't optimize it, optimize the data fetch.

**Tiebreak chain:** minimax regret → utilitarian mean → travel distance. Ties are common with small groups and coarse scores, so define this explicitly rather than letting sort order decide.

**Empty feasible set** is the important edge case. Relax in a fixed, stated order: distance first, then price. **Never silently relax a dietary constraint.** If it's still empty, say so and name whose constraint is binding: "No options work for both Sam and Dev within 20 minutes. Widen the radius?"

**Strategic voting.** Minimax regret is manipulable. Claim to hate everything except your favorite and your regret dominates the calculation. Ordinal input blunts this, since a ranking can't express intensity. If it becomes a real problem, cap how many options one person can rank at the bottom.

**Degenerate cases.** One participant, or all options scoring identically, collapse all three rules to the same answer. Test them anyway, they're where off-by-one bugs live.

---

## Why this is the launch post

You now have a piece of writing that argues something specific and slightly counterintuitive, with worked numbers proving it: *the fair way to pick a restaurant is not the popular way, and the math to fix it is fifteen lines.*

Title it something like **"Why your group chat can't pick a restaurant"**, put the tables in it, put Hangry at the bottom as the live demo. That post is your Hacker News submission, your portfolio piece, and your answer when an interviewer asks about a technical decision you had to defend. One artifact, three jobs.
