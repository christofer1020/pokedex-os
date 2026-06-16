# POKÉDEX OS

A premium, full-featured Pokédex web app that feels like looking *inside* a real
handheld device — a glossy red clamshell with a phosphor-green data screen,
scanlines, status LEDs, a tactile D-pad, and smooth, lit animations. It browses
every Pokémon, searches by name or number (typo-tolerant), and opens a deep,
tabbed entry for any creature, all sourced live from [PokéAPI](https://pokeapi.co).

---

## Quick start

You need **Python 3.9+** and an internet connection (the app pulls live data from
PokéAPI on first use and caches it locally afterward).

```bash
# 1. from inside the pokedex-os/ folder, install the two dependencies
pip install -r requirements.txt
#    (or simply:  pip install flask requests)

# 2. start the server
python3 server.py

# 3. open the device in your browser
#    http://localhost:8000
```

That's it — one command, no build step, no Node, no bundler. The server prints the
URL when it boots. To use a different port: `PORT=9000 python3 server.py`.

### 👉 What to do first
When the device powers on you'll see the **browsable grid** of every Pokémon on the
right screen. To feel the whole thing out in ten seconds:

1. **Type `charizard`** (or even `charizrd` — fuzzy search forgives typos) in the
   search bar, or just **click any card** to open an entry. The **background reacts to
   the Pokémon**: it tints to that Pokémon's type colours (a two-colour wash for dual
   types) and a few faint copies of its own artwork drift behind the device. Page to a
   different Pokémon and the whole backdrop shifts colour with it. The artwork shows on
   the left screen — **open the “Matchups” tab** to see the **full 18-type defensive
   grid**, colour-coded ×0–×4 (Charizard is ×4 from Rock, immune to Ground, ×¼ from
   Grass/Bug). The math is computed, not hard-coded, and dual types are multiplied
   correctly.
2. **Open “Evolution.”** It now holds the evolution tree *and* every form: trigger
   text on each arrow with the **item's pixel sprite** (try an Eevee or a stone
   evolver), then **Forms & Variants** below — regional forms, Megas with their
   **Mega-Stone sprite + name**, and a **GIGANTAMAX** band on Gmax forms. Click any
   form or stage to jump to it.
3. **Open “Locations”** and **tap a game** to expand its areas — method (walk/surf/
   old-rod…), level range, conditions (time/season), and % chance.
4. Tap **NORMAL / SHINY** to flip the sprite; use the **◀ ▶ D-pad** or arrow keys to
   page through the dex. Press **`/`** to search, **Esc** to return to the grid.

---

## Features

**Browse & find**
- Grid of every national-dex Pokémon — sprite, dex number, name, and type chips
  (chips lazy-load as cards scroll into view; the grid infinite-scrolls).
- Typo-tolerant search by **name or dex number** with live autocomplete.
- Filter by **type** (any of 18) and by **generation**.

**Every entry includes**
- Official artwork (left screen) with a **normal ↔ shiny** toggle. Everywhere inside
  the data screen — grid, evolution tree, forms — uses authentic **pixel game
  sprites** (FireRed/LeafGreen for Gen 1–3, Black/White for Gen 4–5, the contributed
  default sprite for Gen 6–9 and alternate forms), falling back to scaled-down
  official artwork only when no pixel sprite exists.
- Types, **base stats** with filled, **per-stat-coloured** bars (HP green, Attack red,
  Defense gold, Sp. Atk blue, Sp. Def teal, Speed purple) + total, and flavor text.
- **Full 18-type defensive grid** — the multiplier this Pokémon takes from every
  attacking type (×0, ×¼, ×½, ×1, ×2, ×4), colour-coded, dual types multiplied. No
  prose lists; just the whole chart.
- **Abilities** with effect text, with hidden abilities flagged.
- **Moves** grouped by how they're learned (level-up / TM·HM / egg / tutor); expand
  any move for its type, category, power, accuracy, and PP (loaded on demand).
- **Evolution + every form in one tab.** The evolution tree shows triggers (levels,
  stones, trades, friendship, time, etc.) with the relevant **item pixel sprite** on
  each step, including branching lines. Below it, **Forms & Variants** — regional
  (Alolan/Galarian/Hisuian/Paldean), **Megas with their Mega-Stone sprite + name**,
  **Gigantamax** (badged), and any other variety the API lists — all switchable in
  place.
- **Bio**: height/weight, egg groups, gender ratio, held items, capture rate, base
  happiness, growth rate, and legendary/mythical flags.
- **Locations** — **click a game to expand** its wild-encounter areas: method, level
  range, conditions (time/season), and % chance (with a graceful empty state).

**Feel**
- **A background that reacts to the open Pokémon.** Open any entry and the backdrop
  tints to that Pokémon's type colours — a soft two-colour wash for dual types — while
  a few faint, gently drifting copies of its own artwork sit behind the device. Move to
  another Pokémon and the colour shifts with it; the grid uses a calm neutral wash. The
  device stays the hero behind a soft darkening veil, and the motion stops under
  `prefers-reduced-motion`.
- Clean, **flat screens** — no gloss, glare, scanlines, or glow behind the device.
- Power-on boot animation, channel-flicker tab changes, stat bars that fill, and a
  sparkle burst on the shiny toggle.
- Fully responsive (the clamshell stacks vertically on phones), keyboard-navigable,
  with visible focus rings and full `prefers-reduced-motion` support.
- Robust loading skeletons, error states, and empty states throughout.

---

