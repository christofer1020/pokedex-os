"""Generate minimal PokeAPI fixtures for offline tests. Run: python3 tests/_make_fixtures.py"""
import json, os

FX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")
os.makedirs(FX, exist_ok=True)


def w(key, data):
    with open(os.path.join(FX, key.replace("/", "__") + ".json"), "w") as f:
        json.dump(data, f)


def typ(name):
    return {"type": {"name": name, "url": ""}}


def stat(name, val):
    return {"stat": {"name": name, "url": ""}, "base_stat": val}


def mv(name, method, level=0):
    return {"move": {"name": name, "url": ""},
            "version_group_details": [{"move_learn_method": {"name": method}, "level_learned_at": level}]}


# ---- charizard (id 6) ---- #
w("pokemon/charizard", {
    "id": 6, "name": "charizard", "is_default": True, "base_experience": 267,
    "height": 17, "weight": 905,
    "species": {"name": "charizard", "url": "https://pokeapi.co/api/v2/pokemon-species/6/"},
    "types": [typ("fire"), typ("flying")],
    "stats": [stat("hp", 78), stat("attack", 84), stat("defense", 78),
              stat("special-attack", 109), stat("special-defense", 85), stat("speed", 100)],
    "abilities": [
        {"ability": {"name": "blaze", "url": "https://pokeapi.co/api/v2/ability/blaze"}, "is_hidden": False, "slot": 1},
        {"ability": {"name": "solar-power", "url": "https://pokeapi.co/api/v2/ability/solar-power"}, "is_hidden": True, "slot": 3},
    ],
    "held_items": [],
    "cries": {"latest": "https://raw.githubusercontent.com/PokeAPI/cries/main/cries/pokemon/latest/6.ogg"},
    "sprites": {
        "front_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/6.png",
        "front_shiny": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/shiny/6.png",
        "other": {"official-artwork": {
            "front_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/6.png",
            "front_shiny": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/shiny/6.png"}},
    },
    "moves": [
        mv("flamethrower", "level-up", 46), mv("fire-spin", "level-up", 24),
        mv("ember", "level-up", 1), mv("wing-attack", "level-up", 36),
        mv("fly", "machine"), mv("fire-blast", "machine"), mv("dragon-claw", "machine"),
        mv("belly-drum", "egg"), mv("dragon-dance", "egg"),
        mv("fire-punch", "tutor"), mv("outrage", "tutor"),
    ],
})

# encounters: empty -> tests graceful "no wild encounters" state
w("pokemon/6/encounters", [])

w("pokemon-species/6", {
    "id": 6, "name": "charizard", "order": 6, "gender_rate": 1,
    "capture_rate": 45, "base_happiness": 50, "is_legendary": False, "is_mythical": False,
    "growth_rate": {"name": "medium-slow"},
    "generation": {"name": "generation-i", "url": "https://pokeapi.co/api/v2/generation/1/"},
    "egg_groups": [{"name": "monster"}, {"name": "dragon"}],
    "genera": [{"language": {"name": "en"}, "genus": "Flame Pokémon"}],
    "names": [{"language": {"name": "en"}, "name": "Charizard"}],
    "flavor_text_entries": [
        {"language": {"name": "en"}, "version": {"name": "red"},
         "flavor_text": "Spits fire that\nis hot enough to\nmelt boulders."},
        {"language": {"name": "en"}, "version": {"name": "scarlet"},
         "flavor_text": "It flies around the sky\nin search of powerful opponents."},
    ],
    "evolution_chain": {"url": "https://pokeapi.co/api/v2/evolution-chain/2/"},
    "varieties": [
        {"is_default": True, "pokemon": {"name": "charizard", "url": "https://pokeapi.co/api/v2/pokemon/6/"}},
        {"is_default": False, "pokemon": {"name": "charizard-mega-x", "url": "https://pokeapi.co/api/v2/pokemon/10034/"}},
        {"is_default": False, "pokemon": {"name": "charizard-mega-y", "url": "https://pokeapi.co/api/v2/pokemon/10035/"}},
        {"is_default": False, "pokemon": {"name": "charizard-gmax", "url": "https://pokeapi.co/api/v2/pokemon/10196/"}},
    ],
})

w("evolution-chain/2", {"chain": {
    "species": {"name": "charmander", "url": "https://pokeapi.co/api/v2/pokemon-species/4/"},
    "evolution_details": [],
    "evolves_to": [{
        "species": {"name": "charmeleon", "url": "https://pokeapi.co/api/v2/pokemon-species/5/"},
        "evolution_details": [{"trigger": {"name": "level-up"}, "min_level": 16}],
        "evolves_to": [{
            "species": {"name": "charizard", "url": "https://pokeapi.co/api/v2/pokemon-species/6/"},
            "evolution_details": [{"trigger": {"name": "level-up"}, "min_level": 36}],
            "evolves_to": [],
        }],
    }],
}})

w("type/fire", {"damage_relations": {
    "double_damage_from": [{"name": "water"}, {"name": "ground"}, {"name": "rock"}],
    "half_damage_from": [{"name": "fire"}, {"name": "grass"}, {"name": "ice"}, {"name": "bug"}, {"name": "steel"}, {"name": "fairy"}],
    "no_damage_from": []}})
w("type/flying", {"damage_relations": {
    "double_damage_from": [{"name": "electric"}, {"name": "ice"}, {"name": "rock"}],
    "half_damage_from": [{"name": "grass"}, {"name": "fighting"}, {"name": "bug"}],
    "no_damage_from": [{"name": "ground"}]}})

w("ability/blaze", {"name": "blaze", "effect_entries": [
    {"language": {"name": "en"}, "short_effect": "Powers up Fire-type moves when the Pokémon's HP is low."}]})
w("ability/solar-power", {"name": "solar-power", "effect_entries": [
    {"language": {"name": "en"}, "short_effect": "Boosts Sp. Atk in harsh sunlight, but costs HP each turn."}]})

# move details (lazy tab)
w("move/flamethrower", {"name": "flamethrower", "type": {"name": "fire"}, "damage_class": {"name": "special"},
                        "power": 90, "accuracy": 100, "pp": 15, "effect_chance": 10,
                        "effect_entries": [{"language": {"name": "en"}, "short_effect": "Has a $effect_chance% chance to burn the target."}]})

# ---- tiny index ---- #
w("pokedex/national", {"pokemon_entries": [
    {"entry_number": 4, "pokemon_species": {"name": "charmander", "url": "https://pokeapi.co/api/v2/pokemon-species/4/"}},
    {"entry_number": 5, "pokemon_species": {"name": "charmeleon", "url": "https://pokeapi.co/api/v2/pokemon-species/5/"}},
    {"entry_number": 6, "pokemon_species": {"name": "charizard", "url": "https://pokeapi.co/api/v2/pokemon-species/6/"}},
]})
w("generation/1", {"pokemon_species": [{"name": "charmander"}, {"name": "charmeleon"}, {"name": "charizard"}]})

print("fixtures written to", FX)
print(sorted(os.listdir(FX)))
