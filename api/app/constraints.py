"""The constraint vocabulary, and what the data can and cannot answer.

The one invariant with real-world consequences: **missing dietary data is
never treated as satisfied**. Everything in this module exists to keep that
true at the type level rather than by remembering to check.
"""

from __future__ import annotations

from enum import StrEnum

# Our constraint key -> the OSM tag that answers it.
# These are the only dietary questions OpenStreetMap has a schema for.
FILTERABLE_DIETS: dict[str, str] = {
    "vegetarian": "diet:vegetarian",
    "vegan": "diet:vegan",
    "gluten_free": "diet:gluten_free",
    "halal": "diet:halal",
    "kosher": "diet:kosher",
}

# OSM has no allergen tagging at all — not sparse, absent. Routing these
# through the unverified tier would tip every candidate into it and destroy
# the signal the tier carries, so they become a standing advisory shown on
# every candidate and on the result instead. That is still never "safe":
# it says the data cannot answer, and names who needs to ask.
ADVISORY_DIETS: dict[str, str] = {
    "nut_allergy": "nut allergy",
    "shellfish_allergy": "shellfish allergy",
}

ALL_DIETS = list(FILTERABLE_DIETS) + list(ADVISORY_DIETS)

HUMAN_LABELS: dict[str, str] = {
    "vegetarian": "vegetarian",
    "vegan": "vegan",
    "gluten_free": "gluten-free",
    "halal": "halal",
    "kosher": "kosher",
    "nut_allergy": "nut allergy",
    "shellfish_allergy": "shellfish allergy",
    "max_distance_m": "travel distance",
    "max_price_tier": "price",
    "open_now": "open now",
}


class Status(StrEnum):
    """Three states, and the middle one is the entire product.

    A boolean here is the bug: it forces UNKNOWN to collapse into one of the
    other two, and whichever way it collapses is wrong.
    """

    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNKNOWN = "unknown"


def diet_status(diet_flags: dict[str, str | None], constraint: str) -> Status:
    """Evaluate one dietary constraint against a place's OSM diet flags.

    Values follow OSM's `diet:*` vocabulary:
      yes / only  -> satisfied
      no          -> violated
      limited     -> UNKNOWN. "Limited options" is not a confident yes, and
                     this is exactly the case where guessing hurts someone.
      absent/null -> UNKNOWN
    """
    if constraint not in FILTERABLE_DIETS:
        # Anything we cannot filter on is unknown by construction. Callers
        # must never read this as satisfied.
        return Status.UNKNOWN

    raw = diet_flags.get(constraint)

    # A vegan kitchen satisfies a vegetarian, but not the reverse.
    if constraint == "vegetarian" and raw not in ("yes", "only", "no"):
        vegan = diet_flags.get("vegan")
        if vegan in ("yes", "only"):
            return Status.SATISFIED

    if raw in ("yes", "only"):
        return Status.SATISFIED
    if raw == "no":
        return Status.VIOLATED
    return Status.UNKNOWN
