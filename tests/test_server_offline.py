"""
Offline integration tests. Runs the real aggregation + Flask routes against canned
fixtures (no network). Run: python3 tests/test_server_offline.py
"""
import os, sys, tempfile

# Configure offline mode + an empty cache dir BEFORE importing the app modules.
os.environ["POKEDEX_OFFLINE"] = "1"
os.environ["POKEDEX_CACHE"] = tempfile.mkdtemp(prefix="pokedex-test-cache-")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pokeapi
import server


def test_full_entry():
    p = pokeapi.get_pokemon("charizard")
    assert p["id"] == 6 and p["display"] == "Charizard"
    assert p["genus"] == "Flame Pokémon"
    assert [t["name"] for t in p["types"]] == ["fire", "flying"]
    assert p["stat_total"] == 534, p["stat_total"]
    assert p["generation_label"] == "Gen I"

    # abilities incl. flagged hidden
    abil = {a["name"]: a for a in p["abilities"]}
    assert abil["blaze"]["hidden"] is False
    assert abil["solar-power"]["hidden"] is True and "Sp. Atk" in abil["solar-power"]["effect"]

    # matchups (decorated with colours)
    weak4 = {i["type"] for i in p["matchups"]["buckets"]["weak_4x"]}
    assert weak4 == {"rock"}
    assert p["matchups"]["buckets"]["immune"][0]["type"] == "ground"
    assert "color" in p["matchups"]["buckets"]["weak_4x"][0]

    # full 18-type defensive grid is exposed for the chart
    mult = p["matchups"]["multipliers"]
    assert len(mult) == 18
    assert mult["rock"] == 4 and mult["ground"] == 0
    assert mult["grass"] == 0.25 and mult["bug"] == 0.25
    assert mult["normal"] == 1  # neutral types present too

    # bio
    assert p["bio"]["weight_kg"] == 90.5 and p["bio"]["height_m"] == 1.7
    assert p["bio"]["gender"]["female"] == 12.5 and p["bio"]["gender"]["male"] == 87.5
    assert p["bio"]["egg_groups"] == ["Monster", "Dragon"]

    # evolution: charmander -> charmeleon (Lv 16) -> charizard (Lv 36)
    evo = p["evolution"]
    assert evo["name"] == "charmander" and evo["trigger"] == ""
    mid = evo["children"][0]
    assert mid["name"] == "charmeleon" and mid["trigger"] == "Level 16"
    assert mid["children"][0]["name"] == "charizard" and mid["children"][0]["trigger"] == "Level 36"

    # forms: mega x / mega y / gmax all detected and categorised
    forms = {f["name"]: f for f in p["forms"]}
    assert forms["charizard-mega-x"]["category"] == "mega"
    assert forms["charizard-mega-y"]["label"] == "Mega Y"
    assert forms["charizard-gmax"]["category"] == "gmax"
    # mega stone item attached + gmax badge (curated mega-stone map)
    assert forms["charizard-mega-x"]["item"]["slug"] == "charizardite-x"
    assert forms["charizard-mega-x"]["item"]["sprite"].endswith("/items/charizardite-x.png")
    assert forms["charizard-gmax"]["badge"] == "Gigantamax"

    # moves grouped & sorted
    lu = p["moves"]["level-up"]
    assert [m["level"] for m in lu] == sorted(m["level"] for m in lu)
    assert lu[0]["display"] == "Ember"  # lowest level
    assert {m["name"] for m in p["moves"]["machine"]} == {"fly", "fire-blast", "dragon-claw"}
    assert p["moves"]["egg"] and p["moves"]["tutor"]

    # graceful empty encounters
    assert p["encounters"] == []
    print("  ok  full Charizard entry (types, stats, abilities, matchups, bio, evo, forms, moves)")


def test_move_detail():
    m = pokeapi.get_move("flamethrower")
    assert m["power"] == 90 and m["category"] == "special" and m["pp"] == 15
    assert "10%" in m["effect"]  # $effect_chance substituted
    print("  ok  lazy move detail (flamethrower 90 BP, 10% burn)")


def test_edge_evolutions():
    # no-evolution species (single node)
    node = pokeapi._evo_node({
        "species": {"name": "tauros", "url": "https://pokeapi.co/api/v2/pokemon-species/128/"},
        "evolution_details": [], "evolves_to": [],
    })
    assert node["children"] == [] and node["display"] == "Tauros"

    # branching evolution (eevee-style): multiple children, item/stone triggers
    branch = pokeapi._evo_node({
        "species": {"name": "eevee", "url": "https://pokeapi.co/api/v2/pokemon-species/133/"},
        "evolution_details": [],
        "evolves_to": [
            {"species": {"name": "vaporeon", "url": ".../pokemon-species/134/"},
             "evolution_details": [{"trigger": {"name": "use-item"}, "item": {"name": "water-stone"}}],
             "evolves_to": []},
            {"species": {"name": "espeon", "url": ".../pokemon-species/196/"},
             "evolution_details": [{"trigger": {"name": "level-up"}, "min_happiness": 220, "time_of_day": "day"}],
             "evolves_to": []},
        ],
    })
    assert len(branch["children"]) == 2
    assert branch["children"][0]["trigger"] == "Use Water Stone"
    assert branch["children"][0]["trigger_item"] == "water-stone"   # item slug for its sprite
    assert "friendship" in branch["children"][1]["trigger"] and "day" in branch["children"][1]["trigger"]
    print("  ok  edge evolutions (no-evo single node + branching item/friendship triggers)")


def test_encounters():
    # Uses fixtures/pokemon__19__encounters.json: one game, one area, two walk slots.
    enc = pokeapi.get_encounters(19)
    assert len(enc) == 1
    g = enc[0]
    assert g["game"] == "Red"
    assert len(g["areas"]) == 1
    a = g["areas"][0]
    assert a["area"] == "Kanto Route 1 Area"
    assert a["methods"] == ["Walk"]
    assert a["min_level"] == 2 and a["max_level"] == 5   # min of mins, max of maxes
    assert a["chance"] == 50                             # best chance across slots
    assert "Time Morning" in a["conditions"]
    print("  ok  encounters parsing (method, level range, conditions, best chance)")


def test_index():
    idx = pokeapi.build_index()
    assert idx["count"] == 3
    assert idx["generations"][0]["label"] == "Gen I"
    assert {m["name"] for m in idx["pokemon"]} == {"charmander", "charmeleon", "charizard"}
    assert idx["pokemon"][0]["artwork"].endswith("/4.png")
    print("  ok  grid index (3 species, Gen I, artwork URLs)")


def test_routes():
    c = server.app.test_client()
    assert c.get("/").status_code == 200
    assert c.get("/api/index").status_code == 200
    r = c.get("/api/pokemon/charizard")
    assert r.status_code == 200 and r.get_json()["id"] == 6
    assert c.get("/api/move/flamethrower").status_code == 200
    # search by number and by typo
    assert any(m["id"] == 6 for m in c.get("/api/search?q=6").get_json())
    assert any(m["name"] == "charizard" for m in c.get("/api/search?q=charizrd").get_json())
    # unknown pokemon -> clean 404, not a crash
    assert c.get("/api/pokemon/notarealmon").status_code == 404
    print("  ok  flask routes (spa, index, pokemon, move, fuzzy search, 404 handling)")


if __name__ == "__main__":
    test_full_entry()
    test_move_detail()
    test_edge_evolutions()
    test_encounters()
    test_index()
    test_routes()
    print("\nALL OFFLINE INTEGRATION TESTS PASSED")
