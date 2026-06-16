"""
Type matchup engine.

Pure functions, no network, easy to unit-test. Given the PokeAPI `damage_relations`
for a Pokemon's type(s), compute the *defensive* multiplier the Pokemon takes from
every attacking type, correctly combining dual types by multiplying the per-type
multipliers.

PokeAPI `/type/{name}` exposes `damage_relations` from the perspective of the type
itself:
    double_damage_from -> attacking types that hit this type for 2x
    half_damage_from   -> attacking types that hit this type for 0.5x
    no_damage_from     -> attacking types that hit this type for 0x
Everything else is 1x. For a Pokemon, the multiplier from attacking type A is the
product over each defending type D of (how much A does to D).
"""

from __future__ import annotations

# Canonical ordering used everywhere in the UI.
TYPES = [
    "normal", "fire", "water", "electric", "grass", "ice",
    "fighting", "poison", "ground", "flying", "psychic", "bug",
    "rock", "ghost", "dragon", "dark", "steel", "fairy",
]


def defensive_multipliers(type_relations):
    """
    type_relations: list of PokeAPI `damage_relations` dicts, one per defending
                    type of the Pokemon (1 for mono-type, 2 for dual-type).

    Returns: dict mapping every attacking type name -> combined multiplier (float).
    """
    combined = {t: 1.0 for t in TYPES}

    for rel in type_relations:
        per_type = {t: 1.0 for t in TYPES}
        for entry in rel.get("double_damage_from", []) or []:
            per_type[entry["name"]] = 2.0
        for entry in rel.get("half_damage_from", []) or []:
            per_type[entry["name"]] = 0.5
        for entry in rel.get("no_damage_from", []) or []:
            per_type[entry["name"]] = 0.0
        for t in TYPES:
            combined[t] *= per_type[t]

    return combined


def categorize(multipliers):
    """
    Bucket a multiplier map into the groups the UI renders. Each bucket is a list
    of {"type": name, "x": multiplier} sorted by descending/ascending severity.
    """
    weak_4x, weak_2x, resist_half, resist_quarter, immune, neutral = [], [], [], [], [], []
    for t in TYPES:
        m = multipliers[t]
        item = {"type": t, "x": m}
        if m == 0:
            immune.append(item)
        elif m >= 4:
            weak_4x.append(item)
        elif m > 1:          # 2x
            weak_2x.append(item)
        elif m <= 0.25:      # 0.25x (or smaller, defensively capped at 0.25)
            resist_quarter.append(item)
        elif m < 1:          # 0.5x
            resist_half.append(item)
        else:
            neutral.append(item)

    return {
        "weak_4x": weak_4x,
        "weak_2x": weak_2x,
        "resist_half": resist_half,
        "resist_quarter": resist_quarter,
        "immune": immune,
        "neutral": neutral,
    }


def compute_matchups(type_relations):
    """Convenience: multipliers + categorized buckets in one call."""
    mults = defensive_multipliers(type_relations)
    return {"multipliers": mults, "buckets": categorize(mults)}
