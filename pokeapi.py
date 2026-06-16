"""
High-level PokeAPI aggregation.

Turns the many small PokeAPI resources into a few rich, UI-ready payloads:
  build_index()          -> every species for the browsable grid (cheap: ~10 calls)
  get_pokemon(key)       -> one complete entry (types, stats, flavor, evolution tree,
                            forms/megas/gmax, abilities, bio, encounters, matchups)
  get_cards(ids)         -> lazy type chips for grid cards
  get_move(name)         -> lazy move details for the moves tab

Everything is wrapped so a single missing/odd sub-resource degrades gracefully
instead of breaking the whole entry.
"""

from __future__ import annotations

import re

from cache import fetch_json, fetch_many
import matchup

SPRITES = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"

# Pokemon type colours (the subject's own vernacular -- kept from the reference app).
TYPE_COLORS = {
    "normal": "#9099A1", "fire": "#FF6242", "water": "#4D90D5", "electric": "#F3D23B",
    "grass": "#63BB5B", "ice": "#74CEC0", "fighting": "#CE4069", "poison": "#AB6AC8",
    "ground": "#D97746", "flying": "#8FA9DE", "psychic": "#F97176", "bug": "#90C12C",
    "rock": "#C7B78B", "ghost": "#5269AC", "dragon": "#0B6DC3", "dark": "#5A5366",
    "steel": "#5A8EA1", "fairy": "#EC8FE6",
}

STAT_LABELS = {
    "hp": "HP", "attack": "Attack", "defense": "Defense",
    "special-attack": "Sp. Atk", "special-defense": "Sp. Def", "speed": "Speed",
}

ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII", 9: "IX"}


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def id_from_url(url):
    m = re.search(r"/(\d+)/?$", url or "")
    return int(m.group(1)) if m else None


def pretty(name):
    return (name or "").replace("-", " ").title()


def artwork_url(poke_id):
    return f"{SPRITES}/other/official-artwork/{poke_id}.png"


def artwork_shiny_url(poke_id):
    return f"{SPRITES}/other/official-artwork/shiny/{poke_id}.png"


ITEMS_SPRITES = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items"


def item_sprite(slug):
    return f"{ITEMS_SPRITES}/{slug}.png"


# Mega Evolution / Primal Reversion -> the held stone/orb item (PokeAPI item slug).
# PokeAPI does NOT link a Mega form to its stone, so this is a small curated map of
# canonical, well-known data. Anything not listed simply shows no stone (just the badge).
MEGA_STONES = {
    "venusaur-mega": "venusaurite", "charizard-mega-x": "charizardite-x",
    "charizard-mega-y": "charizardite-y", "blastoise-mega": "blastoisinite",
    "alakazam-mega": "alakazite", "gengar-mega": "gengarite",
    "kangaskhan-mega": "kangaskhanite", "pinsir-mega": "pinsirite",
    "gyarados-mega": "gyaradosite", "aerodactyl-mega": "aerodactylite",
    "mewtwo-mega-x": "mewtwonite-x", "mewtwo-mega-y": "mewtwonite-y",
    "ampharos-mega": "ampharosite", "steelix-mega": "steelixite",
    "scizor-mega": "scizorite", "heracross-mega": "heracronite",
    "houndoom-mega": "houndoominite", "tyranitar-mega": "tyranitarite",
    "sceptile-mega": "sceptilite", "blaziken-mega": "blazikenite",
    "swampert-mega": "swampertite", "gardevoir-mega": "gardevoirite",
    "sableye-mega": "sablenite", "mawile-mega": "mawilite",
    "aggron-mega": "aggronite", "medicham-mega": "medichamite",
    "manectric-mega": "manectite", "sharpedo-mega": "sharpedonite",
    "camerupt-mega": "cameruptite", "altaria-mega": "altarianite",
    "banette-mega": "banettite", "absol-mega": "absolite",
    "glalie-mega": "glalitite", "salamence-mega": "salamencite",
    "metagross-mega": "metagrossite", "latias-mega": "latiasite",
    "latios-mega": "latiosite", "lopunny-mega": "lopunnite",
    "garchomp-mega": "garchompite", "lucario-mega": "lucarionite",
    "abomasnow-mega": "abomasite", "gallade-mega": "galladite",
    "audino-mega": "audinite", "diancie-mega": "diancite",
    "beedrill-mega": "beedrillite", "pidgeot-mega": "pidgeotite",
    "slowbro-mega": "slowbronite", "groudon-primal": "red-orb",
    "kyogre-primal": "blue-orb",
}


