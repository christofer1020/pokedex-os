"""
POKEDEX OS -- local backend.

Serves the single-page frontend from ./web and a small JSON API that wraps and
caches PokeAPI. Run it with:  python3 server.py   then open http://localhost:8000
"""

from __future__ import annotations

import difflib
import os

from flask import Flask, jsonify, request, send_from_directory

import pokeapi
from cache import FetchError

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
app = Flask(__name__, static_folder=None)

# light response cache headers so the browser/SPA feel instant on repeat views
@app.after_request
def _cache_headers(resp):
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


# ---- frontend ---- #
@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    # real asset? serve it.
    full = os.path.normpath(os.path.join(WEB_DIR, filename))
    if full.startswith(WEB_DIR) and os.path.isfile(full):
        return send_from_directory(WEB_DIR, filename)
    # unknown /api/* path -> clean JSON 404 (never serve HTML for the API)
    if filename.startswith("api/"):
        return jsonify({"error": "Not found."}), 404
    # otherwise it's a client-side route (e.g. /pokemon/charizard) -> SPA shell
    return send_from_directory(WEB_DIR, "index.html")


# ---- API ---- #
@app.route("/api/index")
def api_index():
    try:
        return jsonify(pokeapi.build_index())
    except FetchError as e:
        return jsonify({"error": str(e), "hint": "PokeAPI unreachable -- check your internet connection."}), 502


@app.route("/api/pokemon/<key>")
def api_pokemon(key):
    try:
        return jsonify(pokeapi.get_pokemon(key))
    except FetchError:
        return jsonify({"error": f"No Pokémon matched '{key}'."}), 404
    except Exception as e:  # defensive: an odd edge-case Pokemon should 500 cleanly, not hang
        return jsonify({"error": f"Could not assemble entry for '{key}': {e}"}), 500


@app.route("/api/cards")
def api_cards():
    raw = request.args.get("ids", "")
    ids = [p for p in raw.split(",") if p.strip().isdigit()][:80]
    if not ids:
        return jsonify({})
    return jsonify(pokeapi.get_cards(ids))


@app.route("/api/move/<name>")
def api_move(name):
    try:
        return jsonify(pokeapi.get_move(name))
    except FetchError:
        return jsonify({"error": f"Unknown move '{name}'."}), 404


@app.route("/api/search")
def api_search():
    """Fuzzy / typo-tolerant search across the dex index (server-side fallback)."""
    q = (request.args.get("q") or "").strip().lower()
    if not q:
        return jsonify([])
    try:
        index = pokeapi.build_index()
    except FetchError as e:
        return jsonify({"error": str(e)}), 502

    mons = index["pokemon"]
    if q.isdigit():
        n = int(q)
        results = [m for m in mons if str(m["id"]).startswith(q)][:20] or [m for m in mons if m["id"] == n]
        return jsonify(results[:20])

    names = [m["name"] for m in mons]
    by_name = {m["name"]: m for m in mons}
    starts = [m for m in mons if m["name"].startswith(q)]
    contains = [m for m in mons if q in m["name"] and not m["name"].startswith(q)]
    fuzzy = [by_name[n] for n in difflib.get_close_matches(q, names, n=10, cutoff=0.6)]

    seen, out = set(), []
    for m in starts + contains + fuzzy:
        if m["id"] not in seen:
            seen.add(m["id"])
            out.append(m)
    return jsonify(out[:20])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"\n  POKEDEX OS  ->  http://localhost:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
