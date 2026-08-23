"""Stage 3, aggregation, ported from the canonical `aggregate.py` at the
repo root.

The core math below is a direct port and must stay logically identical to the
canonical module. `tests/test_aggregation.py` asserts the two agree on the
six-person fixture; if you change one, that test fails until you change both.
Everything under "API glue" is additive and has no counterpart upstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# person -> option -> score in [0, 1]
ScoreMatrix = dict[str, dict[str, float]]

EPS = 1e-9


# --------------------------------------------------------------------------
# Core math, keep in lockstep with aggregate.py
# --------------------------------------------------------------------------


def borda_scores(rankings: dict[str, list[str]]) -> ScoreMatrix:
    """score = (m - rank) / (m - 1), rank 1-indexed. Best 1.0, worst 0.0."""
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
        scores[person] = {opt: 1.0 if m == 1 else (m - 1 - i) / (m - 1) for i, opt in enumerate(order)}
    return scores


def regret_matrix(scores: ScoreMatrix) -> ScoreMatrix:
    """regret(p, o) = best p could have gotten - what o gives them."""
    return {
        person: {opt: max(row.values()) - value for opt, value in row.items()}
        for person, row in scores.items()
    }


def _options(scores: ScoreMatrix) -> list[str]:
    if not scores:
        return []
    return list(next(iter(scores.values())).keys())


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
    """Maximise the mean. Kept because showing what it would have picked, and
    who it would have excluded, is a shipped feature."""
    return sorted(_options(scores), key=lambda o: (-mean_score(scores, o), o))


def maximin(scores: ScoreMatrix) -> list[str]:
    """Maximise the worst individual score. Overcorrects toward the chain
    restaurant nobody objected to."""
    return sorted(_options(scores), key=lambda o: (-min_score(scores, o), -mean_score(scores, o), o))


def minimax_regret(scores: ScoreMatrix, distances: dict[str, float] | None = None) -> list[str]:
    """The shipped rule. Tiebreak chain is explicit: regret, mean, distance."""
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


@dataclass
class OptionResult:
    option: str
    max_regret: float
    mean: float
    minimum: float
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
    if not scores:
        raise ValueError("cannot decide with no participants")

    order = minimax_regret(scores, distances)
    regrets = regret_matrix(scores)

    ranked = []
    for option in order:
        ranked.append(
            OptionResult(
                option=option,
                max_regret=max(row[option] for row in regrets.values()),
                mean=mean_score(scores, option),
                minimum=min(_column(scores, option)),
                worst_for=[p for p, row in scores.items() if abs(row[option] - min(row.values())) < EPS],
            )
        )

    return Decision(
        ranked=ranked,
        alternates={"utilitarian": utilitarian(scores)[0], "maximin": maximin(scores)[0]},
    )


# --------------------------------------------------------------------------
# API glue, no counterpart in aggregate.py
# --------------------------------------------------------------------------


def _plural(n: int) -> str:
    if n == 0:
        return "Nobody"
    return "1 of you" if n == 1 else f"{n} of you"


def _names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def annotate(decision: Decision, scores: ScoreMatrix) -> list[dict]:
    """Turn the numbers into the sentences the shortlist actually renders.

    The runner-up annotations are the whole point of showing runners-up: a
    bare ranked list recreates the paralysis the product exists to end, so
    every option below #1 has to say what it costs and who it costs.
    """
    people = len(scores)
    util_pick = decision.alternates["utilitarian"]
    maximin_pick = decision.alternates["maximin"]

    out = []
    for index, result in enumerate(decision.ranked):
        option = result.option
        firsts = [p for p, row in scores.items() if abs(row[option] - max(row.values())) < EPS]
        lasts = result.worst_for

        if index == 0:
            note = "Best balance. Nobody gives up much to be here."
            if option == util_pick:
                note = "Best balance, and the group favourite. No tradeoff to make."
            elif lasts and people > 1:
                note = f"Best balance. {_names(lasts)} ranked it last, but nothing else costs anyone more."
        elif option == util_pick:
            note = f"{_plural(len(firsts))} would love it"
            note += f", but {_names(lasts)} wouldn't eat." if lasts else "."
            note += " This is what a majority vote picks."
        elif option == maximin_pick:
            note = "Safest option. Nobody's worst choice"
            note += f", but only {_plural(len(firsts))} put it first." if firsts else "."
        elif lasts:
            note = f"{_names(lasts)} ranked it last."
        elif firsts:
            note = f"{_plural(len(firsts))} put it first."
        else:
            note = "Nobody's first choice, nobody's last."

        out.append(
            {
                "option": option,
                "max_regret": round(result.max_regret, 4),
                "mean": round(result.mean, 4),
                "minimum": round(result.minimum, 4),
                "worst_for": lasts,
                "best_for": firsts,
                "annotation": note,
            }
        )
    return out


def comparison(decision: Decision, scores: ScoreMatrix) -> dict:
    """What the other two rules would have picked, and who pays for it.

    This is the shareable insight, the launch content, and the interview
    story, all falling out of the same code.
    """
    util_pick = decision.alternates["utilitarian"]
    maximin_pick = decision.alternates["maximin"]
    util_result = next(r for r in decision.ranked if r.option == util_pick)

    excluded = util_result.worst_for
    if util_pick == decision.winner:
        headline = "The fair answer and the popular answer agree this time."
    elif excluded:
        headline = f"A majority vote picks {util_pick}, and {_names(excluded)} wouldn't eat."
    else:
        headline = f"A majority vote picks {util_pick}."

    return {
        "headline": headline,
        "utilitarian": {"option": util_pick, "excludes": excluded, "mean": round(mean_score(scores, util_pick), 4)},
        "maximin": {"option": maximin_pick, "minimum": round(min_score(scores, maximin_pick), 4)},
        "minimax_regret": {"option": decision.winner, "max_regret": round(decision.ranked[0].max_regret, 4)},
    }
