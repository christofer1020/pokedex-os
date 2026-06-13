import requests
import json
import os
import webbrowser
from thefuzz import process

# --- Configuration ---
POKEAPI_BASE = "https://pokeapi.co/api/v2"
TEMPLATE_FILE = "pokedex.html"
OUTPUT_FILE = "generated_pokedex.html"

# --- API Helpers ---
def fetch_json(url):
    """Utility to fetch and parse JSON from an API endpoint."""
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

def fetch_pokemon_list():
    """Fetches a list of valid Pokemon names for typo correction."""
    print("[*] Fetching valid Pokemon list for auto-correct...")
    data = fetch_json(f"{POKEAPI_BASE}/pokemon?limit=10000")
    if data:
        return [p['name'] for p in data['results']]
    return []

# --- Data Processing Functions ---
def get_types_html(types_data):
    html = ""
    # Pokemon type color mapping
    type_colors = {
        "normal": "#A8A878", "fire": "#F08030", "water": "#6890F0", "electric": "#F8D030",
        "grass": "#78C850", "ice": "#98D8D8", "fighting": "#C03028", "poison": "#A040A0",
        "ground": "#E0C068", "flying": "#A890F0", "psychic": "#F85888", "bug": "#A8B820",
        "rock": "#B8A038", "ghost": "#705898", "dragon": "#7038F8", "dark": "#705848",
        "steel": "#B8B8D0", "fairy": "#EE99AC"
    }
    for t in types_data:
        t_name = t['type']['name']
        color = type_colors.get(t_name, "#68A090")
        html += f'<span class="type-badge" style="background:{color}; box-shadow: 0 0 10px {color};">{t_name.upper()}</span>\n'
    return html

def get_stats_html(stats_data):
    html = ""
    # Map API stat names to UI abbreviations
    stat_abbr = {
        "hp": "HP", "attack": "ATK", "defense": "DEF", 
        "special-attack": "SPA", "special-defense": "SPD", "speed": "SPE"
    }
    for stat in stats_data:
        name = stat_abbr.get(stat['stat']['name'], stat['stat']['name'].upper())
        value = stat['base_stat']
        # Normalize bar width (max 255 for base stats)
        width_pct = min((value / 200) * 100, 100) 
        html += f'''
        <div class="stat-row">
            <span class="stat-label">{name}</span>
            <div class="stat-bar-container"><div class="stat-bar" style="width: {width_pct}%;"></div></div>
            <span class="stat-num">{value}</span>
        </div>
        '''
    return html

def get_moves_html(moves_data):
    moves_list = []
    for move in moves_data:
        # Check version group details for level-up moves
        for detail in move['version_group_details']:
            if detail['move_learn_method']['name'] == 'level-up':
                level = detail['level_learned_at']
                name = move['move']['name'].replace('-', ' ').upper()
                moves_list.append((level, name))
                break # Only add once per move

    # Sort by level learned
    moves_list.sort(key=lambda x: x[0])
    
    html = ""
    for level, name in moves_list:
        html += f'<div class="pill"><span style="color:#fff">{name}</span><span style="color:#aaa">Lvl {level}</span></div>\n'
    
    if not html:
        return '<div class="pill"><span style="color:#aaa">No level-up moves found.</span></div>'
    return html

def parse_evo_chain(chain, html=""):
    """Recursively builds the evolution tree HTML."""
    species_name = chain['species']['name']
    species_data = fetch_json(f"{POKEAPI_BASE}/pokemon/{species_name}")
    sprite = species_data['sprites']['front_default'] if species_data else ""
    
    html += f'''
    <div class="evo-item">
        <img class="evo-sprite" src="{sprite}">
        <span class="evo-name">{species_name}</span>
    </div>
    '''
    
    if chain['evolves_to']:
        # Get evolution details
        details = chain['evolves_to'][0]['evolution_details'][0]
        trigger = "Trade" if details['trigger']['name'] == 'trade' else "Evolve"
        if details.get('min_level'): trigger = f"Lvl {details['min_level']}"
        elif details.get('item'): trigger = f"Use {details['item']['name'].replace('-', ' ').title()}"
        
        html += f'<div class="evo-arrow"><br>{trigger}<br>→</div>\n'
        
        # Recursively call for next stage
        html = parse_evo_chain(chain['evolves_to'][0], html)
        
    return html

def get_locations_html(pokemon_id):
    encounters = fetch_json(f"{POKEAPI_BASE}/pokemon/{pokemon_id}/encounters")
    if not encounters:
        return '''
        <div class="loc-box">
            <div class="loc-desc">Obtained via Evolution, Breeding, Event, or In-Game Trade.</div>
        </div>
        '''
    
    # Group locations by game version
    games_map = {}
    for encounter in encounters:
        loc_name = encounter['location_area']['name'].replace('-', ' ').title()
        for version_detail in encounter['version_details']:
            game_ver = version_detail['version']['name'].replace('-', ' ').upper()
            if game_ver not in games_map:
                games_map[game_ver] = set()
            games_map[game_ver].add(loc_name)
    
    html = ""
    for game, locs in games_map.items():
        # Display max 3 locations per game to save space
        loc_str = ", ".join(list(locs)[:3])
        if len(locs) > 3: loc_str += "..."
        html += f'''
        <div class="loc-box">
            <div class="loc-title">{game}</div>
            <div class="loc-desc">{loc_str}</div>
        </div>
        '''
    return html

