/* Metlink departure board. Stops are picked in the card, shown as coloured chips, and remembered per browser. */
(() => {
"use strict";
const WS = "metlink_explorer/";
const STORE_KEY = "metlink_explorer_board:";
const MAX_STOPS = 8;
const PALETTE = ["#e53935", "#fb8c00", "#fbc02d", "#43a047", "#1e88e5", "#3949ab", "#8e24aa", "#00acc1"];

let stopsCache;
const loadStops = (hass) => (stopsCache ||= hass.callWS({ type: WS + "stops" }).catch((e) => { stopsCache = undefined; throw e; }));

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const clock = (ts) => {
  const d = new Date(ts * 1000);
  const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return d.toDateString() === new Date().toDateString() ? time : `${d.toLocaleDateString([], { weekday: "short" })} ${time}`;
};
const cssColor = (c, fallback) => (/^#[0-9a-f]{6}$/i.test(c || "") ? c : fallback);
const textOn = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.4 ? "#000" : "#fff";
};
const byName = (a, b) => String(a.name).localeCompare(String(b.name), undefined, { numeric: true });

class MetlinkDepartureBoardCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._key = STORE_KEY + (this._config.id || "default");
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(this._key) || "{}"); } catch (_) { /* ignore */ }
    let stops = Array.isArray(saved.stops) ? saved.stops : [];
    if (!stops.length && saved.stopId) stops = [{ id: saved.stopId, name: saved.stopName || saved.stopId, towards: saved.towards || "" }];
    if (!stops.length && this._config.stop_id) stops = [{ id: this._config.stop_id, name: this._config.stop_id, towards: this._config.towards || "" }];
    this._sel = { stops: stops.slice(0, MAX_STOPS).map((s, i) => ({ id: s.id, name: s.name || s.id, towards: s.towards || "", color: cssColor(s.color, PALETTE[i % PALETTE.length]) })), height: Number(saved.height) > 0 ? Number(saved.height) : 0, routeColors: saved.routeColors && typeof saved.routeColors === "object" ? saved.routeColors : {} };
    this._limit = this._config.limit || 10;
    const h = this._config.height;
    this._height = h ? (typeof h === "number" || /^\d+(\.\d+)?$/.test(String(h)) ? `${h}px` : String(h)) : "";
    if (this._built) { this._applyHeight(); this._refresh(); }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._build();
  }

  connectedCallback() {
    this.style.display = "block";
    this._tick = setInterval(() => this._renderRows(), 30000);
    if (this._built) { document.addEventListener("pointerup", this._onUp); this._subscribe(); }
  }

  disconnectedCallback() {
    clearInterval(this._tick);
    document.removeEventListener("pointerup", this._onUp);
    this._unsubscribe();
  }

  getCardSize() { return 6; }
  getGridOptions() { return { columns: 12, rows: "auto", min_columns: 3 }; }
  static getStubConfig() { return { limit: 10 }; }

  _build() {
    this._built = true;
    this.innerHTML = `
      <div class="mx-card" style="background:var(--ha-card-background,var(--card-background-color,#fff));border-radius:var(--ha-card-border-radius,12px);box-shadow:var(--ha-card-box-shadow,none);border:var(--ha-card-border-width,1px) solid var(--ha-card-border-color,var(--divider-color));color:var(--primary-text-color);overflow:hidden;resize:vertical;min-height:160px;display:flex;flex-direction:column;box-sizing:border-box">
        <style>
          .mx{padding:12px 16px;display:flex;flex-direction:column;min-height:0;flex:1}.mx input[type=search],.mx select{width:100%;box-sizing:border-box;padding:8px;margin:4px 0;border:1px solid var(--divider-color);border-radius:6px;background:var(--card-background-color);color:var(--primary-text-color)}
          .mx .hits button{display:block;width:100%;text-align:left;padding:6px 8px;border:0;background:none;color:var(--primary-text-color);cursor:pointer}
          .mx .hits button:hover{background:var(--secondary-background-color)}
          .mx .chips{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0}
          .mx .chip{display:inline-flex;align-items:center;gap:4px;padding:2px 4px 2px 10px;border-radius:14px;font-weight:600;font-size:.9em}
          .mx .chip .nm{position:relative;cursor:pointer}.mx .chip input{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer;padding:0;border:0}
          .mx .chip button{border:0;background:none;color:inherit;cursor:pointer;font-size:1em;padding:0 4px}
          .mx .tw{display:flex;align-items:center;gap:6px}.mx .tw i{flex:none;width:10px;height:10px;border-radius:50%}
          .mx .body{overflow-y:auto;overflow-x:hidden;flex:1;min-height:0}
          .mx .grp{margin-top:10px}.mx .gh{display:flex;align-items:center;gap:8px;font-weight:600;margin-bottom:4px}
          .mx .badge{position:relative;display:inline-block;min-width:2.2em;text-align:center;padding:2px 6px;border-radius:4px;font-weight:600}
          .mx .dep{display:flex;align-items:center;gap:8px;padding:5px 10px;margin:2px 0;border-radius:6px;color:#fff;text-shadow:0 0 3px rgba(0,0,0,.7)}
          .mx .dep .st{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
          .mx .dep .when{text-align:right;white-space:nowrap}
          .mx .badge input{position:absolute;inset:0;width:100%;height:100%;opacity:0;padding:0;border:0;cursor:pointer}.mx .late,.mx .early{padding:0 6px;border-radius:8px;background:rgba(0,0,0,.65);font-weight:600}.mx .late{color:#ff8a80}.mx .early{color:#80d8ff}.mx .gone{text-decoration:line-through;opacity:.6}.mx .muted{color:var(--secondary-text-color)}
        </style>
        <div class="mx">
          <input class="search" type="search" placeholder="Add a stop. Search by name or number…" autocomplete="off">
          <div class="hits"></div>
          <div class="chips"></div>
          <div class="tws"></div>
          <div class="body"></div>
        </div>
      </div>`;
    const q = (s) => this.querySelector(s);
    this._el = { card: q(".mx-card"), search: q(".search"), hits: q(".hits"), chips: q(".chips"), tws: q(".tws"), body: q(".body") };
    this._el.search.addEventListener("input", () => this._search());
    this._applyHeight();
    this._el.card.addEventListener("pointerdown", (e) => {
      if (this._height || e.target.closest("input,select,button")) return;
      this._el.card.style.maxHeight = "none";
      this._el.card.style.height = `${this._el.card.offsetHeight}px`;
      this._dragging = true;
    });
    this._onUp = () => {
      if (!this._dragging) return;
      this._dragging = false;
      this._sel.height = Math.round(this._el.card.offsetHeight);
      this._save();
    };
    document.addEventListener("pointerup", this._onUp);
    this._refresh();
  }

  _applyHeight() {
    const px = this._height ? 0 : this._sel.height;
    this._el.card.style.height = this._height || (px ? `${px}px` : "");
    this._el.card.style.maxHeight = this._height || px ? "none" : "70vh";
  }

  _save() {
    try { localStorage.setItem(this._key, JSON.stringify(this._sel)); } catch (_) { /* private mode */ }
  }

  _mapColors() {
    try {
      const m = JSON.parse(localStorage.getItem("metlink_explorer_map:" + (this._config.map_id || "default")) || "{}");
      return new Map((m.routes || []).filter((r) => /^#[0-9a-f]{6}$/i.test(r.color || "")).map((r) => [String(r.id), r.color]));
    } catch (_) { return new Map(); }
  }

  _freeColor() {
    const used = new Set(this._sel.stops.map((s) => s.color));
    return PALETTE.find((c) => !used.has(c)) || PALETTE[this._sel.stops.length % PALETTE.length];
  }

  async _search() {
    const text = this._el.search.value.trim().toLowerCase();
    if (text.length < 2) { this._el.hits.innerHTML = ""; return; }
    try {
      const stops = await loadStops(this._hass);
      const hits = stops.filter((s) => s.name.toLowerCase().includes(text) || s.stop_ids.some((i) => i.startsWith(text))).slice(0, 12);
      this._el.hits.innerHTML = hits.map((s) => `<button data-id="${esc(s.id)}" data-name="${esc(s.name)}">${esc(s.name)} <span class="muted">${esc(s.modes.join(", "))} · ${esc(s.id)}</span></button>`).join("") || `<div class="muted">No stops found</div>`;
      this._el.hits.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
        this._el.search.value = "";
        this._el.hits.innerHTML = "";
        if (this._sel.stops.some((s) => s.id === b.dataset.id)) return;
        if (this._sel.stops.length >= MAX_STOPS) { this._el.hits.innerHTML = `<div class="muted">At most ${MAX_STOPS} stops. Remove one first.</div>`; return; }
        this._sel.stops.push({ id: b.dataset.id, name: b.dataset.name, towards: "", color: this._freeColor() });
        this._save();
        this._refresh();
      }));
    } catch (err) {
      this._el.hits.innerHTML = `<div class="muted">Stops are not available yet. The timetable is still downloading.</div>`;
    }
  }

  _renderChips() {
    const stops = [...this._sel.stops].sort(byName);
    this._el.chips.innerHTML = stops.map((s) => `<span class="chip" style="background:${esc(s.color)};color:${textOn(s.color)}"><span class="nm" title="Change colour">${esc(s.name)}<input type="color" data-color="${esc(s.id)}" value="${esc(s.color)}"></span><button data-rm="${esc(s.id)}" title="Remove">✕</button></span>`).join("");
    this._el.chips.querySelectorAll("[data-color]").forEach((i) => i.addEventListener("input", () => {
      const s = this._sel.stops.find((x) => x.id === i.dataset.color);
      if (!s) return;
      s.color = i.value;
      i.closest(".chip").style.cssText = `background:${s.color};color:${textOn(s.color)}`;
      this._save();
      this._renderRows();
    }));
    this._el.chips.querySelectorAll("[data-rm]").forEach((b) => b.addEventListener("click", () => {
      this._sel.stops = this._sel.stops.filter((s) => s.id !== b.dataset.rm);
      this._save();
      this._refresh();
    }));
  }

  async _refresh() {
    this._unsubscribe();
    this._rows = {};
    this._renderChips();
    if (!this._sel.stops.length) { this._el.tws.innerHTML = ""; this._el.body.innerHTML = `<p class="muted">Search for a stop to see its departures.</p>`; return; }
    this._el.body.innerHTML = `<p class="muted">Loading…</p>`;
    const failed = [];
    this._dests = this._dests || {};
    await Promise.all(this._sel.stops.map(async (s) => {
      try {
        this._dests[s.id] = this._dests[s.id] || await this._hass.callWS({ type: WS + "destinations", stop_id: s.id });
      } catch (err) { failed.push(s.name); this._dests[s.id] = []; }
      if (s.towards && !this._dests[s.id].some((d) => d.stop_id === s.towards)) s.towards = "";
    }));
    this._renderTowards();
    this._subscribe();
  }

  _renderTowards() {
    this._el.tws.innerHTML = [...this._sel.stops].sort(byName).map((s) => `<div class="tw"><i style="background:${esc(s.color)}"></i><select data-tw="${esc(s.id)}" title="${esc(s.name)}"><option value="">${esc(s.name)}: towards anywhere</option>${(this._dests[s.id] || []).map((d) => `<option value="${esc(d.stop_id)}"${d.stop_id === s.towards ? " selected" : ""}>${esc(s.name)}: towards ${esc(d.name)} (${esc(d.routes.join(", "))})</option>`).join("")}</select></div>`).join("");
    this._el.tws.querySelectorAll("[data-tw]").forEach((sel) => sel.addEventListener("change", () => {
      const s = this._sel.stops.find((x) => x.id === sel.dataset.tw);
      if (!s) return;
      s.towards = sel.value;
      this._save();
      this._subscribeStop(s);
    }));
  }

  _subscribe() {
    this._unsubscribe();
    if (!this._hass) return;
    this._unsubs = this._unsubs || {};
    this._sel.stops.forEach((s) => this._subscribeStop(s));
  }

  async _subscribeStop(s) {
    if (!this._hass) return;
    this._unsubs = this._unsubs || {};
    this._tokens = this._tokens || {};
    if (this._unsubs[s.id]) { try { this._unsubs[s.id](); } catch (_) { /* socket closed */ } delete this._unsubs[s.id]; }
    delete this._rows[s.id];
    const msg = { type: WS + "subscribe_departures", stop_id: s.id, limit: this._limit };
    if (s.towards) msg.towards = s.towards;
    const token = (this._tokens[s.id] = {});
    try {
      const unsub = await this._hass.connection.subscribeMessage((rows) => { this._rows[s.id] = rows; this._renderRows(); }, msg);
      if (this._tokens[s.id] !== token) { unsub(); return; }
      this._unsubs[s.id] = unsub;
    } catch (err) {
      this._rows[s.id] = { error: err.message || err.code || "error" };
      this._renderRows();
    }
  }

  _unsubscribe() {
    this._tokens = {};
    Object.values(this._unsubs || {}).forEach((u) => { try { u(); } catch (_) { /* socket closed */ } });
    this._unsubs = {};
  }

  _renderRows() {
    if (!this._built || !this._rows) return;
    const stops = this._sel.stops;
    if (!stops.length) return;
    const now = Date.now() / 1000;
    const errors = [];
    const deps = [];
    let waiting = 0;
    stops.forEach((s) => {
      const rows = this._rows[s.id];
      if (!rows) { waiting++; return; }
      if (!Array.isArray(rows)) { errors.push(`${s.name} (${rows.error})`); return; }
      rows.forEach((r) => { if (r.timestamp_expected > now - 60) deps.push({ r, s }); });
    });
    if (waiting === stops.length) return;
    const mapColors = this._mapColors();
    const html = [...stops].sort(byName).map((s) => {
      const items = deps.filter((d) => d.s === s).sort((a, b) => a.r.timestamp_expected - b.r.timestamp_expected).map(({ r }) => {
        const rid = String(r.route_id || r.route);
        const mapC = mapColors.get(rid);
        const own = mapC || cssColor(this._sel.routeColors[rid], "") || (r.color ? "#" + r.color : "");
        const hasOwn = /^#[0-9a-f]{6}$/i.test(own);
        const style = hasOwn ? `background:${esc(own)};color:${mapC || this._sel.routeColors[rid] ? textOn(own) : r.text_color ? "#" + esc(r.text_color) : textOn(own)}` : "background:var(--primary-color);color:#fff";
        const pick = mapC ? "" : `<input type="color" data-rc="${esc(rid)}" value="${hasOwn ? esc(own) : "#546e7a"}">`;
        const mins = Math.round((r.timestamp_expected - now) / 60);
        const when = r.status === "canceled" ? "Cancelled" : mins < 1 ? "Due" : mins < 60 ? `${mins} min` : clock(r.timestamp_expected);
        const note = r.status === "delayed" ? `<span class="late">+${Math.round(r.delay / 60)} min</span>` : r.status === "early" ? `<span class="early">${Math.round(r.delay / 60)} min</span>` : r.status === "skipped" ? "Skipped" : "";
        return `<div class="dep ${r.status === "canceled" || r.status === "skipped" ? "gone" : ""}" style="background:linear-gradient(90deg,#000,${esc(s.color)})"><span class="badge" style="${style}" title="${mapC ? "Colour set on the map card" : "Change colour"}">${esc(r.route)}${pick}</span><span class="st">${esc(r.headsign || r.destination)}${r.is_school ? " (school)" : ""}</span><span>${esc(clock(r.timestamp))}</span><span class="when">${esc(when)} ${note}</span></div>`;
      }).join("");
      const failed = this._rows[s.id] && !Array.isArray(this._rows[s.id]);
      const body = items || (failed || !this._rows[s.id] ? "" : `<p class="muted">No departures in the next 72 hours.</p>`);
      const towards = s.towards ? (this._dests[s.id] || []).find((d) => d.stop_id === s.towards) : null;
      return `<div class="grp"><div class="gh" style="border-left:6px solid ${esc(s.color)};padding-left:8px">${esc(s.name)}${towards ? ` <span class="muted">towards ${esc(towards.name)}</span>` : ""}</div>${body}</div>`;
    });
    const err = errors.length ? `<p class="muted">Live departures unavailable for ${esc(errors.join(", "))}.</p>` : "";
    this._el.body.innerHTML = err + html.join("");
    this._el.body.querySelectorAll("[data-rc]").forEach((i) => i.addEventListener("change", () => {
      this._sel.routeColors[i.dataset.rc] = i.value;
      this._save();
      this._renderRows();
    }));
  }
}

const BOARD_TAG = "metlink-departure-board-card";
if (!customElements.get(BOARD_TAG)) {
  customElements.define(BOARD_TAG, MetlinkDepartureBoardCard);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: BOARD_TAG, name: "Metlink Departure Board", description: "Scheduled and live departures for several stops, grouped by stop." });
  // Home Assistant has been seen discarding the definition shortly after load; keep re-registering until it holds.
  let tries = 0;
  const watch = setInterval(() => {
    if (++tries > 240) { clearInterval(watch); return; }
    if (customElements.get(BOARD_TAG)) return;
    console.warn(`Metlink departure board card: element missing after ${tries * 250} ms, registering again`);
    try { customElements.define(BOARD_TAG, class extends MetlinkDepartureBoardCard {}); } catch (_) { /* retry on the next tick */ }
  }, 250);
}
})();
