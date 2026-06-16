"""
Caching layer for PokeAPI.

PokeAPI is read-only and explicitly asks consumers to cache, so every resource we
ever touch is stored both in memory (fast repeat lookups within a process) and on
disk (survives restarts). Pulling full move/ability/type details means many calls,
so this also exposes a batched concurrent fetch.

Offline mode (POKEDEX_OFFLINE=1) reads canned JSON from ./fixtures instead of the
network, which is how the test suite runs without internet.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = "https://pokeapi.co/api/v2"
CACHE_DIR = os.environ.get("POKEDEX_CACHE", os.path.join(os.path.dirname(__file__), ".cache"))
FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
OFFLINE = os.environ.get("POKEDEX_OFFLINE") == "1"
TIMEOUT = 20
RETRIES = 3
HEADERS = {"User-Agent": "POKEDEX-OS/1.0 (local educational app)"}

os.makedirs(CACHE_DIR, exist_ok=True)

_mem = {}
_mem_lock = threading.Lock()
_session = requests.Session()
_session.headers.update(HEADERS)


class FetchError(RuntimeError):
    """Raised when a resource cannot be retrieved (after retries / when missing)."""


def _key(path_or_url):
    """Normalise a full URL or relative path into a stable cache key like 'pokemon/25'."""
    s = path_or_url
    if s.startswith("http"):
        s = s.split("/api/v2/", 1)[-1]
    return s.strip("/").lower()


def _disk_path(key):
    safe = re.sub(r"[^a-z0-9._/-]", "_", key).replace("/", "__")
    return os.path.join(CACHE_DIR, safe + ".json")


def _read_disk(key):
    p = _disk_path(key)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _write_disk(key, data):
    try:
        with open(_disk_path(key), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass  # cache is best-effort; never fail a request because the disk is unhappy


def _read_fixture(key):
    p = os.path.join(FIXTURE_DIR, key.replace("/", "__") + ".json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def fetch_json(path_or_url, optional=False):
    """
    Fetch a PokeAPI resource (by relative path like 'pokemon/charizard' or full URL),
    using memory -> disk -> network in that order.

    optional=True returns None instead of raising when the resource is missing/404
    (used for things like encounter data that legitimately may not exist).
    """
    key = _key(path_or_url)

    with _mem_lock:
        if key in _mem:
            return _mem[key]

    cached = _read_disk(key)
    if cached is not None:
        with _mem_lock:
            _mem[key] = cached
        return cached

    if OFFLINE:
        fx = _read_fixture(key)
        if fx is None:
            if optional:
                return None
            raise FetchError(f"[offline] no fixture for '{key}'")
        with _mem_lock:
            _mem[key] = fx
        return fx

    url = path_or_url if path_or_url.startswith("http") else f"{BASE}/{key}"
    last_err = None
    for attempt in range(RETRIES):
        try:
            resp = _session.get(url, timeout=TIMEOUT)
            if resp.status_code == 404:
                if optional:
                    return None
                raise FetchError(f"not found: {url}")
            resp.raise_for_status()
            data = resp.json()
            _write_disk(key, data)
            with _mem_lock:
                _mem[key] = data
            return data
        except requests.RequestException as exc:
            last_err = exc
            time.sleep(0.4 * (attempt + 1))

    if optional:
        return None
    raise FetchError(f"could not fetch {url}: {last_err}")


def fetch_many(paths, max_workers=16, optional=True):
    """Fetch many resources concurrently. Returns a dict {key: data-or-None}."""
    out = {}
    if not paths:
        return out
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fetch_json, p, optional): p for p in paths}
        for fut, p in futures.items():
            try:
                out[_key(p)] = fut.result()
            except FetchError:
                out[_key(p)] = None
    return out
