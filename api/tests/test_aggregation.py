"""The correctness core.

This is the file that matters. It is what gets asked about in interviews and
the thing most likely to silently break during a refactor, so it pins the
worked numbers from `hangry-algorithm.md` rather than just the winner.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

from app.aggregation import (
    Decision,
    annotate,
    borda_scores,
    comparison,
    decide,
    max_regret,
    maximin,
    mean_score,
    min_score,
    minimax_regret,
    regret_matrix,
    utilitarian,
)

# The canonical module lives at the repo root, outside the api package.
_CANONICAL = Path(__file__).resolve().parents[2] / "aggregate.py"
_spec = importlib.util.spec_from_file_location("canonical_aggregate", _CANONICAL)
canonical = importlib.util.module_from_spec(_spec)
sys.modules["canonical_aggregate"] = canonical
_spec.loader.exec_module(canonical)


# --------------------------------------------------------------------------
# Standing rule 1: aggregate.py is canonical
# --------------------------------------------------------------------------


def test_api_module_matches_canonical_on_the_fixture():
    """`api/app/aggregation.py` must not drift from `aggregate.py`.

    Both directions of the pipeline are checked: the cardinal scores as the
    doc writes them, and the ordinal path the live product actually uses.
    """
    for scores in (canonical.DOC_SCORES, canonical.borda_scores(canonical.DOC_RANKINGS)):
        assert minimax_regret(scores) == canonical.minimax_regret(scores)
        assert utilitarian(scores) == canonical.utilitarian(scores)
        assert maximin(scores) == canonical.maximin(scores)
        assert regret_matrix(scores) == canonical.regret_matrix(scores)

        mine, theirs = decide(scores), canonical.decide(scores)
        assert mine.winner == theirs.winner
        assert mine.alternates == theirs.alternates
        assert [(r.option, r.max_regret, r.mean, r.minimum, r.worst_for) for r in mine.ranked] == [
            (r.option, r.max_regret, r.mean, r.minimum, r.worst_for) for r in theirs.ranked
        ]


def test_borda_conversion_matches_canonical():
    assert borda_scores(canonical.DOC_RANKINGS) == canonical.borda_scores(canonical.DOC_RANKINGS)


# --------------------------------------------------------------------------
# The six-person fixture, cardinal scores exactly as the doc writes them
# --------------------------------------------------------------------------


@pytest.fixture
def doc_scores():
    return canonical.DOC_SCORES


def test_all_three_rules_pick_different_restaurants(doc_scores):
    """The divergence is the product. If these ever agree on this fixture,
    the fixture stopped demonstrating anything."""
    assert utilitarian(doc_scores)[0] == "Sushi"
    assert maximin(doc_scores)[0] == "Mediterranean"
    assert minimax_regret(doc_scores)[0] == "Indian"


def test_utilitarian_means_match_the_doc(doc_scores):
    assert mean_score(doc_scores, "Mediterranean") == pytest.approx(0.675)
    assert mean_score(doc_scores, "Indian") == pytest.approx(0.758, abs=0.001)
    assert mean_score(doc_scores, "Sushi") == pytest.approx(0.767, abs=0.001)


def test_maximin_minimums_match_the_doc(doc_scores):
    assert min_score(doc_scores, "Mediterranean") == pytest.approx(0.65)
    assert min_score(doc_scores, "Indian") == pytest.approx(0.40)
    assert min_score(doc_scores, "Sushi") == pytest.approx(0.10)


def test_regret_table_matches_the_doc(doc_scores):
    """Every cell of the regret table in hangry-algorithm.md."""
    expected = {
        "Maazin": {"Mediterranean": 0.25, "Indian": 0.10, "Sushi": 0.00},
        "Ana": {"Mediterranean": 0.30, "Indian": 0.25, "Sushi": 0.00},
        "Sam": {"Mediterranean": 0.25, "Indian": 0.05, "Sushi": 0.00},
        "Priya": {"Mediterranean": 0.25, "Indian": 0.00, "Sushi": 0.15},
        "Jordan": {"Mediterranean": 0.00, "Indian": 0.30, "Sushi": 0.60},
        "Dev": {"Mediterranean": 0.25, "Indian": 0.10, "Sushi": 0.00},
    }
    actual = regret_matrix(doc_scores)
    for person, row in expected.items():
        for option, value in row.items():
            assert actual[person][option] == pytest.approx(value), f"{person}/{option}"


def test_max_regrets_match_the_doc(doc_scores):
    assert max_regret(doc_scores, "Mediterranean") == pytest.approx(0.30)
    assert max_regret(doc_scores, "Indian") == pytest.approx(0.30)
    # Sushi costs Jordan twice the worst case of either alternative.
    assert max_regret(doc_scores, "Sushi") == pytest.approx(0.60)


def test_mediterranean_and_indian_tie_and_mean_breaks_it(doc_scores):
    """The doc's stated tiebreak: equal max regret, resolved by mean."""
    assert max_regret(doc_scores, "Mediterranean") == pytest.approx(max_regret(doc_scores, "Indian"))
    assert mean_score(doc_scores, "Indian") > mean_score(doc_scores, "Mediterranean")
    assert minimax_regret(doc_scores)[0] == "Indian"


def test_jordan_is_named_as_who_sushi_excludes(doc_scores):
    decision = decide(doc_scores)
    sushi = next(r for r in decision.ranked if r.option == "Sushi")
    assert sushi.worst_for == ["Jordan"]

    compare = comparison(decision, doc_scores)
    assert compare["utilitarian"]["option"] == "Sushi"
    assert compare["utilitarian"]["excludes"] == ["Jordan"]
    assert "Jordan" in compare["headline"]