## Data notes & honesty

- **All data is live from PokéAPI** at runtime, cached on disk + in memory. Sprites
  load directly from the PokéAPI sprite CDN in your browser.
- **Special obtain methods and fusions are API-only.** Evolution triggers, forms, and
  wild-encounter data are exactly what PokéAPI exposes — nothing about gift/event/
  quest steps or fusions is invented. Triggers and items are attached only where the
  API actually provides them.
- **Mega-Stone mapping is curated.** PokéAPI does not link a Mega/Primal form to its
  stone, so the form → stone mapping (e.g. *Mega Charizard X → Charizardite X*,
  *Primal Groudon → Red Orb*) is a small, well-known canonical table baked into the
  backend. The stone *sprite* still comes from the PokéAPI item CDN. Forms not in the
  table simply show the form without a stone.
- **Regional-form evolutions** appear as switchable form cards; a regional form's own
  evolution line shows on that form's entry, because PokéAPI's evolution chain is
  keyed to the base species and doesn't cleanly expose parallel regional branches.
- **The background isn't bundled art.** The backdrop's colours are derived from the
  Pokémon's own type colours (already in the PokéAPI data), and the faint motifs reuse
  the **same official artwork the app already streams from the PokéAPI sprite CDN** at
  runtime — nothing is drawn by hand and no image files are committed to the repo, so
  there's nothing extra to break or ship. (As with any Pokédex, that artwork and data
  are third-party assets fetched live, not redistributed in this project.)
- **Validation:** the type math and API aggregation (matchups, evolution triggers,
  Mega-stone/Gmax tagging, the encounters parser) are covered by offline tests against
  fixtures, and the UI was checked via rendered screenshots. The live network calls
  and sprite URLs themselves resolve in your browser — there's no internet in the
  build sandbox, so end-to-end live fetching is exercised when *you* run it.

---



| Layer | Choice | Why |
|---|---|---|
| Backend | **Python + Flask** | Serves the app *and* a small JSON API that wraps PokéAPI, with disk + in-memory caching and concurrent batching so the UI stays fast and PokéAPI isn't hammered. |
| Frontend | **Vanilla JS SPA + custom CSS** (no build) | Runs with a single `python3 server.py` — no npm, no bundler, nothing to compile. It also makes the bespoke "physical device" aesthetic possible with full control, and keeps everything working offline once data is cached. |
| Search | stdlib `difflib` (server) + a client-side fuzzy matcher | Typo tolerance with zero extra dependencies. |

**Honest trade-off:** the original brief suggested Tailwind + shadcn/ui. Those need a
React/npm build pipeline; to keep this *one-command runnable* and to hand-craft the
tactile device look, I wrote the styling as custom CSS instead. The result is
dependency-free and self-contained. If you'd prefer the Tailwind+shadcn route, the
backend API is UI-agnostic and a React front end could consume it unchanged.

### How the backend stays fast
- `/api/index` builds the full grid from just ~10 calls (national dex + 9 generations);
  sprite/artwork URLs are derived from IDs rather than fetched per-Pokémon.
- Type chips for grid cards are fetched lazily in batches (`/api/cards`) only for what
  you actually scroll past.
- A full entry (`/api/pokemon/<name>`) fans out across the needed PokéAPI resources,
  caching each to disk; move details load on demand (`/api/move/<name>`).
- Every fetched resource is cached to `./.cache/` (override with `POKEDEX_CACHE`), so
  repeat views are instant.

---

## Project structure

```
pokedex-os/
├── server.py            Flask app: serves the SPA + JSON API, fuzzy search, SPA routing
├── pokeapi.py           Aggregation: turns many PokéAPI resources into UI-ready payloads
├── cache.py             Disk + memory caching fetch layer (concurrent batching)
├── matchup.py           Pure defensive type-effectiveness engine (unit-tested)
├── requirements.txt
├── web/
│   ├── index.html       The persistent device shell (two screens, hinge, controls)
│   ├── styles.css       The full premium device aesthetic
│   └── app.js           The SPA: grid, search, filters, entry tabs, navigation
├── fixtures/            Canned PokéAPI JSON used by the offline tests
└── tests/
    ├── test_matchup.py        Type-math unit tests
    └── test_server_offline.py Aggregation + Flask route tests (run against fixtures)
```

---

## Tests

```bash
python3 tests/test_matchup.py          # type-effectiveness math
python3 tests/test_server_offline.py   # aggregation + API routes, against fixtures
```

The test suite runs **fully offline** against canned fixtures (it sets
`POKEDEX_OFFLINE=1`), and verifies the things most likely to break: dual-type matchup
math (Charizard = ×4 Rock, 0× Ground, ¼ Grass/Bug), hidden-ability flagging, branching
vs. non-evolving chains, fuzzy/number search, and clean 404 handling for unknown names.

> **A note on what was validated where:** this project was assembled in a sandbox with
> no outbound internet, so the logic, type math, caching, aggregation, and HTTP routes
> were verified offline against fixtures, and the UI was checked via rendered
> screenshots. The **live PokéAPI path is identical** and runs the moment you start the
> server on your own (networked) machine — first load fetches and caches, and everything
> after that is served from cache.

---

## Keyboard shortcuts

| Key | Action |
|---|---|
| `/` | Focus the search bar |
| `◀` `▶` | Previous / next Pokémon (in an entry) |
| `▲` `▼` | Scroll the data screen |
| `Esc` | Back to the grid |

Enjoy exploring the dex. ⚡