def best_artwork(poke):
    other = (poke.get("sprites") or {}).get("other") or {}
    oa = (other.get("official-artwork") or {})
    home = (other.get("home") or {})
    front = (poke.get("sprites") or {}).get("front_default")
    return {
        "artwork": oa.get("front_default") or home.get("front_default") or front or artwork_url(poke["id"]),
        "artwork_shiny": oa.get("front_shiny") or home.get("front_shiny") or (poke.get("sprites") or {}).get("front_shiny") or artwork_shiny_url(poke["id"]),
        "sprite": front or f"{SPRITES}/{poke['id']}.png",
        "sprite_shiny": (poke.get("sprites") or {}).get("front_shiny") or f"{SPRITES}/shiny/{poke['id']}.png",
    }


def english_flavor(species):
    seen, out = set(), []
    for entry in reversed(species.get("flavor_text_entries", []) or []):  # newest first
        if entry["language"]["name"] != "en":
            continue
        text = entry["flavor_text"].replace("\n", " ").replace("\f", " ").replace("\u00ad", "").strip()
        text = re.sub(r"\s+", " ", text)
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append({"text": text, "version": pretty(entry["version"]["name"])})
    return out


def english_genus(species):
    for g in species.get("genera", []) or []:
        if g["language"]["name"] == "en":
            return g["genus"]
    return ""


def english_name(species, fallback):
    for n in species.get("names", []) or []:
        if n["language"]["name"] == "en":
            return n["name"]
    return pretty(fallback)


# --------------------------------------------------------------------------- #
# evolution
# --------------------------------------------------------------------------- #
def _evo_trigger_text(details):
    if not details:
        return ""
    d = details[0]
    trig = (d.get("trigger") or {}).get("name", "")
    parts = []
    if d.get("min_level"):
        parts.append(f"Level {d['min_level']}")
    elif trig == "trade":
        s = "Trade"
        if d.get("trade_species"):
            s += f" for {pretty(d['trade_species']['name'])}"
        if d.get("held_item"):
            s += f" holding {pretty(d['held_item']['name'])}"
        parts.append(s)
    elif d.get("item"):
        parts.append(f"Use {pretty(d['item']['name'])}")
    elif trig == "level-up":
        parts.append("Level up")
    elif trig:
        parts.append(pretty(trig))

    if d.get("held_item") and trig != "trade":
        parts.append(f"holding {pretty(d['held_item']['name'])}")
    if d.get("min_happiness"):
        parts.append("high friendship")
    if d.get("min_affection"):
        parts.append("high affection")
    if d.get("known_move"):
        parts.append(f"knowing {pretty(d['known_move']['name'])}")
    if d.get("known_move_type"):
        parts.append(f"knowing a {pretty(d['known_move_type']['name'])} move")
    if d.get("location"):
        parts.append(f"at {pretty(d['location']['name'])}")
    if d.get("time_of_day"):
        parts.append(f"({d['time_of_day']})")
    if d.get("gender") in (1, 2):
        parts.append("(♀)" if d["gender"] == 1 else "(♂)")
    if d.get("needs_overworld_rain"):
        parts.append("in rain")
    if d.get("turn_upside_down"):
        parts.append("(console upside down)")
    return " ".join(parts) if parts else "Special"


def _evo_trigger_item(details):
    """The item slug involved in this evolution step (use-item or held item), if any."""
    if not details:
        return None
    d = details[0]
    it = d.get("item") or d.get("held_item")
    return it["name"] if it else None