# --------------------------------------------------------------------------
# The ordinal pipeline the product actually ships
# --------------------------------------------------------------------------


def test_ordinal_pipeline_still_picks_indian():
    """Phase 3 DoD, at the unit level.

    Note the divergence from the cardinal table: under Borda, maximin also
    picks Indian rather than Mediterranean. Ordinal input cannot express that
    Mediterranean is mildly acceptable to everyone, so the "safe mediocre
    option" that maximin exists to find is invisible to it. Minimax regret and
    utilitarian are unaffected, which is why the shipped rule is unchanged.
    """
    scores = borda_scores(canonical.DOC_RANKINGS)
    assert minimax_regret(scores)[0] == "Indian"
    assert utilitarian(scores)[0] == "Sushi"
    assert maximin(scores)[0] == "Indian"


def test_borda_endpoints_and_spacing():
    scores = borda_scores({"A": ["x", "y", "z"]})
    assert scores["A"] == {"x": 1.0, "y": 0.5, "z": 0.0}


def test_borda_rejects_ragged_and_duplicate_rankings():
    with pytest.raises(ValueError, match="different numbers"):
        borda_scores({"A": ["x", "y"], "B": ["x"]})
    with pytest.raises(ValueError, match="duplicates"):
        borda_scores({"A": ["x", "x"]})


# --------------------------------------------------------------------------
# Tiebreak chain: regret -> mean -> distance
# --------------------------------------------------------------------------


def test_mean_breaks_a_regret_tie():
    scores = {
        "A": {"X": 1.0, "Y": 0.5},
        "B": {"X": 0.5, "Y": 1.0},
        "C": {"X": 1.0, "Y": 0.6},
    }
    assert max_regret(scores, "X") == pytest.approx(max_regret(scores, "Y"))
    assert minimax_regret(scores)[0] == "X"


def test_distance_breaks_a_regret_and_mean_tie():
    scores = {"A": {"X": 1.0, "Y": 0.0}, "B": {"X": 0.0, "Y": 1.0}}
    assert max_regret(scores, "X") == pytest.approx(max_regret(scores, "Y"))
    assert mean_score(scores, "X") == pytest.approx(mean_score(scores, "Y"))
    assert minimax_regret(scores, {"X": 4000.0, "Y": 900.0})[0] == "Y"
    assert minimax_regret(scores, {"X": 900.0, "Y": 4000.0})[0] == "X"


def test_tiebreak_is_deterministic_without_distances():
    """Ties are common with small groups and coarse ordinal scores, so the
    winner must not be an accident of dict insertion order."""
    scores = {"A": {"X": 1.0, "Y": 0.0}, "B": {"X": 0.0, "Y": 1.0}}
    reversed_scores = {"B": {"Y": 1.0, "X": 0.0}, "A": {"Y": 0.0, "X": 1.0}}
    assert minimax_regret(scores)[0] == minimax_regret(reversed_scores)[0]


# --------------------------------------------------------------------------
# Degenerate cases, where off-by-one bugs live
# --------------------------------------------------------------------------


def test_single_participant_collapses_all_three_rules():
    scores = borda_scores({"Solo": ["b", "a", "c"]})
    assert utilitarian(scores)[0] == maximin(scores)[0] == minimax_regret(scores)[0] == "b"


def test_single_option_scores_one_and_has_no_regret():
    scores = borda_scores({"A": ["only"], "B": ["only"]})
    assert scores == {"A": {"only": 1.0}, "B": {"only": 1.0}}
    decision = decide(scores)
    assert decision.winner == "only"
    assert decision.ranked[0].max_regret == 0.0


def test_identical_scores_collapse_all_three_rules():
    scores = {"A": {"X": 0.5, "Y": 0.5}, "B": {"X": 0.5, "Y": 0.5}}
    assert utilitarian(scores)[0] == maximin(scores)[0] == minimax_regret(scores)[0]
    assert decide(scores).ranked[0].max_regret == 0.0


def test_unanimous_group_has_no_tradeoff_to_annotate():
    scores = borda_scores({"A": ["x", "y"], "B": ["x", "y"]})
    decision = decide(scores)
    assert decision.winner == "x"
    assert comparison(decision, scores)["headline"] == "The fair answer and the popular answer agree this time."


def test_decide_refuses_an_empty_group():
    with pytest.raises(ValueError, match="no participants"):
        decide({})


def test_annotations_name_people_not_numbers():
    """The runner-up lines are the reason runners-up are shown at all."""
    scores = borda_scores(canonical.DOC_RANKINGS)
    rows = annotate(decide(scores), scores)

    assert rows[0]["option"] == "Indian"
    sushi = next(r for r in rows if r["option"] == "Sushi")
    assert "Jordan" in sushi["annotation"]
    assert "majority vote" in sushi["annotation"]
    assert sushi["worst_for"] == ["Jordan"]


def test_regret_is_measured_against_what_was_achievable():
    """The property that makes the output feel fair rather than arbitrary.

    Jordan's real favourite being unavailable does not entitle him to
    compensation, regret is scored against the feasible set, so removing his
    unavailable favourite from the matrix changes nothing about the winner.
    """
    scores = borda_scores(canonical.DOC_RANKINGS)
    assert all(min(row.values()) == 0.0 and max(row.values()) == 1.0 for row in scores.values())
    assert decide(scores).winner == "Indian"