# --- Main Logic ---
def main():
    if not os.path.exists(TEMPLATE_FILE):
        print(f"[-] ERROR: Template file '{TEMPLATE_FILE}' not found. Please create it in the same directory.")
        return

    valid_pokemon = fetch_pokemon_list()
    
    while True:
        user_input = input("\n[?] Enter a Pokemon name (or 'exit' to quit): ").strip().lower()
        if user_input == 'exit':
            break
        if not user_input:
            continue

        # Auto-correct typo
        best_match = user_input
        if valid_pokemon:
            matches = process.extractOne(user_input, valid_pokemon)
            if matches and matches[1] < 100 and matches[1] > 60:
                confirm = input(f"[*] Did you mean '{matches[0]}'? [Y/n]: ").strip().lower()
                if confirm in ('', 'y', 'yes'):
                    best_match = matches[0]
            elif matches and matches[1] >= 100:
                best_match = matches[0]

        print(f"[*] Fetching data for {best_match.title()}...")
        
        # 1. Fetch Basic Pokemon Data
        poke_data = fetch_json(f"{POKEAPI_BASE}/pokemon/{best_match}")
        if not poke_data:
            print("[-] Pokemon not found in API.")
            continue
            
        poke_id = poke_data['id']
        main_art = poke_data['sprites']['other']['official-artwork']['front_default'] or ""
        shiny_art = poke_data['sprites']['other']['official-artwork']['front_shiny'] or main_art
        front_def = poke_data['sprites']['front_default'] or ""
        front_shiny = poke_data['sprites']['front_shiny'] or front_def
        
        # 2. Fetch Species Data (for Dex Entry & Evolution Chain URL)
        species_data = fetch_json(poke_data['species']['url'])
        
        # Flavor Text
        flavor_text = "No pokedex entry found."
        for entry in species_data.get('flavor_text_entries', []):
            if entry['language']['name'] == 'en':
                flavor_text = entry['flavor_text'].replace('\n', ' ').replace('\f', ' ')
                break
                
        # 3. Process Tab Data
        types_html = get_types_html(poke_data['types'])
        stats_html = get_stats_html(poke_data['stats'])
        moves_html = get_moves_html(poke_data['moves'])
        locations_html = get_locations_html(poke_id)
        
        # 4. Evolutions, Megas & G-Max
        evo_tree_html = ""
        megas_html = ""
        gmax_html = ""
        
        # Build Tree
        evo_chain_data = fetch_json(species_data['evolution_chain']['url'])
        if evo_chain_data:
             evo_tree_html = parse_evo_chain(evo_chain_data['chain'])
             
        # Check Varieties for Megas/GMAX
        megas = []
        gmax_sprite = None
        for variety in species_data['varieties']:
            v_name = variety['pokemon']['name']
            if '-mega' in v_name:
                mega_data = fetch_json(variety['pokemon']['url'])
                if mega_data:
                    sprite = mega_data['sprites']['front_default']
                    item_name = v_name.replace('-mega', 'ite') # Naive guess for stone name
                    item_sprite = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/{item_name}.png"
                    megas.append((v_name.replace('-', ' ').upper(), sprite, item_sprite))
            elif '-gmax' in v_name:
                gmax_data = fetch_json(variety['pokemon']['url'])
                if gmax_data:
                    gmax_sprite = gmax_data['sprites']['front_default']
                    
        if megas:
            megas_html = '<div class="section-title">MEGA EVOLUTIONS</div>\n<div class="evo-chain">\n'
            for name, sprite, item_sprite in megas:
                megas_html += f'''
                <div class="evo-item" style="margin-right:20px;">
                    <img class="evo-sprite" src="{sprite}">
                    <span class="evo-name">{name}</span>
                    <img class="item-sprite" src="{item_sprite}" onerror="this.style.display='none'">
                </div>
                '''
            megas_html += '</div>\n'
            
        if gmax_sprite:
            gmax_html = f'''
            <div class="section-title">GIGANTAMAX FORM</div>
            <div class="evo-chain">
                <div class="evo-item">
                    <img class="evo-sprite" src="{gmax_sprite}">
                    <span class="evo-name" style="color:#ff5555;">G-MAX</span>
                    <span style="font-size:7px; color:#aaa; margin-top:4px;">G-MAX FACTOR</span>
                </div>
            </div>
            '''

        # --- Inject into HTML ---
        print("[*] Generating UI...")
        with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Simple string replacements matching the placeholders
        replacements = {
            "{main_artwork}": main_art,
            "{shiny_artwork}": shiny_art,
            "{dex_number}": str(poke_id).zfill(3),
            "{pokemon_name}": best_match.upper(),
            "{types_html}": types_html,
            "{flavor_text}": flavor_text,
            "{stats_html}": stats_html,
            "{moves_html}": moves_html,
            "{evo_tree_html}": evo_tree_html,
            "{megas_html}": megas_html,
            "{gmax_html}": gmax_html,
            "{locations_html}": locations_html,
            "{front_default}": front_def,
            "{front_shiny}": front_shiny
        }

        for key, value in replacements.items():
            html_content = html_content.replace(key, str(value))

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"[+] Success! Opening {OUTPUT_FILE} in browser...\n")
        webbrowser.open('file://' + os.path.realpath(OUTPUT_FILE))

if __name__ == "__main__":
    main()