def _evo_node(chain):
    pid = id_from_url(chain["species"]["url"])
    return {
        "id": pid,
        "name": chain["species"]["name"],
        "display": pretty(chain["species"]["name"]),
        "artwork": artwork_url(pid),
        "sprite": f"{SPRITES}/{pid}.png",
        "trigger": _evo_trigger_text(chain.get("evolution_details")),
        "trigger_item": _evo_trigger_item(chain.get("evolution_details")),
        "children": [_evo_node(c) for c in chain.get("evolves_to", [])],
    }


def get_evolution(species):
    url = (species.get("evolution_chain") or {}).get("url")
    if not url:
        return None
    data = fetch_json(url, optional=True)
    if not data:
        return None
    return _evo_node(data["chain"])


# --------------------------------------------------------------------------- #
# forms / megas / gmax
# --------------------------------------------------------------------------- #
FORM_RULES = [
    ("-mega-x", "mega", "Mega X"),
    ("-mega-y", "mega", "Mega Y"),
    ("-mega", "mega", "Mega"),
    ("-gmax", "gmax", "Gigantamax"),
    ("-alola", "regional", "Alolan"),
    ("-galar", "regional", "Galarian"),
    ("-hisui", "regional", "Hisuian"),
    ("-paldea", "regional", "Paldean"),
    ("-primal", "mega", "Primal"),
    ("-totem", "alt", "Totem"),
]


def classify_form(name, default_name):
    if name == default_name:
        return ("base", "Base Form")
    for token, cat, label in FORM_RULES:
        if token in name:
            return (cat, label)
    return ("alt", pretty(name).replace(pretty(default_name), "").strip() or pretty(name))


def get_forms(species, default_name):
    forms = []
    for v in species.get("varieties", []) or []:
        name = v["pokemon"]["name"]
        pid = id_from_url(v["pokemon"]["url"])
        cat, label = classify_form(name, default_name)
        form = {
            "name": name,
            "id": pid,
            "label": label if name != default_name else "Base Form",
            "category": cat,
            "is_default": bool(v.get("is_default")),
            "artwork": artwork_url(pid),
            "sprite": f"{SPRITES}/{pid}.png",
        }
        stone = MEGA_STONES.get(name)
        if stone:
            form["item"] = {"slug": stone, "display": pretty(stone), "sprite": item_sprite(stone)}
        if cat == "gmax":
            form["badge"] = "Gigantamax"
        forms.append(form)
    return forms


# --------------------------------------------------------------------------- #
# abilities / matchups / bio / moves / encounters
# --------------------------------------------------------------------------- #
def get_abilities(poke):
    refs = poke.get("abilities", []) or []
    detail = fetch_many([f"ability/{a['ability']['name']}" for a in refs], optional=True)
    out = []
    for a in refs:
        d = detail.get(f"ability/{a['ability']['name']}")
        effect = ""
        if d:
            for e in d.get("effect_entries", []) or []:
                if e["language"]["name"] == "en":
                    effect = (e.get("short_effect") or e.get("effect") or "").strip()
                    break
            if not effect:
                for e in d.get("flavor_text_entries", []) or []:
                    if e["language"]["name"] == "en":
                        effect = e["flavor_text"].replace("\n", " ").strip()
                        break
        out.append({
            "name": a["ability"]["name"],
            "display": pretty(a["ability"]["name"]),
            "hidden": bool(a.get("is_hidden")),
            "effect": effect or "No description available.",
        })
    return out


def get_matchups(poke):
    type_names = [t["type"]["name"] for t in poke.get("types", []) or []]
    rels = []
    detail = fetch_many([f"type/{t}" for t in type_names], optional=True)
    for t in type_names:
        d = detail.get(f"type/{t}")
        if d:
            rels.append(d["damage_relations"])
    result = matchup.compute_matchups(rels)
    # decorate buckets with colours for the UI
    for bucket in result["buckets"].values():
        for item in bucket:
            item["color"] = TYPE_COLORS.get(item["type"], "#68A090")
    return result


