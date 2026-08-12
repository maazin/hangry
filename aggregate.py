"""Hangry — canonical aggregation reference.

This is the source of truth for the decision math. `api/app/aggregation.py`
must produce identical output on the six-person fixture; that equivalence is
asserted in `api/tests/test_aggregation.py`.

Stdlib only, on purpose. It runs standalone (`python aggregate.py`) so the
algorithm can be demonstrated and argued about without booting the API.

Three rules, one shipped:

    utilitarian     argmax_o  mean_p  score[p][o]
    maximin         argmax_o  min_p   score[p][o]
    minimax regret  argmin_o  max_p   regret[p][o]

    regret(p, o) = max_over_options(score[p]) - score[p][o]

Regret is measured against what was *actually achievable* from the feasible
set, not against an ideal. If someone's favourite cuisine was eliminated by
another participant's dietary constraint, minimax regret does not try to
compensate them for it — they never could have had it. That property is why
the output reads as fair to a human rather than arbitrary.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# person -> option -> score in [0, 1]
ScoreMatrix = dict[str, dict[str, float]]

# Scores are floats; comparisons need a tolerance or ties go undetected and
# the tiebreak chain never runs.
EPS = 1e-9


# --------------------------------------------------------------------------
# Stage 2 — ordinal input becomes cardinal scores
# --------------------------------------------------------------------------


def borda_scores(rankings: dict[str, list[str]]) -> ScoreMatrix:
    """Convert per-person orderings into normalised Borda scores in [0, 1].

        score = (m - rank) / (m - 1)      m = option count, rank 1-indexed

    Best-ranked option scores 1.0, worst scores 0.0.

    We collect ordinally and convert here rather than asking people for 1-5
    ratings directly. Cardinal input invites inflation — everyone rates their
    favourite 5 and everything else 1 — and every rule below degenerates into
    "whoever cared loudest wins".
    """
    if not rankings:
        return {}

    option_counts = {len(order) for order in rankings.values()}
    if len(option_counts) > 1:
        raise ValueError(f"participants ranked different numbers of options: {sorted(option_counts)}")

    m = option_counts.pop()
    if m == 0:
        raise ValueError("cannot score an empty option set")

    scores: ScoreMatrix = {}
    for person, order in rankings.items():
        if len(set(order)) != m:
            raise ValueError(f"{person} submitted a ranking with duplicates: {order}")
        # A single option is trivially everyone's best; the formula divides by
        # zero here, so short-circuit rather than special-casing downstream.
        scores[person] = {opt: 1.0 if m == 1 else (m - 1 - i) / (m - 1) for i, opt in enumerate(order)}
    return scores


# --------------------------------------------------------------------------
# Stage 3 — aggregation
# --------------------------------------------------------------------------


def regret_matrix(scores: ScoreMatrix) -> ScoreMatrix:
    """regret(p, o) = best score p could have gotten - score p gets from o."""
    return {
        person: {opt: max(row.values()) - value for opt, value in row.items()}
        for person, row in scores.items()
    }


def _options(scores: ScoreMatrix) -> list[str]:
    if not scores:
        return []
    # Preserve first participant's ordering so output is stable, not set-random.
    first = next(iter(scores.values()))
    return list(first.keys())


def _column(scores: ScoreMatrix, option: str) -> list[float]:
    return [row[option] for row in scores.values()]


def mean_score(scores: ScoreMatrix, option: str) -> float:
    column = _column(scores, option)
    return sum(column) / len(column)


def min_score(scores: ScoreMatrix, option: str) -> float:
    return min(_column(scores, option))


def max_regret(scores: ScoreMatrix, option: str) -> float:
    return max(_column(regret_matrix(scores), option))


def utilitarian(scores: ScoreMatrix) -> list[str]:
    """Maximise the group mean. The obvious rule, and the wrong one.

    Five people mildly preferring something outweighs one person for whom it
    is unusable. The mean cannot tell "everyone is fine" apart from "most are
    delighted and one is excluded". Kept because showing what this rule would
    have picked, and who it would have left out, is a shipped feature.
    """
    return sorted(_options(scores), key=lambda o: (-mean_score(scores, o), o))


def maximin(scores: ScoreMatrix) -> list[str]:
    """Maximise the worst individual score. Overcorrects.

    Optimises against disaster rather than toward a good dinner — this is the
    rule that lands the group at the chain restaurant nobody objected to.
    """
    return sorted(_options(scores), key=lambda o: (-min_score(scores, o), -mean_score(scores, o), o))


def minimax_regret(scores: ScoreMatrix, distances: dict[str, float] | None = None) -> list[str]:
    """Minimise the worst individual regret. The rule Hangry ships.

    Tiebreak chain is explicit — minimax regret, then utilitarian mean, then
    travel distance. Ties are common with small groups and coarse ordinal
    scores, so letting sort order decide would make the winner an accident of
    dict insertion.
    """
    distances = distances or {}
    regrets = regret_matrix(scores)
    return sorted(
        _options(scores),
        key=lambda o: (
            max(row[o] for row in regrets.values()),
            -mean_score(scores, o),
            distances.get(o, 0.0),
            o,
        ),
    )


# --------------------------------------------------------------------------
# Result assembly
# --------------------------------------------------------------------------


@dataclass
class OptionResult:
    option: str
    max_regret: float
    mean: float
    minimum: float
    # Participants who ranked this option dead last. This is what lets the UI
    # say "Jordan wouldn't eat" instead of quoting a regret number at people.
    worst_for: list[str] = field(default_factory=list)


@dataclass
class Decision:
    ranked: list[OptionResult]
    alternates: dict[str, str]
    rule: str = "minimax_regret"

    @property
    def winner(self) -> str:
        return self.ranked[0].option


def decide(scores: ScoreMatrix, distances: dict[str, float] | None = None) -> Decision:
    """Run the shipped rule and record what the other two would have picked."""
    if not scores:
        raise ValueError("cannot decide with no participants")

    order = minimax_regret(scores, distances)
    regrets = regret_matrix(scores)

    ranked = []
    for option in order:
        worst = min(_column(scores, option))
        ranked.append(
            OptionResult(
                option=option,
                max_regret=max(row[option] for row in regrets.values()),
                mean=mean_score(scores, option),
                minimum=worst,
                # Their minimum, not the group's — "this is your last choice".
                worst_for=[p for p, row in scores.items() if abs(row[option] - min(row.values())) < EPS],
            )
        )

    return Decision(
        ranked=ranked,
        alternates={
            "utilitarian": utilitarian(scores)[0],
            "maximin": maximin(scores)[0],
        },
    )


# --------------------------------------------------------------------------
# The six-person fixture from hangry-algorithm.md
# --------------------------------------------------------------------------

# Cardinal scores as written in the doc. These illustrate the argument; the
# live product derives scores ordinally via borda_scores() instead. Both are
# exercised in the test suite, and they do not agree on maximin — see the
# note in api/tests/test_aggregation.py.
DOC_SCORES: ScoreMatrix = {
    "Maazin": {"Mediterranean": 0.65, "Indian": 0.80, "Sushi": 0.90},
    "Ana": {"Mediterranean": 0.70, "Indian": 0.75, "Sushi": 1.00},
    "Sam": {"Mediterranean": 0.65, "Indian": 0.85, "Sushi": 0.90},
    "Priya": {"Mediterranean": 0.70, "Indian": 0.95, "Sushi": 0.80},
    "Jordan": {"Mediterranean": 0.70, "Indian": 0.40, "Sushi": 0.10},
    "Dev": {"Mediterranean": 0.65, "Indian": 0.80, "Sushi": 0.90},
}

# The same six people expressed as rankings, which is what the API collects.
DOC_RANKINGS: dict[str, list[str]] = {
    "Maazin": ["Sushi", "Indian", "Mediterranean"],
    "Ana": ["Sushi", "Indian", "Mediterranean"],
    "Sam": ["Sushi", "Indian", "Mediterranean"],
    "Priya": ["Indian", "Sushi", "Mediterranean"],
    "Jordan": ["Mediterranean", "Indian", "Sushi"],
    "Dev": ["Sushi", "Indian", "Mediterranean"],
}


def _demo() -> None:
    for label, scores in (("cardinal (doc)", DOC_SCORES), ("ordinal (shipped)", borda_scores(DOC_RANKINGS))):
        print(f"\n=== {label} ===")
        print(f"{'option':<16} {'mean':>7} {'min':>7} {'maxregret':>10}")
        for opt in minimax_regret(scores):
            print(
                f"{opt:<16} {mean_score(scores, opt):>7.3f} "
                f"{min_score(scores, opt):>7.3f} {max_regret(scores, opt):>10.3f}"
            )
        print(f"  utilitarian    -> {utilitarian(scores)[0]}")
        print(f"  maximin        -> {maximin(scores)[0]}")
        print(f"  minimax regret -> {minimax_regret(scores)[0]}   <-- shipped")


if __name__ == "__main__":
    _demo()
