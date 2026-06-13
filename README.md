# Pokédex OS v5.0 🔴

An interactive, full-stack Pokédex application featuring a skeuomorphic/glassmorphic UI and a dynamic Python backend.

## 🚀 Features
* **Dynamic Data:** Fetches real-time data from [PokeAPI](https://pokeapi.co/).
* **Python Backend:** A robust Python script that acts as the engine, processing complex nested JSON data (Evolutions, Encounter Locations, Level-Up Moves).
* **Auto-Correction:** Uses `thefuzz` for fuzzy string matching to auto-correct typos in user input (e.g., typing "charimander" fetches "charmander").
* **Interactive UI:** 5 functional tabs written in raw HTML/CSS/JS, featuring dynamic sprite toggling (Normal/Shiny) and dynamic HTML injection.

## 🛠️ Technologies Used
* **Frontend:** HTML5, CSS3 (Advanced Box-Shadows, Gradients), JavaScript.
* **Backend:** Python (`requests`, `thefuzz`, `webbrowser`).

## ⚙️ How to Run
1. Clone this repository.
2. Install the required Python libraries:
   `pip install requests thefuzz`
3. Make sure `pokedex.html` is in the same directory.
4. Run the engine:
   `python run_pokedex.py`
5. Type a Pokémon name in the terminal, and watch the UI generate in your browser!