def get_bio(poke, species):
    rate = species.get("gender_rate", -1)
    if rate == -1:
        gender = {"genderless": True}
    else:
        gender = {"female": round(rate / 8 * 100, 1), "male": round((8 - rate) / 8 * 100, 1)}
    h_m = poke.get("height", 0) / 10
    w_kg = poke.get("weight", 0) / 10
    total_in = round(h_m * 39.3701)
    return {
        "height_m": round(h_m, 2),
        "height_ft": f"{total_in // 12}'{total_in % 12:02d}\"",
        "weight_kg": round(w_kg, 1),
        "weight_lb": round(w_kg * 2.20462, 1),
        "egg_groups": [pretty(g["name"]) for g in species.get("egg_groups", []) or []],
        "gender": gender,
        "held_items": [pretty(i["item"]["name"]) for i in poke.get("held_items", []) or []],
        "capture_rate": species.get("capture_rate"),
        "base_happiness": species.get("base_happiness"),
        "growth_rate": pretty((species.get("growth_rate") or {}).get("name", "")),
        "base_exp": poke.get("base_experience"),
        "is_legendary": species.get("is_legendary", False),
        "is_mythical": species.get("is_mythical", False),
    }


def get_move_groups(poke):
    """Group move names by learn method. Full per-move stats are loaded lazily."""
    levelup, machine, egg, tutor = {}, set(), set(), set()
    for m in poke.get("moves", []) or []:
        name = m["move"]["name"]
        for d in m.get("version_group_details", []) or []:
            method = d["move_learn_method"]["name"]
            if method == "level-up":
                levelup[name] = d.get("level_learned_at", 0)  # last (newest) wins
            elif method == "machine":
                machine.add(name)
            elif method == "egg":
                egg.add(name)
            elif method == "tutor":
                tutor.add(name)

    def shape(names, with_level=False):
        items = []
        for n in sorted(names):
            entry = {"name": n, "display": pretty(n)}
            if with_level:
                entry["level"] = levelup[n]
            items.append(entry)
        if with_level:
            items.sort(key=lambda x: (x["level"], x["display"]))
        return items

    return {
        "level-up": shape(levelup.keys(), with_level=True),
        "machine": shape(machine),
        "egg": shape(egg),
        "tutor": shape(tutor),
    }


def get_encounters(poke_id):
    """Per game -> list of areas, each with method(s), level range, conditions and best chance."""
    data = fetch_json(f"pokemon/{poke_id}/encounters", optional=True)
    if not data:
        return []
    games = {}
    for enc in data:
        area = pretty(enc["location_area"]["name"])
        for vd in enc.get("version_details", []) or []:
            game = pretty(vd["version"]["name"])
            slot = games.setdefault(game, {}).setdefault(
                area, {"methods": set(), "min": None, "max": None, "chance": None, "conditions": set()}
            )
            for det in vd.get("encounter_details", []) or []:
                method = (det.get("method") or {}).get("name")
                if method:
                    slot["methods"].add(pretty(method))
                mn, mx = det.get("min_level"), det.get("max_level")
                if mn is not None:
                    slot["min"] = mn if slot["min"] is None else min(slot["min"], mn)
                if mx is not None:
                    slot["max"] = mx if slot["max"] is None else max(slot["max"], mx)
                ch = det.get("chance")
                if ch is not None:
                    slot["chance"] = ch if slot["chance"] is None else max(slot["chance"], ch)
                for cv in det.get("condition_values", []) or []:
                    if cv.get("name"):
                        slot["conditions"].add(pretty(cv["name"]))

    out = []
    for game in sorted(games):
        areas = []
        for area, slot in games[game].items():
            areas.append({
                "area": area,
                "methods": sorted(slot["methods"]),
                "min_level": slot["min"],
                "max_level": slot["max"],
                "chance": slot["chance"],
                "conditions": sorted(slot["conditions"]),
            })
        areas.sort(key=lambda a: (-(a["chance"] or 0), a["area"]))
        out.append({"game": game, "areas": areas})
    return out


