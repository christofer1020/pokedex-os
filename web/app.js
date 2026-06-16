/* ============================================================================
   POKÉDEX OS — single-page app brain (no build step, no dependencies).
   Talks to the Flask API, drives the two screens of the device, handles
   routing, search, filters, infinite scroll, the entry tabs and navigation.
   ========================================================================== */
(function () {
  "use strict";

  // -------------------------------------------------------------- shortcuts -
  const $  = (s, r = document) => r.querySelector(s);
  const device   = $("#device");
  const viewEl   = $("#view");
  const dataEl   = $("#data");
  const toastEl  = $("#toast");
  const statusEl = $("#brandStatus");
  const PLACEHOLDER =
    "data:image/svg+xml;utf8," +
    encodeURIComponent(
      "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 96 96'>" +
      "<circle cx='48' cy='48' r='34' fill='none' stroke='%232E7F5E' stroke-width='5'/>" +
      "<line x1='14' y1='48' x2='82' y2='48' stroke='%232E7F5E' stroke-width='5'/>" +
      "<circle cx='48' cy='48' r='9' fill='none' stroke='%232E7F5E' stroke-width='5'/></svg>"
    );

  const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // -------- in-dex pixel sprites (by id) --------
  // Authentic game sprites for the data screen. FireRed/LeafGreen for Gen 1-3,
  // Black/White for Gen 4-5, and the contributed default sprite (covers Gen 6-9 +
  // alternate-form ids). Each step falls back to the next, then to official art,
  // then to a drawn placeholder — so nothing ever shows a broken image.
  const SPRITE_BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon";
  function pixelChain(id) {
    const urls = [];
    if (id && id <= 386) urls.push(`${SPRITE_BASE}/versions/generation-iii/firered-leafgreen/${id}.png`);
    if (id && id <= 649) urls.push(`${SPRITE_BASE}/versions/generation-v/black-white/${id}.png`);
    if (id) urls.push(`${SPRITE_BASE}/${id}.png`);
    if (id) urls.push(`${SPRITE_BASE}/other/official-artwork/${id}.png`);
    return urls;
  }
  // Build an <img> that walks the pixel chain on error. `cls` and extra attrs optional.
  function pixImg(id, alt, cls, extra) {
    const chain = pixelChain(id);
    const first = chain[0] || PLACEHOLDER;
    const rest = chain.slice(1).join("|");
    return `<img class="${cls || ""}" alt="${esc(alt || "")}" src="${esc(first)}" ` +
      `data-chain="${esc(rest)}" onerror="pixelFallback(this)" ${extra || ""}>`;
  }
  window.pixelFallback = function (img) {
    const rest = (img.getAttribute("data-chain") || "").split("|").filter(Boolean);
    if (rest.length) {
      const next = rest.shift();
      img.setAttribute("data-chain", rest.join("|"));
      img.src = next;
    } else {
      img.onerror = null;
      img.src = PLACEHOLDER;
      img.classList.remove("ph");
    }
  };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const esc = (s) =>
    String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

  // ------------------------------------------------------------------ state -
  let INDEX = null;            // { count, generations, type_colors, pokemon[] }
  let TYPE_COLORS = {};
  let FILTERED = [];           // currently shown list (after filters/search)
  let cursor = 0;              // how many cards rendered so far
  const PAGE = 60;

  const typeData = new Map();  // id(number) -> [{name,color}]   (lazy)
  const activeTypes = new Set();
  let activeGen = null;
  let term = "";

  let current = null;          // loaded entry payload
  let isShiny = false;
  let activeTab = "stats";
  let suggestIdx = -1;

  let scrollIO = null;         // infinite-scroll sentinel observer
  let cardIO = null;           // lazy type-chip observer
  const cardEls = new Map();   // id -> card element (for chip hydration)
  let chipQueue = new Set();
  let chipTimer = null;

  const api_cache = new Map();
  let viewBody = null;
  let inflightEntry = null;    // AbortController for entry fetch

  // ------------------------------------------------------------------- API --
  async function api(path, { signal } = {}) {
    if (api_cache.has(path)) return api_cache.get(path);
    const res = await fetch(path, { signal });
    let body = null;
    try { body = await res.json(); } catch (_) {}
    if (!res.ok) {
      const err = new Error((body && body.error) || `Request failed (${res.status})`);
      err.status = res.status;
      err.hint = body && body.hint;
      throw err;
    }
    api_cache.set(path, body);
    return body;
  }

  function setStatus(t) { if (statusEl) statusEl.textContent = t; }

  // ---------- reactive background: tinted to the open Pokémon + faint artwork ----------
  // No hand-drawn art and nothing bundled — the colour comes from the Pokémon's types
  // and the faint motifs reuse the same official artwork the app already loads at runtime.
  function hexToRgba(hex, a) {
    if (!hex) return `rgba(91,232,168,${a})`;
    let h = String(hex).replace("#", "").trim();
    if (h.length === 3) h = h.split("").map((x) => x + x).join("");
    if (h.length !== 6) return `rgba(91,232,168,${a})`;
    const n = parseInt(h, 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }

  let bgArtKey = null;
  function setBackground(m) {
    const tint = $("#bgTint"), art = $("#bgArt");
    if (!tint) return;
    if (!m) {                                   // grid / no entry: calm neutral
      tint.style.setProperty("--bg1", "rgba(46,64,96,.32)");
      tint.style.setProperty("--bg2", "rgba(18,28,48,.34)");
      if (art && bgArtKey !== null) { art.innerHTML = ""; bgArtKey = null; }
      return;
    }
    const c1 = (m.types[0] && m.types[0].color) || "#5be8a8";
    const c2 = (m.types[1] && m.types[1].color) || c1;
    tint.style.setProperty("--bg1", hexToRgba(c1, 0.55));
    tint.style.setProperty("--bg2", hexToRgba(c2, 0.45));
    if (art && bgArtKey !== m.id) {             // refresh faint artwork motifs
      bgArtKey = m.id;
      const src = m.artwork || m.artwork_shiny || "";
      if (!src) { art.innerHTML = ""; return; }
      const s = esc(src);
      art.innerHTML =
        `<img class="bg-hero" src="${s}" alt="" onerror="this.style.display='none'">` +
        `<img class="bg-spot bg-spot-a" src="${s}" alt="" onerror="this.style.display='none'">` +
        `<img class="bg-spot bg-spot-b" src="${s}" alt="" onerror="this.style.display='none'">`;
    }
  }

  function toast(msg, ms = 2600) {
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => toastEl.classList.remove("show"), ms);
  }

  // =========================================================== type loading =
  // Fetch types for a set of ids in batches of 80, cache them, return when done.
  async function ensureTypes(ids) {
    const missing = [];
    for (const id of ids) if (!typeData.has(id)) missing.push(id);
    if (!missing.length) return;
    const batches = [];
    for (let i = 0; i < missing.length; i += 80) batches.push(missing.slice(i, i + 80));
    for (const batch of batches) {
      try {
        const res = await api(`/api/cards?ids=${batch.join(",")}`);
        for (const id of batch) {
          const rec = res[String(id)];
          typeData.set(id, (rec && rec.types) || []);
        }
      } catch (_) {
        for (const id of batch) if (!typeData.has(id)) typeData.set(id, []);
      }
    }
  }

  // hydrate the visible cards' type chips (called from the card observer queue)
  async function hydrateChips() {
    chipTimer = null;
    const ids = [...chipQueue];
    chipQueue.clear();
    if (!ids.length) return;
    await ensureTypes(ids);
    for (const id of ids) {
      const card = cardEls.get(id);
      if (!card) continue;
      const slot = card.querySelector(".card-types");
      if (!slot || slot.dataset.done) continue;
      const types = typeData.get(id) || [];
      slot.innerHTML = types
        .map((t) => `<span class="chip-mini" style="--c:${esc(t.color)}">${esc(t.name)}</span>`)
        .join("");
      slot.dataset.done = "1";
    }
  }

  // ================================================================== boot ==
  async function boot() {
    setStatus("BOOTING…");
    const t0 = Date.now();
    try {
      INDEX = await api("/api/index");
    } catch (e) {
      device.dataset.mode = "grid";
      ensureViewBody();
      renderIdle();
      renderFatal(e);
      return;
    }
    TYPE_COLORS = INDEX.type_colors || {};
    const wait = 850 - (Date.now() - t0);
    if (!REDUCED && wait > 0) await sleep(wait);

    device.dataset.mode = "grid";
    ensureViewBody();
    setStatus("SYSTEM READY");
    buildGridShell();
    route(true);
    window.addEventListener("popstate", () => route(false));
    wireGlobalKeys();
    wireDeck();
  }

  function ensureViewBody() {
    if (viewBody) return;
    const boot = viewEl.querySelector(".boot");
    if (boot) boot.remove();
    viewBody = document.createElement("div");
    viewBody.id = "viewBody";
    viewBody.style.position = "absolute";
    viewBody.style.top = "0";
    viewBody.style.right = "0";
    viewBody.style.bottom = "0";
    viewBody.style.left = "0";
    viewBody.style.zIndex = "1";
    viewEl.appendChild(viewBody);
  }

  // ============================================================ routing =====
  function route(initial) {
    const m = location.pathname.match(/^\/pokemon\/([^/]+)/);
    if (m) {
      openEntry(decodeURIComponent(m[1]), { push: false });
    } else {
      showGrid({ push: false, restore: !initial });
    }
  }
  function go(path) {
    if (location.pathname !== path) history.pushState({}, "", path);
  }

  // ============================================================ GRID MODE ====
  function buildGridShell() {
    device.dataset.mode = "grid";
    renderIdle();
    dataEl.innerHTML = `
      <div class="search-wrap">
        <div class="search-box">
          <span class="ico" aria-hidden="true">⌕</span>
          <input id="q" type="text" autocomplete="off" spellcheck="false"
                 aria-label="Search Pokémon by name or number"
                 placeholder="SEARCH NAME OR Nº…">
          <button class="search-clear" id="qClear" aria-label="Clear search" hidden>✕</button>
          <div class="suggest" id="suggest" role="listbox" hidden></div>
        </div>
      </div>
      <div class="filters" id="filters"></div>
      <div class="grid" id="grid" role="list" aria-label="Pokédex"></div>
      <div class="grid-sentinel" id="sentinel"></div>
      <div class="grid-loading" id="gridLoading" hidden></div>
    `;
    buildFilters();
    wireSearch();

    FILTERED = INDEX.pokemon.slice();
    cursor = 0;
    $("#grid").innerHTML = "";
    cardEls.clear();
    renderNextPage();
    setupScrollObserver();
    setupCardObserver();
    setBackground(null);
    setStatus("SYSTEM READY");
  }

  function buildFilters() {
    const wrap = $("#filters");
    const order = [
      "normal","fire","water","electric","grass","ice","fighting","poison","ground",
      "flying","psychic","bug","rock","ghost","dragon","dark","steel","fairy",
    ];
    let html = `<span class="filter-label">FILTER BY TYPE</span>`;
    html += order
      .map((t) => `<button class="tfilter" data-type="${t}" style="--c:${esc(TYPE_COLORS[t] || "#555")}">${t}</button>`)
      .join("");
    html += `<span class="filter-label" style="margin-top:8px">GENERATION</span>`;
    html += (INDEX.generations || [])
      .map((g) => `<button class="genfilter" data-gen="${g.id}">${esc(g.label)}</button>`)
      .join("");
    html += `<span class="filter-meta" id="count"></span>`;
    wrap.innerHTML = html;

    wrap.querySelectorAll(".tfilter").forEach((b) =>
      b.addEventListener("click", () => {
        const t = b.dataset.type;
        if (activeTypes.has(t)) { activeTypes.delete(t); b.classList.remove("on"); }
        else { activeTypes.add(t); b.classList.add("on"); }
        applyFilters();
      })
    );
    wrap.querySelectorAll(".genfilter").forEach((b) =>
      b.addEventListener("click", () => {
        const g = Number(b.dataset.gen);
        if (activeGen === g) { activeGen = null; b.classList.remove("on"); }
        else {
          activeGen = g;
          wrap.querySelectorAll(".genfilter").forEach((x) => x.classList.remove("on"));
          b.classList.add("on");
        }
        applyFilters();
      })
    );
    updateCount();
  }

  function updateCount() {
    const c = $("#count");
    if (c) c.textContent = `${FILTERED.length} / ${INDEX.count}`;
  }

  async function applyFilters() {
    let list = INDEX.pokemon;
    if (activeGen) list = list.filter((m) => m.gen === activeGen);
    if (term) {
      const scored = [];
      for (const m of list) {
        const s = scoreMatch(term, m);
        if (s > 0) scored.push([s, m]);
      }
      scored.sort((a, b) => b[0] - a[0]);
      list = scored.map((x) => x[1]);
    }
    if (activeTypes.size) {
      const loading = $("#gridLoading");
      if (loading) { loading.hidden = false; loading.textContent = "READING TYPE DATA…"; loading.classList.add("flash"); }
      await ensureTypes(list.map((m) => m.id));
      list = list.filter((m) => {
        const ts = (typeData.get(m.id) || []).map((t) => t.name);
        for (const t of activeTypes) if (ts.includes(t)) return true;
        return false;
      });
      if (loading) { loading.hidden = true; loading.classList.remove("flash"); }
    }
    FILTERED = list;
    cursor = 0;
    $("#grid").innerHTML = "";
    cardEls.clear();
    renderNextPage();
    updateCount();
    dataEl.scrollTop = 0;
  }

  function renderNextPage() {
    const grid = $("#grid");
    if (!grid) return;
    const slice = FILTERED.slice(cursor, cursor + PAGE);
    const frag = document.createDocumentFragment();
    for (const m of slice) frag.appendChild(makeCard(m));
    grid.appendChild(frag);
    cursor += slice.length;
    if (cursor >= FILTERED.length && FILTERED.length === 0) {
      grid.innerHTML = `<div class="empty-state"><span class="big">⌕</span>No Pokémon match those filters.<br>Try clearing a filter or your search.</div>`;
    }
  }

  function makeCard(m) {
    const card = document.createElement("button");
    card.className = "card";
    card.setAttribute("role", "listitem");
    card.dataset.id = m.id;
    card.setAttribute("aria-label", `${m.display}, number ${m.id}`);
    card.innerHTML = `
      <span class="card-num">Nº${String(m.id).padStart(4, "0")}</span>
      ${pixImg(m.id, m.display, "card-img ph", 'loading="lazy"')}
      <span class="card-name">${esc(m.display)}</span>
      <span class="card-types"></span>`;
    const img = card.querySelector("img");
    img.addEventListener("load", () => img.classList.remove("ph"));
    card.addEventListener("click", () => openEntry(m.name, { push: true }));
    card.addEventListener("mouseenter", () => { if (device.dataset.mode === "grid") previewArt(m); });
    cardEls.set(m.id, card);
    if (cardIO) cardIO.observe(card);
    return card;
  }

  function setupScrollObserver() {
    if (scrollIO) scrollIO.disconnect();
    const sentinel = $("#sentinel");
    scrollIO = new IntersectionObserver(
      (entries) => { if (entries.some((e) => e.isIntersecting) && cursor < FILTERED.length) renderNextPage(); },
      { root: dataEl, rootMargin: "600px" }
    );
    if (sentinel) scrollIO.observe(sentinel);
  }

  function setupCardObserver() {
    if (cardIO) cardIO.disconnect();
    cardIO = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          const id = Number(e.target.dataset.id);
          const slot = e.target.querySelector(".card-types");
          if (slot && !slot.dataset.done) { chipQueue.add(id); }
          cardIO.unobserve(e.target);
        }
        if (chipQueue.size && !chipTimer) chipTimer = setTimeout(hydrateChips, 70);
      },
      { root: dataEl, rootMargin: "200px" }
    );
    cardEls.forEach((card) => cardIO.observe(card));
  }

  // ---------- search + autocomplete ----------
  function wireSearch() {
    const input = $("#q");
    const clear = $("#qClear");
    const box = $("#suggest");
    let debounce;

    input.addEventListener("input", () => {
      term = input.value.trim().toLowerCase();
      clear.hidden = !term;
      clearTimeout(debounce);
      debounce = setTimeout(() => { applyFilters(); renderSuggest(); }, 130);
    });
    input.addEventListener("keydown", (e) => {
      const items = box.hidden ? [] : [...box.querySelectorAll(".suggest-item")];
      if (e.key === "ArrowDown" && items.length) {
        e.preventDefault(); suggestIdx = (suggestIdx + 1) % items.length; markSuggest(items);
      } else if (e.key === "ArrowUp" && items.length) {
        e.preventDefault(); suggestIdx = (suggestIdx - 1 + items.length) % items.length; markSuggest(items);
      } else if (e.key === "Enter") {
        const pick = items[suggestIdx] || items[0];
        if (pick) { openEntry(pick.dataset.name, { push: true }); hideSuggest(); input.blur(); }
        else if (FILTERED[0]) { openEntry(FILTERED[0].name, { push: true }); input.blur(); }
      } else if (e.key === "Escape") {
        if (!box.hidden) hideSuggest();
        else { input.value = ""; term = ""; clear.hidden = true; applyFilters(); }
      }
    });
    clear.addEventListener("click", () => {
      input.value = ""; term = ""; clear.hidden = true; hideSuggest(); applyFilters(); input.focus();
    });
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".search-box")) hideSuggest();
    });
  }

  function renderSuggest() {
    const box = $("#suggest");
    if (!term) return hideSuggest();
    const top = FILTERED.slice(0, 7);
    if (!top.length) return hideSuggest();
    suggestIdx = -1;
    box.innerHTML = top
      .map(
        (m) => `<div class="suggest-item" role="option" data-name="${esc(m.name)}">
          <img src="${esc(m.sprite)}" alt="" onerror="this.style.visibility='hidden'">
          <span class="suggest-num">Nº${String(m.id).padStart(4, "0")}</span>
          <span class="suggest-name">${esc(m.display)}</span>
        </div>`
      )
      .join("");
    box.hidden = false;
    box.querySelectorAll(".suggest-item").forEach((it) =>
      it.addEventListener("click", () => { openEntry(it.dataset.name, { push: true }); hideSuggest(); })
    );
  }
  function markSuggest(items) {
    items.forEach((it, i) => it.classList.toggle("active", i === suggestIdx));
    if (items[suggestIdx]) items[suggestIdx].scrollIntoView({ block: "nearest" });
  }
  function hideSuggest() { const b = $("#suggest"); if (b) { b.hidden = true; b.innerHTML = ""; } suggestIdx = -1; }

  // ---------- fuzzy matcher ----------
  function scoreMatch(q, m) {
    const n = m.name;
    if (/^\d+$/.test(q)) {
      const id = String(m.id);
      if (id === q) return 1000;
      if (id.startsWith(q)) return 700 - (id.length - q.length);
      return 0;
    }
    if (n === q) return 1000;
    if (n.startsWith(q)) return 850 - (n.length - q.length);
    const idx = n.indexOf(q);
    if (idx >= 0) return 650 - idx - (n.length - q.length) * 0.1;
    // subsequence
    let i = 0;
    for (let c = 0; c < n.length && i < q.length; c++) if (n[c] === q[i]) i++;
    if (i === q.length) return 360 - n.length * 0.2;
    // typo tolerance on the leading slice
    const d = lev(q, n.slice(0, q.length + 2));
    if (d <= 2) return 240 - d * 60;
    return 0;
  }
  function lev(a, b) {
    const m = a.length, n = b.length;
    if (!m) return n; if (!n) return m;
    let prev = Array.from({ length: n + 1 }, (_, i) => i);
    let cur = new Array(n + 1);
    for (let i = 1; i <= m; i++) {
      cur[0] = i;
      for (let j = 1; j <= n; j++) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
      }
      [prev, cur] = [cur, prev];
    }
    return prev[n];
  }

  // ---------- view-screen previews (grid hover + idle) ----------
  function renderIdle() {
    if (!viewBody) return;
    viewBody.innerHTML = `
      <div class="view-grid-idle">
        <div class="view-orb view-orb-glow" aria-hidden="true"></div>
        <div class="view-idle-title">SELECT A POKÉMON</div>
        <div class="view-idle-sub">Browse the grid or search by name or №. Tap a card to open its entry, then flip through the dex with ◀ ▶.</div>
        <div class="view-count">${INDEX ? INDEX.count + " ENTRIES ONLINE" : ""}</div>
      </div>`;
  }
  let previewTimer = null;
  function previewArt(m) {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(() => {
      if (device.dataset.mode !== "grid" || !viewBody) return;
      const color = (typeData.get(m.id) && typeData.get(m.id)[0] && typeData.get(m.id)[0].color) || "rgba(91,232,168,.35)";
      viewBody.innerHTML = `
        <div class="view-art" style="--halo:${esc(color)}">
          <div class="halo" aria-hidden="true"></div>
          <img src="${esc(m.artwork)}" alt="${esc(m.display)}" onerror="this.onerror=null;this.src='${PLACEHOLDER}'">
        </div>
        <div class="view-dexmark">Nº${String(m.id).padStart(4, "0")}</div>`;
    }, 40);
  }

  function showGrid({ push = true, restore = false } = {}) {
    if (push) go("/");
    device.dataset.mode = "grid";
    current = null;
    setBackground(null);
    setStatus("SYSTEM READY");
    if (!$("#grid")) buildGridShell();
    else { renderIdle(); }
  }

  // ============================================================ ENTRY MODE ===
  async function openEntry(key, { push = true } = {}) {
    hideSuggest();
    if (push) go(`/pokemon/${encodeURIComponent(key)}`);
    device.dataset.mode = "entry";
    isShiny = false;
    activeTab = "stats";
    setStatus("LOADING…");
    renderEntrySkeleton();

    if (inflightEntry) inflightEntry.abort();
    inflightEntry = new AbortController();
    let mon;
    try {
      mon = await api(`/api/pokemon/${encodeURIComponent(key.toLowerCase())}`, { signal: inflightEntry.signal });
    } catch (e) {
      if (e.name === "AbortError") return;
      renderEntryError(e, key);
      setStatus("ERROR");
      return;
    }
    current = mon;
    renderView();
    renderData();
    dataEl.scrollTop = 0;
    setStatus(`Nº${String(dexId()).padStart(4, "0")}`);
  }

  function dexId() {
    if (!current) return 0;
    const base = (current.forms || []).find((f) => f.is_default);
    return (base && base.id) || current.id;
  }

  function renderEntrySkeleton() {
    if (viewBody)
      viewBody.innerHTML = `<div class="view-grid-idle"><div class="view-orb" aria-hidden="true"></div>
        <div class="view-idle-title" style="font-size:10px">LOADING ENTRY…</div></div>`;
    dataEl.innerHTML = `<div class="skeleton">
      ${'<div class="sk-line" style="width:62%"></div>'}
      ${'<div class="sk-line" style="width:40%"></div>'}
      ${'<div class="sk-line" style="width:90%"></div>'}
      ${'<div class="sk-line" style="width:80%"></div>'}
      ${'<div class="sk-line" style="width:86%"></div>'}
      ${'<div class="sk-line" style="width:70%"></div>'}
    </div>`;
  }

  function renderEntryError(e, key) {
    if (viewBody) renderIdle();
    const is404 = e.status === 404;
    dataEl.innerHTML = `
      <div class="error-state">
        <span class="big">${is404 ? "🔍" : "⚠"}</span>
        <div class="msg">${is404 ? `No entry found for “${esc(key)}”.` : esc(e.message)}</div>
        <div class="hint">${esc(e.hint || (is404 ? "Check the spelling, or pick one from the dex." : "The data device could not reach PokéAPI."))}</div>
        <button class="retry-btn" id="retry">${is404 ? "BACK TO DEX" : "RETRY"}</button>
      </div>`;
    $("#retry").addEventListener("click", () => (is404 ? showGrid({ push: true }) : openEntry(key, { push: false })));
  }

  // ---------- view screen (artwork) ----------
  function renderView() {
    if (!viewBody) return;
    const m = current;
    const color = (m.types[0] && m.types[0].color) || "rgba(91,232,168,.35)";
    setBackground(m);
    const src = isShiny ? m.artwork_shiny : m.artwork;
    viewBody.innerHTML = `
      <button class="shiny-toggle" id="shiny" aria-pressed="${isShiny}" title="Toggle shiny">
        <span class="star">✦</span><span>${isShiny ? "SHINY" : "NORMAL"}</span>
      </button>
      <div class="view-art" id="art" style="--halo:${esc(color)}">
        <div class="halo" aria-hidden="true"></div>
        <img id="artImg" src="${esc(src)}" alt="${esc(m.display)}${isShiny ? " (shiny)" : ""}"
             onerror="this.onerror=null;this.src='${PLACEHOLDER}'">
      </div>
      <div class="view-dexmark">Nº${String(dexId()).padStart(4, "0")}</div>`;
    $("#shiny").addEventListener("click", toggleShiny);
  }

  function toggleShiny() {
    isShiny = !isShiny;
    const btn = $("#shiny");
    const img = $("#artImg");
    btn.setAttribute("aria-pressed", isShiny);
    btn.querySelector("span:last-child").textContent = isShiny ? "SHINY" : "NORMAL";
    const art = $("#art");
    if (art) art.classList.add("is-swapping");
    if (!REDUCED) burstSparkles(art);
    setTimeout(() => {
      if (img) img.src = isShiny ? current.artwork_shiny : current.artwork;
      if (art) art.classList.remove("is-swapping");
    }, REDUCED ? 0 : 150);
  }

  function burstSparkles(host) {
    if (!host) return;
    for (let i = 0; i < 10; i++) {
      const s = document.createElement("span");
      s.className = "sparkle";
      const ang = Math.random() * Math.PI * 2, dist = 40 + Math.random() * 70;
      s.style.setProperty("--dx", `${Math.cos(ang) * dist}px`);
      s.style.setProperty("--dy", `${Math.sin(ang) * dist}px`);
      s.style.left = "50%"; s.style.top = "46%";
      host.appendChild(s);
      setTimeout(() => s.remove(), 750);
    }
  }

  // ---------- data screen (header + tabs) ----------
  const TABS = [
    ["stats", "Stats"], ["matchups", "Matchups"], ["abilities", "Abilities"],
    ["moves", "Moves"], ["evolution", "Evolution"], ["bio", "Bio"],
    ["locations", "Locations"],
  ];

  function renderData() {
    const m = current;
    const types = m.types
      .map((t) => `<span class="chip" style="--c:${esc(t.color)}">${esc(t.name)}</span>`)
      .join("");
    const tabs = TABS.map(
      ([id, label]) =>
        `<button class="tab" role="tab" data-tab="${id}" aria-selected="${id === activeTab}">${label}</button>`
    ).join("");

    dataEl.innerHTML = `
      <div class="entry-head">
        <div class="entry-meta-row">
          <span class="entry-num">Nº${String(dexId()).padStart(4, "0")}</span>
          <span class="entry-name">${esc(m.display)}</span>
          <span class="entry-gen">${esc(m.generation_label || "")}</span>
        </div>
        ${m.genus ? `<div class="entry-genus">${esc(m.genus)}</div>` : ""}
        <div class="entry-types">${types}</div>
      </div>
      <div class="tabs" role="tablist">${tabs}</div>
      <div class="panel-body" id="pane"></div>`;

    dataEl.querySelectorAll(".tab").forEach((b) =>
      b.addEventListener("click", () => selectTab(b.dataset.tab))
    );
    renderPane();
  }

  function selectTab(id) {
    if (id === activeTab) return;
    activeTab = id;
    dataEl.querySelectorAll(".tab").forEach((b) =>
      b.setAttribute("aria-selected", b.dataset.tab === id)
    );
    renderPane();
    const pane = $("#pane");
    if (pane) pane.scrollIntoView({ block: "nearest" });
  }

  function renderPane() {
    const pane = $("#pane");
    if (!pane) return;
    const m = current;
    let html = "";
    switch (activeTab) {
      case "stats":     html = paneStats(m); break;
      case "matchups":  html = paneMatchups(m); break;
      case "abilities": html = paneAbilities(m); break;
      case "moves":     html = paneMoves(m); break;
      case "evolution": html = paneEvolution(m); break;
      case "bio":       html = paneBio(m); break;
      case "locations": html = paneLocations(m); break;
    }
    pane.innerHTML = `<div class="tabpane">${html}</div>`;
    afterPane();
  }

  // ----- Stats -----
  // colour each bar by which stat it is (HP/Atk/Def/SpA/SpD/Spe)
  const STAT_COLORS = {
    "hp":              ["#7be8a8", "#3fce86"],  // green
    "attack":          ["#ff8a6b", "#ef4d3c"],  // red
    "defense":         ["#ffd66b", "#f0b02b"],  // amber / gold
    "special-attack":  ["#7fb6ff", "#4f8cff"],  // blue
    "special-defense": ["#5fe0cf", "#2bbfb0"],  // teal
    "speed":           ["#c79bff", "#a05bff"],  // purple
  };
  function statColors(name) { return STAT_COLORS[name] || ["#9fe6c8", "#5be8a8"]; }
  function paneStats(m) {
    const fl = (m.flavor && m.flavor[0]) || null;
    const rows = m.stats
      .map((s) => {
        // scale so bars read as full: eased curve against a ~200 reference, clamped.
        const pct = Math.max(6, Math.min(100, Math.pow(Math.min(s.value, 200) / 200, 0.72) * 100));
        const [c1, c2] = statColors(s.name);
        return `<div class="stat-row">
          <span class="stat-label">${esc(s.label)}</span>
          <span class="stat-val">${s.value}</span>
          <span class="stat-track"><span class="stat-fill" data-w="${pct.toFixed(1)}" style="--sc1:${c1};--sc2:${c2}"></span></span>
        </div>`;
      })
      .join("");
    return `
      ${fl ? `<div class="flavor">${esc(fl.text)}<cite>— ${esc(fl.version)} edition</cite></div>` : ""}
      <div class="sect"><span class="tick">▸</span> Base Stats</div>
      ${rows}
      <div class="stat-total"><span class="lbl">TOTAL</span><span class="num">${m.stat_total}</span></div>`;
  }

  // ----- Matchups: full 18-type defensive grid -----
  const TYPE_ORDER = [
    "normal", "fire", "water", "electric", "grass", "ice",
    "fighting", "poison", "ground", "flying", "psychic", "bug",
    "rock", "ghost", "dragon", "dark", "steel", "fairy",
  ];
  function multInfo(x) {
    if (x === 0) return { label: "0", cls: "m0" };
    if (x >= 4) return { label: "×4", cls: "m4" };
    if (x > 1) return { label: "×2", cls: "m2" };
    if (x <= 0.25) return { label: "×¼", cls: "mq" };
    if (x < 1) return { label: "×½", cls: "mh" };
    return { label: "×1", cls: "m1" };
  }
  function paneMatchups(m) {
    const mult = (m.matchups && m.matchups.multipliers) || {};
    const cells = TYPE_ORDER.map((t) => {
      const info = multInfo(mult[t] == null ? 1 : mult[t]);
      const color = TYPE_COLORS[t] || "#888";
      return `<div class="tc ${info.cls}">
        <span class="tc-type" style="--c:${esc(color)}">${esc(t)}</span>
        <span class="tc-x">${info.label}</span>
      </div>`;
    }).join("");
    return `<div class="sect"><span class="tick">▸</span> Type Defenses</div>
      <div class="tchart">${cells}</div>
      <div class="tchart-key">
        <span class="k m4">×4</span><span class="k m2">×2</span>
        <span class="k m1">×1</span><span class="k mh">×½</span>
        <span class="k mq">×¼</span><span class="k m0">0</span>
        <span class="k-note">damage this Pokémon takes from each attacking type</span>
      </div>`;
  }

  // ----- Abilities -----
  function paneAbilities(m) {
    let html = `<div class="sect"><span class="tick">▸</span> Abilities</div>`;
    html += (m.abilities || [])
      .map(
        (a) => `<div class="ability">
          <div class="ability-top">
            <span class="ability-name">${esc(a.display)}</span>
            ${a.hidden ? `<span class="badge-hidden">Hidden</span>` : ""}
          </div>
          <div class="ability-effect">${esc(a.effect)}</div>
        </div>`
      )
      .join("");
    return html;
  }

  // ----- Moves -----
  const MOVE_METHODS = [
    ["level-up", "Level-Up"], ["machine", "TM / HM"], ["egg", "Egg"], ["tutor", "Tutor"],
  ];
  let moveMethod = "level-up";
  function paneMoves(m) {
    const groups = m.moves || {};
    const avail = MOVE_METHODS.filter(([k]) => (groups[k] || []).length);
    if (!avail.length) return `<div class="empty-state"><span class="big">⚔</span>No recorded moves for this Pokémon.</div>`;
    if (!groups[moveMethod] || !groups[moveMethod].length) moveMethod = avail[0][0];
    const btns = avail
      .map(
        ([k, label]) =>
          `<button class="mm-btn ${k === moveMethod ? "on" : ""}" data-method="${k}">${label}<span class="n">${groups[k].length}</span></button>`
      )
      .join("");
    const list = groups[moveMethod]
      .map((mv) => {
        const lv = moveMethod === "level-up" ? `<span class="move-lv">Lv ${mv.level}</span>` : `<span class="move-lv">—</span>`;
        return `<div class="move" data-name="${esc(mv.name)}">
          <button class="move-row">
            ${lv}
            <span class="move-name">${esc(mv.display)}</span>
            <span class="move-caret">▸</span>
          </button>
          <div class="move-detail"></div>
        </div>`;
      })
      .join("");
    return `<div class="sect"><span class="tick">▸</span> Move Pool</div>
      <div class="move-methods">${btns}</div>
      <div class="move-list">${list}</div>`;
  }

  async function expandMove(moveEl) {
    const detail = moveEl.querySelector(".move-detail");
    const open = moveEl.classList.toggle("open");
    if (!open) return;
    if (detail.dataset.loaded) return;
    detail.classList.add("loading");
    detail.textContent = "READING DATA…";
    try {
      const d = await api(`/api/move/${encodeURIComponent(moveEl.dataset.name)}`);
      detail.classList.remove("loading");
      detail.dataset.loaded = "1";
      const cat = (d.category || "status").toLowerCase();
      detail.innerHTML = `
        <div class="move-stats">
          <span class="ms"><span class="k">TYPE</span><span class="chip-mini" style="--c:${esc(d.type_color)}">${esc(d.type)}</span></span>
          <span class="ms"><span class="k">CLASS</span><span class="move-cat cat-${cat}">${esc(cat)}</span></span>
          <span class="ms"><span class="k">POWER</span><span class="v">${d.power ?? "—"}</span></span>
          <span class="ms"><span class="k">ACC</span><span class="v">${d.accuracy ?? "—"}</span></span>
          <span class="ms"><span class="k">PP</span><span class="v">${d.pp ?? "—"}</span></span>
        </div>
        ${d.effect ? `<div class="move-effect">${esc(d.effect)}</div>` : ""}`;
    } catch (_) {
      detail.classList.remove("loading");
      detail.innerHTML = `<div class="move-effect">Could not load move data.</div>`;
    }
  }

  // ----- Evolution (tree + every form) -----
  function paneEvolution(m) {
    const evo = m.evolution;
    let html = `<div class="sect"><span class="tick">▸</span> Evolution</div>`;
    if (!evo || !evo.children || !evo.children.length) {
      html += `<div class="evo-none">${esc(m.display)} does not evolve.</div>`;
    } else {
      html += `<div class="evo">${renderEvoChain(evo)}</div>`;
    }
    // Every form/variety (regional, Mega, Gigantamax, alt) — the merged former "Forms" tab.
    const forms = m.forms || [];
    if (forms.length > 1) {
      html += `<div class="sect"><span class="tick">▸</span> Forms &amp; Variants</div>
        <div class="forms-grid">${forms.map((f) => formCard(f, m)).join("")}</div>`;
    }
    return html;
  }

  function formCard(f, m) {
    const cur = m.name;
    const cat = f.category || "alt";
    const stone = f.item
      ? `<span class="form-item" title="${esc(f.item.display)}">
           <img src="${esc(f.item.sprite)}" alt="${esc(f.item.display)}" onerror="this.style.display='none'">
           <span class="fi-name">${esc(f.item.display)}</span>
         </span>`
      : "";
    const band = cat === "gmax" ? `<span class="gmax-band">Gigantamax</span>` : "";
    return `<button class="form-chip ${f.name === cur ? "current" : ""}" data-form="${esc(f.name)}">
      <span class="form-art">${pixImg(f.id, f.label + " " + m.display, "")}${band}</span>
      <span class="nm">${esc(f.label)}</span>
      <span class="cat cat-${cat}">${esc(cat)}</span>
      ${stone}
    </button>`;
  }

  // linear chains render as stage → arrow(trigger) → stage; a branch point fans out.
  function renderEvoChain(node) {
    const cur = dexId();
    let html = stageHTML(node, cur);
    let n = node;
    while (n.children && n.children.length === 1) {
      const next = n.children[0];
      html += arrowHTML(next);
      html += stageHTML(next, cur);
      n = next;
    }
    if (n.children && n.children.length > 1) {
      html += `<div class="evo-branches">`;
      html += n.children
        .map(
          (c) => `<div class="evo-branch">${arrowHTML(c)}${stageHTML(c, cur)}${
            c.children && c.children.length ? renderTailInline(c) : ""
          }</div>`
        )
        .join("");
      html += `</div>`;
    }
    return html;
  }
  function renderTailInline(node) {
    let html = "", n = node;
    while (n.children && n.children.length >= 1) {
      const next = n.children[0];
      html += arrowHTML(next) + stageHTML(next, dexId());
      n = next;
    }
    return html;
  }
  function stageHTML(node, curId) {
    const isCur = node.id === curId;
    return `<button class="evo-stage ${isCur ? "current" : ""}" data-name="${esc(node.name)}">
      ${pixImg(node.id, node.display, "")}
      <span class="nm">${esc(node.display)}</span>
    </button>`;
  }
  function arrowHTML(node) {
    const trig = (node && node.trigger) || "";
    const item = node && node.trigger_item
      ? `<img class="evo-item" src="${esc(item_sprite_url(node.trigger_item))}" alt="${esc(node.trigger_item)}" onerror="this.style.display='none'">`
      : "";
    return `<div class="evo-arrow"><div class="ln"></div>${item}<div class="trg">${esc(trig)}</div></div>`;
  }
  function item_sprite_url(slug) {
    return `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/${slug}.png`;
  }

  // ----- Bio -----
  function paneBio(m) {
    const b = m.bio || {};
    const tile = (k, v) => `<div class="bio-tile"><div class="k">${k}</div><div class="v">${v}</div></div>`;
    let gender;
    if (b.gender && b.gender.genderless) gender = `<div class="bio-tile"><div class="k">Gender</div><div class="v">Genderless</div></div>`;
    else if (b.gender)
      gender = `<div class="bio-tile"><div class="k">Gender Ratio</div>
        <div class="v"><span class="sub">♀ ${b.gender.female}% · ♂ ${b.gender.male}%</span></div>
        <div class="gender-bar"><span class="f" style="width:${b.gender.female}%"></span><span class="m" style="width:${b.gender.male}%"></span></div>
      </div>`;
    else gender = "";

    let html = `<div class="sect"><span class="tick">▸</span> Bio Data</div><div class="bio-grid">`;
    html += tile("Height", `${b.height_m} m <span class="sub">(${esc(b.height_ft)})</span>`);
    html += tile("Weight", `${b.weight_kg} kg <span class="sub">(${b.weight_lb} lb)</span>`);
    html += gender;
    if (b.egg_groups && b.egg_groups.length) html += tile("Egg Groups", esc(b.egg_groups.join(", ")));
    if (b.capture_rate != null) html += tile("Capture Rate", `${b.capture_rate} <span class="sub">/ 255</span>`);
    if (b.base_happiness != null) html += tile("Base Happiness", String(b.base_happiness));
    if (b.growth_rate) html += tile("Growth Rate", esc(b.growth_rate));
    if (b.base_exp != null) html += tile("Base EXP", String(b.base_exp));
    if (b.held_items && b.held_items.length) html += tile("Held Items", esc(b.held_items.join(", ")));
    html += `</div>`;
    if (b.is_legendary) html += `<div class="badge-rare">Legendary</div>`;
    if (b.is_mythical) html += `<div class="badge-rare">Mythical</div>`;
    return html;
  }

  // ----- Locations: click a game to expand -----
  function paneLocations(m) {
    const enc = m.encounters || [];
    if (!enc.length)
      return `<div class="sect"><span class="tick">▸</span> Encounters</div>
        <div class="empty-state"><span class="big">🗺</span>Not found in the wild.<br>Likely obtained through evolution, breeding, trade, or special events.</div>`;
    let html = `<div class="sect"><span class="tick">▸</span> Wild Encounters</div>
      <div class="loc-hint">Tap a game to see where, how, and how often.</div>`;
    html += enc
      .map((g, i) => {
        const areas = g.areas
          .map((a) => {
            const lv =
              a.min_level != null
                ? `<span class="la-tag">Lv ${a.min_level}${a.max_level && a.max_level !== a.min_level ? "–" + a.max_level : ""}</span>`
                : "";
            const methods = a.methods.length ? `<span class="la-tag la-method">${esc(a.methods.join(", "))}</span>` : "";
            const conds = a.conditions.map((c) => `<span class="la-cond">${esc(c)}</span>`).join("");
            const pc = a.chance != null ? `<span class="la-pc">${a.chance}%</span>` : "";
            return `<div class="locarea">
              <div class="la-top"><span class="la-name">${esc(a.area)}</span>${pc}</div>
              <div class="la-meta">${methods}${lv}${conds}</div>
            </div>`;
          })
          .join("");
        return `<div class="locgame">
          <button class="locgame-head" data-loc="${i}" aria-expanded="false">
            <span class="lg-name">${esc(g.game)}</span>
            <span class="lg-count">${g.areas.length} area${g.areas.length === 1 ? "" : "s"}</span>
            <span class="lg-caret" aria-hidden="true">▸</span>
          </button>
          <div class="locgame-body" hidden>${areas}</div>
        </div>`;
      })
      .join("");
    return html;
  }

  // ---------- wire up after a pane renders ----------
  function afterPane() {
    // animate stat bars
    const fills = dataEl.querySelectorAll(".stat-fill[data-w]");
    if (fills.length) {
      requestAnimationFrame(() =>
        fills.forEach((f) => { f.style.width = f.dataset.w + "%"; })
      );
    }
    // move method switches + row expanders
    dataEl.querySelectorAll(".mm-btn").forEach((b) =>
      b.addEventListener("click", () => { moveMethod = b.dataset.method; renderPane(); })
    );
    dataEl.querySelectorAll(".move").forEach((mv) => {
      const row = mv.querySelector(".move-row");
      row.addEventListener("click", () => expandMove(mv));
    });
    // evolution / special-form / form navigation
    dataEl.querySelectorAll("[data-name]").forEach((elm) => {
      if (elm.classList.contains("evo-stage"))
        elm.addEventListener("click", () => openEntry(elm.dataset.name, { push: true }));
    });
    dataEl.querySelectorAll("[data-form]").forEach((elm) =>
      elm.addEventListener("click", () => openEntry(elm.dataset.form, { push: true }))
    );
    // locations: expand/collapse a game
    dataEl.querySelectorAll(".locgame-head").forEach((btn) =>
      btn.addEventListener("click", () => {
        const body = btn.parentElement.querySelector(".locgame-body");
        const open = btn.getAttribute("aria-expanded") === "true";
        btn.setAttribute("aria-expanded", String(!open));
        if (body) body.hidden = open;
      })
    );
  }

  // ============================================================ navigation ===
  function neighbour(delta) {
    if (!INDEX || !current) return;
    const id = dexId();
    const list = INDEX.pokemon;
    let i = list.findIndex((m) => m.id === id);
    if (i < 0) return;
    i = (i + delta + list.length) % list.length;
    openEntry(list[i].name, { push: true });
  }

  function wireDeck() {
    const dpad = $("#dpad");
    if (dpad)
      dpad.querySelectorAll(".dpad-arm").forEach((arm) =>
        arm.addEventListener("click", (e) => {
          e.stopPropagation();
          const dir = arm.dataset.dir;
          if (device.dataset.mode === "entry") {
            if (dir === "left") neighbour(-1);
            else if (dir === "right") neighbour(1);
            else if (dir === "up") dataEl.scrollBy({ top: -160, behavior: REDUCED ? "auto" : "smooth" });
            else if (dir === "down") dataEl.scrollBy({ top: 160, behavior: REDUCED ? "auto" : "smooth" });
          } else {
            if (dir === "up") dataEl.scrollBy({ top: -240, behavior: REDUCED ? "auto" : "smooth" });
            else if (dir === "down") dataEl.scrollBy({ top: 240, behavior: REDUCED ? "auto" : "smooth" });
          }
        })
      );
    const home = $("#btnHome");
    if (home) home.addEventListener("click", () => showGrid({ push: true }));
  }

  function wireGlobalKeys() {
    document.addEventListener("keydown", (e) => {
      const typing = /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName);
      if (e.key === "/" && !typing) {
        const q = $("#q");
        if (q) { e.preventDefault(); q.focus(); }
      } else if (e.key === "Escape" && device.dataset.mode === "entry") {
        showGrid({ push: true });
      } else if (device.dataset.mode === "entry" && !typing) {
        if (e.key === "ArrowLeft") { e.preventDefault(); neighbour(-1); }
        else if (e.key === "ArrowRight") { e.preventDefault(); neighbour(1); }
      }
    });
  }

  // ------------------------------------------------------------------- start -
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
