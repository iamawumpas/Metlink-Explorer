/* Metlink departure board. Stop and "Towards" are chosen in the card and remembered per browser. */
(() => {
"use strict";
const WS = "metlink_explorer/";
const STORE_KEY = "metlink_explorer_board:";

let stopsCache;
const loadStops = (hass) => (stopsCache ||= hass.callWS({ type: WS + "stops" }).catch((e) => { stopsCache = undefined; throw e; }));

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const clock = (ts) => new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

class MetlinkDepartureBoardCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._key = STORE_KEY + (this._config.id || "default");
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(this._key) || "{}"); } catch (_) { /* ignore */ }
    this._sel = { stopId: this._config.stop_id || saved.stopId || "", stopName: saved.stopName || "", towards: this._config.towards ?? saved.towards ?? "" };
    this._limit = this._config.limit || 10;
    if (this._built) this._refresh();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._build();
  }

  connectedCallback() {
    this._tick = setInterval(() => this._renderRows(), 30000);
    if (this._built) this._subscribe();
  }

  disconnectedCallback() {
    clearInterval(this._tick);
    this._unsubscribe();
  }

  getCardSize() { return 6; }
  static getStubConfig() { return { limit: 10 }; }

  _build() {
    this._built = true;
    this.innerHTML = `
      <div class="mx-card" style="background:var(--ha-card-background,var(--card-background-color,#fff));border-radius:var(--ha-card-border-radius,12px);box-shadow:var(--ha-card-box-shadow,none);border:var(--ha-card-border-width,1px) solid var(--ha-card-border-color,var(--divider-color));color:var(--primary-text-color);overflow:hidden">
        <style>
          .mx{padding:12px 16px}.mx input,.mx select{width:100%;box-sizing:border-box;padding:8px;margin:4px 0;border:1px solid var(--divider-color);border-radius:6px;background:var(--card-background-color);color:var(--primary-text-color)}
          .mx .hits button{display:block;width:100%;text-align:left;padding:6px 8px;border:0;background:none;color:var(--primary-text-color);cursor:pointer}
          .mx .hits button:hover{background:var(--secondary-background-color)}
          .mx table{width:100%;border-collapse:collapse}.mx td{padding:6px 4px;border-top:1px solid var(--divider-color)}
          .mx .badge{display:inline-block;min-width:2.2em;text-align:center;padding:2px 6px;border-radius:4px;font-weight:600}
          .mx .late{color:var(--error-color)}.mx .early{color:var(--info-color)}.mx .gone{text-decoration:line-through;opacity:.6}.mx .muted{color:var(--secondary-text-color)}
        </style>
        <div class="mx">
          <div class="title"></div>
          <input class="search" type="search" placeholder="Search for a stop…" autocomplete="off">
          <div class="hits"></div>
          <select class="towards" hidden></select>
          <div class="body"></div>
        </div>
      </div>`;
    const q = (s) => this.querySelector(s);
    this._el = { title: q(".title"), search: q(".search"), hits: q(".hits"), towards: q(".towards"), body: q(".body") };
    this._el.search.addEventListener("input", () => this._search());
    this._el.towards.addEventListener("change", () => {
      this._sel.towards = this._el.towards.value;
      this._save();
      this._subscribe();
    });
    this._refresh();
  }

  _save() {
    try { localStorage.setItem(this._key, JSON.stringify(this._sel)); } catch (_) { /* private mode */ }
  }

  async _search() {
    const text = this._el.search.value.trim().toLowerCase();
    if (text.length < 2) { this._el.hits.innerHTML = ""; return; }
    try {
      const stops = await loadStops(this._hass);
      const hits = stops.filter((s) => s.name.toLowerCase().includes(text) || s.stop_ids.some((i) => i.startsWith(text))).slice(0, 12);
      this._el.hits.innerHTML = hits.map((s) => `<button data-id="${esc(s.id)}" data-name="${esc(s.name)}">${esc(s.name)} <span class="muted">${esc(s.modes.join(", "))} · ${esc(s.id)}</span></button>`).join("") || `<div class="muted">No stops found</div>`;
      this._el.hits.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
        this._sel = { stopId: b.dataset.id, stopName: b.dataset.name, towards: "" };
        this._el.search.value = "";
        this._el.hits.innerHTML = "";
        this._save();
        this._refresh();
      }));
    } catch (err) {
      this._el.hits.innerHTML = `<div class="muted">Stops are not available yet. The timetable is still downloading.</div>`;
    }
  }

  async _refresh() {
    this._unsubscribe();
    this._rows = null;
    this._el.title.innerHTML = this._sel.stopId ? `<h2 style="margin:0 0 4px">${esc(this._sel.stopName || this._sel.stopId)}</h2>` : "";
    this._el.towards.hidden = !this._sel.stopId;
    if (!this._sel.stopId) { this._el.body.innerHTML = `<p class="muted">Search for a stop to see its departures.</p>`; return; }
    try {
      const dests = await this._hass.callWS({ type: WS + "destinations", stop_id: this._sel.stopId });
      this._el.towards.innerHTML = `<option value="">Towards: anywhere</option>` + dests.map((d) => `<option value="${esc(d.stop_id)}">Towards ${esc(d.name)} (${esc(d.routes.join(", "))})</option>`).join("");
      this._el.towards.value = dests.some((d) => d.stop_id === this._sel.towards) ? this._sel.towards : "";
      this._sel.towards = this._el.towards.value;
    } catch (err) {
      this._el.body.innerHTML = `<p class="muted">Could not load this stop (${esc(err.message || err.code)}).</p>`;
      return;
    }
    this._subscribe();
  }

  async _subscribe() {
    this._unsubscribe();
    if (!this._hass || !this._sel.stopId) return;
    const msg = { type: WS + "subscribe_departures", stop_id: this._sel.stopId, limit: this._limit };
    if (this._sel.towards) msg.towards = this._sel.towards;
    const token = (this._token = {});
    try {
      const unsub = await this._hass.connection.subscribeMessage((rows) => { this._rows = rows; this._renderRows(); }, msg);
      if (this._token !== token) { unsub(); return; }
      this._unsub = unsub;
    } catch (err) {
      this._el.body.innerHTML = `<p class="muted">Live departures unavailable (${esc(err.message || err.code)}).</p>`;
    }
  }

  _unsubscribe() {
    this._token = null;
    if (this._unsub) { try { this._unsub(); } catch (_) { /* socket closed */ } this._unsub = null; }
  }

  _renderRows() {
    if (!this._built || !this._rows) return;
    if (!this._rows.length) { this._el.body.innerHTML = `<p class="muted">No departures in the next 72 hours.</p>`; return; }
    const now = Date.now() / 1000;
    const rows = this._rows.filter((r) => r.timestamp_expected > now - 60).map((r) => {
      const mins = Math.round((r.timestamp_expected - now) / 60);
      const when = r.status === "canceled" ? "Cancelled" : mins < 1 ? "Due" : mins < 60 ? `${mins} min` : clock(r.timestamp_expected);
      const note = r.status === "delayed" ? `<span class="late">+${Math.round(r.delay / 60)} min</span>` : r.status === "early" ? `<span class="early">${Math.round(r.delay / 60)} min</span>` : r.status === "skipped" ? "Skipped" : "";
      const style = r.color ? `background:#${esc(r.color)};color:${r.text_color ? "#" + esc(r.text_color) : "#fff"}` : "background:var(--primary-color);color:#fff";
      return `<tr class="${r.status === "canceled" || r.status === "skipped" ? "gone" : ""}"><td><span class="badge" style="${style}">${esc(r.route)}</span></td><td>${esc(r.headsign || r.destination)}${r.is_school ? ' <span class="muted">school</span>' : ""}</td><td>${esc(clock(r.timestamp))}</td><td>${esc(when)} ${note}</td></tr>`;
    });
    this._el.body.innerHTML = `<table>${rows.join("")}</table>`;
  }
}

const BOARD_TAG = "metlink-departure-board-card";
if (!customElements.get(BOARD_TAG)) {
  customElements.define(BOARD_TAG, MetlinkDepartureBoardCard);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: BOARD_TAG, name: "Metlink Departure Board", description: "Scheduled and live departures for a stop, filtered by where you are going." });
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