# --------------------------------------------------------------------------- #
# top-level payloads
# --------------------------------------------------------------------------- #
def get_pokemon(key):
    poke = fetch_json(f"pokemon/{str(key).lower()}")
    species = fetch_json(poke["species"]["url"])
    art = best_artwork(poke)

    types = [{"name": t["type"]["name"], "color": TYPE_COLORS.get(t["type"]["name"], "#68A090")}
             for t in poke.get("types", []) or []]
    stats = []
    for s in poke.get("stats", []) or []:
        stats.append({
            "name": s["stat"]["name"],
            "label": STAT_LABELS.get(s["stat"]["name"], pretty(s["stat"]["name"])),
            "value": s["base_stat"],
        })
    total = sum(s["value"] for s in stats)

    gen_num = id_from_url((species.get("generation") or {}).get("url", "")) or 0

    return {
        "id": poke["id"],
        "name": poke["name"],
        "display": english_name(species, poke["name"]),
        "genus": english_genus(species),
        "order": species.get("order"),
        "generation": gen_num,
        "generation_label": f"Gen {ROMAN.get(gen_num, gen_num)}",
        "types": types,
        **art,
        "cry": (poke.get("cries") or {}).get("latest"),
        "stats": stats,
        "stat_total": total,
        "flavor": english_flavor(species),
        "abilities": get_abilities(poke),
        "matchups": get_matchups(poke),
        "bio": get_bio(poke, species),
        "moves": get_move_groups(poke),
        "evolution": get_evolution(species),
        "forms": get_forms(species, species["name"]),
        "encounters": get_encounters(poke["id"]),
        "is_default": poke.get("is_default", True),
    }


def get_move(name):
    d = fetch_json(f"move/{name.lower()}")
    effect = ""
    chance = d.get("effect_chance")
    for e in d.get("effect_entries", []) or []:
        if e["language"]["name"] == "en":
            effect = (e.get("short_effect") or e.get("effect") or "")
            break
    if chance is not None:
        effect = effect.replace("$effect_chance", str(chance))
    return {
        "name": d["name"],
        "display": pretty(d["name"]),
        "type": (d.get("type") or {}).get("name", ""),
        "type_color": TYPE_COLORS.get((d.get("type") or {}).get("name", ""), "#68A090"),
        "category": (d.get("damage_class") or {}).get("name", "status"),
        "power": d.get("power"),
        "accuracy": d.get("accuracy"),
        "pp": d.get("pp"),
        "effect": effect.strip(),
    }


def get_cards(ids):
    """Lazy type chips (+ display name) for a batch of grid cards."""
    detail = fetch_many([f"pokemon/{i}" for i in ids], optional=True)
    out = {}
    for i in ids:
        d = detail.get(f"pokemon/{i}")
        if not d:
            continue
        out[str(i)] = {
            "types": [{"name": t["type"]["name"], "color": TYPE_COLORS.get(t["type"]["name"], "#68A090")}
                      for t in d.get("types", []) or []],
        }
    return out


_INDEX_CACHE = None


def build_index():
    """Every national-dex species for the grid. Cheap: 1 dex call + 9 generation calls."""
    global _INDEX_CACHE
    if _INDEX_CACHE is not None:
        return _INDEX_CACHE

    dex = fetch_json("pokedex/national")
    gen_of = {}
    generations = []
    for g in range(1, 10):
        gd = fetch_json(f"generation/{g}", optional=True)
        if not gd:
            continue
        generations.append({"id": g, "label": f"Gen {ROMAN[g]}"})
        for sp in gd.get("pokemon_species", []) or []:
            gen_of[sp["name"]] = g

    pokemon = []
    for entry in dex.get("pokemon_entries", []) or []:
        name = entry["pokemon_species"]["name"]
        pid = entry["entry_number"]
        pokemon.append({
            "id": pid,
            "name": name,
            "display": pretty(name),
            "gen": gen_of.get(name, 0),
            "artwork": artwork_url(pid),
            "sprite": f"{SPRITES}/{pid}.png",
        })

    _INDEX_CACHE = {
        "count": len(pokemon),
        "generations": generations,
        "type_colors": TYPE_COLORS,
        "pokemon": pokemon,
    }
    return _INDEX_CACHE
