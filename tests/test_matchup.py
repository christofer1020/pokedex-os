"""Pure-logic tests for the type matchup engine. Run: python3 tests/test_matchup.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matchup


def rel(double=(), half=(), none=()):
    return {
        "double_damage_from": [{"name": n} for n in double],
        "half_damage_from": [{"name": n} for n in half],
        "no_damage_from": [{"name": n} for n in none],
    }


# Defensive damage relations straight from the canonical Gen-9 chart.
FIRE = rel(double=("water", "ground", "rock"),
           half=("fire", "grass", "ice", "bug", "steel", "fairy"))
FLYING = rel(double=("electric", "ice", "rock"),
             half=("grass", "fighting", "bug"),
             none=("ground",))
NORMAL = rel(double=("fighting",), none=("ghost",))
GHOST = rel(double=("ghost", "dark"), half=("poison", "bug"), none=("normal", "fighting"))


def names(bucket):
    return {i["type"] for i in bucket}


def test_charizard():
    r = matchup.compute_matchups([FIRE, FLYING])
    m, b = r["multipliers"], r["buckets"]
    assert m["rock"] == 4, m["rock"]                      # the brief's required check
    assert m["water"] == 2 and m["electric"] == 2
    assert m["ground"] == 0                               # flying immunity wins
    assert m["grass"] == 0.25 and m["bug"] == 0.25        # both types resist -> 0.25
    assert m["fire"] == 0.5 and m["fighting"] == 0.5
    assert m["ice"] == 1                                  # 0.5 * 2 cancels to neutral
    assert names(b["weak_4x"]) == {"rock"}
    assert names(b["weak_2x"]) == {"water", "electric"}
    assert names(b["resist_quarter"]) == {"grass", "bug"}
    assert names(b["immune"]) == {"ground"}
    print("  ok  charizard (fire/flying): 4x rock, 0x ground, 0.25x grass/bug")


def test_mono_immunities():
    r = matchup.compute_matchups([NORMAL])
    assert r["multipliers"]["ghost"] == 0 and r["multipliers"]["fighting"] == 2
    r = matchup.compute_matchups([GHOST])
    assert r["multipliers"]["normal"] == 0 and r["multipliers"]["fighting"] == 0
    print("  ok  mono-type immunities (normal vs ghost, ghost vs normal/fighting)")


def test_no_types():
    r = matchup.compute_matchups([])
    assert all(v == 1 for v in r["multipliers"].values())
    print("  ok  empty type list degrades to all-neutral")


if __name__ == "__main__":
    test_charizard()
    test_mono_immunities()
    test_no_types()
    print("\nALL MATCHUP TESTS PASSED")
