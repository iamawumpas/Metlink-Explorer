/* Metlink map. Shows nothing but a street map until you pick modes or routes; choices are remembered per browser. */
(() => {
"use strict";
const WS = "metlink_explorer/";
const STORE_KEY = "metlink_explorer_map:";
const LEAFLET = "https://unpkg.com/leaflet@1.9.4/dist/leaflet";
const LEAFLET_SRI = { css: "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=", js: "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" };
const MODES = [["bus", "Bus"], ["train", "Train"], ["ferry", "Ferry"], ["cable_car", "Cable car"]];
const MAX_ROUTES = 12;
const STOP_ZOOM = 15;
const CENTRE = [-41.2865, 174.7762];
// All Esri tile services, which need no API key. OSM and CARTO tiles were tested and are blocked or need a key.
const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/";
const BASEMAPS = {
  street: ["Street", ESRI + "World_Street_Map/MapServer/tile/{z}/{y}/{x}", "Tiles © Esri", 19],
  satellite: ["Satellite", ESRI + "World_Imagery/MapServer/tile/{z}/{y}/{x}", "Tiles © Esri", 19],
  topo: ["Topographic", ESRI + "World_Topo_Map/MapServer/tile/{z}/{y}/{x}", "Tiles © Esri", 19],
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const cssColor =  (c, fallback) => (/^#[0-9a-fA-F]{6}$/.test(c || "") ? c : fallback);
// Red, orange, yellow, green, blue, indigo, violet. Picked routes take the next free one.
const PALETTE = ["#e53935", "#fb8c00", "#fbc02d", "#43a047", "#1e88e5", "#3949ab", "#8e24aa"];
const TRAIN_LINES = ["KPL", "HVL", "JVL", "MEL", "WRL"];
const BUS_COLOR = "#546e7a";
// Colour of a route nobody picked: buses are one fixed colour, each train line has its own, ferries white, cable car black.
const modeColor = (mode, short) => {
  if (mode === "ferry") return "#ffffff";
  if (mode === "cable_car") return "#000000";
  if (mode === "train") {
    const i = TRAIN_LINES.indexOf(short);
    const n = i >= 0 ? i : [...String(short || "")].reduce((a, c) => a + c.charCodeAt(0), 0);
    return PALETTE[n % PALETTE.length];
  }
  return BUS_COLOR;
};
const isLight = (c) => {
  const n = parseInt(c.slice(1), 16);
  return 0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255) > 150;
};
// WCAG relative luminance: text is whichever of black or white has the higher contrast with the colour.
const luminance = (c) => {
  const n = parseInt(c.slice(1), 16);
  const [r, g, b] = [n >> 16, (n >> 8) & 255, n & 255].map((v) => { const s = v / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const textOn = (c) => (1.05 / (luminance(c) + 0.05) >= (luminance(c) + 0.05) / 0.05 ? "#ffffff" : "#000000");
const casingColor = (c) => (isLight(c) ? "#263238" : "#ffffff");
const clock = (ts) => new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

let leafletPromise;
function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  leafletPromise ||= new Promise((resolve, reject) => {
    const js = document.createElement("script");
    Object.assign(js, { src: LEAFLET + ".js", integrity: LEAFLET_SRI.js, crossOrigin: "" });
    js.onload = () => resolve(window.L);
    js.onerror = () => { leafletPromise = undefined; reject(new Error("Could not load the map library")); };
    document.head.appendChild(js);
  });
  return leafletPromise;
}

let routesCache;
const loadRoutes = (hass) => (routesCache ||= hass.callWS({ type: WS + "routes" }).catch((e) => { routesCache = undefined; throw e; }));

class MetlinkMapCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._key = STORE_KEY + (this._config.id || "default");
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(this._key) || "{}"); } catch (_) { /* ignore */ }
    this._sel = {
      modes: this._config.modes || saved.modes || [],
      routes: (this._config.routes || saved.routes || []).map((r) => ({ ...r })),
      stops: saved.stops ?? true,
      popup: this._config.popup_theme || saved.popup || "light",
      dim: this._config.dim ?? saved.dim ?? 0,
      stopColor: this._config.stop_color || saved.stopColor || "#ffb300",
      stopSize: this._config.stop_size ?? saved.stopSize ?? 10,
      basemap: this._config.basemap || saved.basemap || "street",
    };
    this._height = this._config.height || 480;
    for (const r of this._sel.routes) if (!cssColor(r.color)) r.color = this._nextColor();
    if (this._built) this._apply();
  }

  _nextColor() {
    const used = new Set(this._sel.routes.map((r) => r.color));
    return PALETTE.find((c) => !used.has(c)) || PALETTE[this._sel.routes.length % PALETTE.length];
  }

  _colorFor(routeId, mode, short) {
    return cssColor(this._sel.routes.find((r) => r.id === routeId)?.color) || modeColor(mode, short);
  }

  _recolour() {
    for (const [id, lines] of this._routeLines || []) {
      const c = this._colorFor(id);
      for (const line of lines) line.setStyle({ color: line._casing ? casingColor(c) : c });
    }
    this._drawVehicles(this._lastVehicles || []);
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._build();
  }

  connectedCallback() { if (this._built) this._apply(); }

  disconnectedCallback() {
    this._unsubscribe();
    this._unsubscribeAlerts();
    clearTimeout(this._moveTimer);
    if (this._observer) this._observer.disconnect();
    if (this._map) { this._map.remove(); this._map = null; }
    this._base = null;
    this._basemapName = null;
    this._fitted = false;
    this._vehicleMarkers = null;
    this._routeLines = new Map();
  }

  getCardSize() { return 8; }
  getGridOptions() { return { columns: 12, rows: "auto", min_columns: 3 }; }
  static getStubConfig() { return {}; }

  _save() { try { localStorage.setItem(this._key, JSON.stringify(this._sel)); } catch (_) { /* private mode */ } }

  _build() {
    this._built = true;
    this.innerHTML = `
      <div class="mm-card" style="background:var(--ha-card-background,var(--card-background-color,#fff));border-radius:var(--ha-card-border-radius,12px);box-shadow:var(--ha-card-box-shadow,none);border:var(--ha-card-border-width,1px) solid var(--ha-card-border-color,var(--divider-color));color:var(--primary-text-color);overflow:hidden">
        <link rel="stylesheet" href="${LEAFLET}.css" integrity="${LEAFLET_SRI.css}" crossorigin="">
        <style>
          .mm{padding:8px 12px}.mm .chips{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0}
          .mm button.chip{border:1px solid var(--divider-color);border-radius:16px;padding:4px 12px;background:var(--card-background-color);color:var(--primary-text-color);cursor:pointer}
          .mm button.chip.on{background:var(--primary-color);color:#fff;border-color:var(--primary-color)}
          .mm input[type=search]{width:100%;box-sizing:border-box;padding:6px 8px;margin:4px 0;border:1px solid var(--divider-color);border-radius:6px;background:var(--card-background-color);color:var(--primary-text-color)}
          .mm .hits{max-height:160px;overflow:auto}.mm .hits button{display:block;width:100%;text-align:left;padding:4px 6px;border:0;background:none;color:var(--primary-text-color);cursor:pointer}
          .mm .hits button:hover{background:var(--secondary-background-color)}.mm .muted{color:var(--secondary-text-color)}
          .mm .opts{display:flex;gap:16px;flex-wrap:wrap;margin:4px 0}.mm .status{font-size:.85em;min-height:1.2em}
          .mm-map{width:100%;position:relative;overflow:hidden;isolation:isolate;z-index:0}.mm-badge{display:flex;align-items:center;justify-content:center;border-radius:12px;color:#fff;font:600 11px/1 sans-serif;min-width:22px;height:22px;padding:0 4px;border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.45),0 1px 4px rgba(0,0,0,.5);box-sizing:border-box}
          .mm-pop table{border-collapse:collapse;width:100%}.mm-pop td{padding:2px 6px;border-top:1px solid rgba(128,128,128,.45);border-bottom:1px solid rgba(128,128,128,.45)}.mm-pop .warn{margin-top:4px;color:#e65100}.mm-pop .head{text-align:center;padding:0 14px;margin-bottom:4px}.mm-map .leaflet-popup-content{margin:12px 20px}
          .mm-pop td.t{text-align:right;white-space:nowrap;padding-right:2px}.mm-pop td.l{width:1%;white-space:nowrap}
          .mm-late{display:inline-block;background:#fff;color:#d50000;font-weight:700;border-radius:8px;padding:0 6px;animation:mm-blink 1s steps(2,start) infinite}
          @keyframes mm-blink{to{visibility:hidden}}
          @media (prefers-reduced-motion:reduce){.mm-late{animation:none}}
          .mm .pr{display:inline-flex;align-items:center;gap:6px;border-radius:16px;padding:4px 10px 4px 12px;border:1px solid rgba(128,128,128,.6);font-weight:600}.mm .pr .nm{position:relative;cursor:pointer}.mm .pr input[type=color]{position:absolute;inset:-4px;width:calc(100% + 8px);height:calc(100% + 8px);opacity:0;cursor:pointer;border:0;padding:0}.mm .pr button{background:none;border:0;color:inherit;cursor:pointer;padding:0 2px;position:relative;z-index:1}
          .mm-dark .leaflet-popup-content-wrapper,.mm-dark .leaflet-popup-tip{background:#263238;color:#eceff1}.mm-dark .mm-pop .muted{color:#b0bec5}.mm-dark .mm-pop .warn{color:#ffb74d}.mm-dark .leaflet-popup-close-button{color:#eceff1}
          .mm .alerts{margin:4px 0}.mm .alerts .pin{padding:6px 8px;margin:4px 0;border-radius:6px;background:#fff3e0;color:#5d4037;border-left:4px solid #e65100}
          .mm .alerts details{margin:4px 0}.mm .alerts .item{padding:4px 0;border-top:1px solid var(--divider-color)}.mm .alerts .item p{margin:2px 0 0;font-size:.9em;white-space:pre-wrap}
        </style>
        <details class="mm" open>
          <summary>Filters</summary>
          <div class="chips modes"></div>
          <div class="opts">
            <label><input type="checkbox" class="stops"> Stops</label>
            <label>Map <select class="basemap">${Object.entries(BASEMAPS).map(([id, b]) => `<option value="${id}">${b[0]}</option>`).join("")}</select></label>
            <label>Stop bubbles <select class="popup"><option value="light">Light</option><option value="dark">Dark</option></select></label>
            <label>Darken map <input type="range" class="dim" min="0" max="80" step="5" style="vertical-align:middle"></label>
            <label>Stop colour <input type="color" class="stopcolor" style="vertical-align:middle"></label>
            <label>Stop size <input type="range" class="stopsize" min="3" max="20" step="1" style="vertical-align:middle"></label>
          </div>
          <input class="search" type="search" placeholder="Add routes: search by number or name…" autocomplete="off">
          <div class="hits"></div>
          <div class="chips picked"></div>
        </details>
        <div class="mm"><div class="alerts"></div></div>
        <div class="mm-map"></div>
        <div class="mm"><div class="status muted"></div></div>
      </div>`;
    const q = (s) => this.querySelector(s);
    this._el = { modes: q(".modes"), dim: q(".dim"), stopColor: q(".stopcolor"), stopSize: q(".stopsize"), stops: q(".stops"), basemap: q(".basemap"), popup: q(".popup"), search: q(".search"), hits: q(".hits"), picked: q(".picked"), mapDiv: q(".mm-map"), status: q(".status"), alerts: q(".alerts") };
    this._el.mapDiv.style.height = this._height + "px";
    this._el.modes.innerHTML = MODES.map(([id, label]) => `<button class="chip" data-mode="${id}">${label}</button>`).join("");
    this._el.modes.addEventListener("click", (e) => {
      const id = e.target.dataset?.mode;
      if (!id) return;
      this._sel.modes = this._sel.modes.includes(id) ? this._sel.modes.filter((m) => m !== id) : [...this._sel.modes, id];
      this._changed();
    });
    this._el.popup.addEventListener("change", () => { this._sel.popup = this._el.popup.value; this._applyPopupTheme(); this._save(); });
    this._el.basemap.addEventListener("change", () => { this._sel.basemap = this._el.basemap.value; this._setBasemap(); this._save(); });
    this._el.stopColor.addEventListener("input", () => { this._sel.stopColor = this._el.stopColor.value; this._styleStops(); this._save(); });
    this._el.stopSize.addEventListener("input", () => { this._sel.stopSize = Number(this._el.stopSize.value); this._styleStops(); this._save(); });
    this._el.dim.addEventListener("input", () => { this._sel.dim = Number(this._el.dim.value); this._applyDim(); this._save(); });
    this._el.stops.addEventListener("change", () => { this._sel.stops = this._el.stops.checked; this._changed(); });
    this._el.search.addEventListener("input", () => this._search());
    this._el.picked.addEventListener("input", (e) => {
      const id = e.target.dataset?.color;
      const route = id && this._sel.routes.find((r) => r.id === id);
      if (!route) return;
      route.color = e.target.value;
      const chip = e.target.closest(".pr");
      if (chip) { chip.style.background = route.color; chip.style.color = textOn(route.color); }
      this._save();
      this._recolour();
    });
    this._el.picked.addEventListener("click", (e) => {
      const id = e.target.dataset?.route;
      if (!id) return;
      this._sel.routes = this._sel.routes.filter((r) => r.id !== id);
      this._changed();
    });
    this._apply();
  }

  _changed() { this._save(); this._apply(); }

  async _apply() {
    this._syncControls();
    try {
      const L = await loadLeaflet();
      this._ensureMap(L);
    } catch (err) {
      this._status(err.message);
      return;
    }
    this._setBasemap();
    await this._drawRoutes();
    this._drawStops();
    this._subscribe();
    this._subscribeAlerts();
  }

  _syncControls() {
    this._el.popup.value = this._sel.popup === "dark" ? "dark" : "light";
    this._applyPopupTheme();
    this._el.basemap.value = BASEMAPS[this._sel.basemap] ? this._sel.basemap : "street";
    this._el.dim.value = this._sel.dim || 0;
    this._el.stopColor.value = cssColor(this._sel.stopColor, "#ffb300");
    this._el.stopSize.value = this._sel.stopSize;
    this._el.stops.checked = !!this._sel.stops;
    this._el.modes.querySelectorAll("button").forEach((b) => b.classList.toggle("on", this._sel.modes.includes(b.dataset.mode)));
    this._el.picked.innerHTML = this._sel.routes.map((r) => { const c = cssColor(r.color, "#546e7a"); return `<span class="pr" data-chip="${esc(r.id)}" style="background:${c};color:${textOn(c)}"><span class="nm" title="Change colour">${esc(r.name)}<input type="color" data-color="${esc(r.id)}" value="${esc(c)}" title="Route colour"></span><button data-route="${esc(r.id)}" title="Remove">✕</button></span>`; }).join("");
  }

  _ensureMap(L) {
    if (this._map) { setTimeout(() => this._map.invalidateSize(), 0); return; }
    const map = (this._map = L.map(this._el.mapDiv, { center: CENTRE, zoom: 12, preferCanvas: true }));
    this._layers = { routes: L.layerGroup().addTo(map), stops: L.layerGroup().addTo(map), vehicles: L.layerGroup().addTo(map) };
    this._vehicleMarkers = new Map();
    map.on("moveend", () => { clearTimeout(this._moveTimer); this._moveTimer = setTimeout(() => this._drawStops(), 400); });
    this._observer = new ResizeObserver(() => map.invalidateSize());
    this._observer.observe(this._el.mapDiv);
  }

  _setBasemap() {
    const L = window.L;
    if (!this._map || this._basemapName === this._sel.basemap) return;
    if (this._base) this._map.removeLayer(this._base);
    const [, url, attribution, nativeZoom] = BASEMAPS[this._sel.basemap] || BASEMAPS.street;
    this._base = L.tileLayer(url, { attribution, maxZoom: 19, maxNativeZoom: nativeZoom }).addTo(this._map);
    this._base.bringToBack();
    this._basemapName = this._sel.basemap;
    this._applyDim();
  }

  _applyPopupTheme() { this._el.mapDiv.classList.toggle("mm-dark", this._sel.popup === "dark"); }

  _stopStyle() {
    const size = Math.min(20, Math.max(3, Number(this._sel.stopSize) || 10));
    return { radius: size, weight: 2, color: "#37474f", fillColor: cssColor(this._sel.stopColor, "#ffb300"), fillOpacity: 1 };
  }

  _styleStops() {
    if (this._layers) this._layers.stops.eachLayer((m) => m.setStyle && m.setRadius && (m.setStyle(this._stopStyle()), m.setRadius(this._stopStyle().radius)));
  }

  // Filtering only the tile pane darkens the map without touching routes, stops or vehicles.
  _applyDim() {
    if (!this._map) return;
    const dim = Math.min(80, Math.max(0, Number(this._sel.dim) || 0));
    this._map.getPane("tilePane").style.filter = dim ? `brightness(${(100 - dim) / 100})` : "";
  }

  _status(text) { if (this._el) this._el.status.textContent = text || ""; }

  async _search() {
    const text = this._el.search.value.trim().toLowerCase();
    if (!text) { this._el.hits.innerHTML = ""; return; }
    try {
      const routes = await loadRoutes(this._hass);
      const hits = routes
        .filter((r) => (!this._sel.modes.length || this._sel.modes.includes(r.mode)))
        .filter((r) => r.short_name.toLowerCase().startsWith(text) || r.long_name.toLowerCase().includes(text))
        .slice(0, 20);
      this._el.hits.innerHTML = hits.map((r) => `<button data-id="${esc(r.route_id)}" data-name="${esc(r.short_name)}">${esc(r.short_name)} <span class="muted">${esc(r.long_name)}</span></button>`).join("") || `<div class="muted">No routes found</div>`;
      this._el.hits.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
        if (this._sel.routes.length >= MAX_ROUTES) { this._status(`Up to ${MAX_ROUTES} routes at a time.`); return; }
        if (!this._sel.routes.some((r) => r.id === b.dataset.id)) this._sel.routes.push({ id: b.dataset.id, name: b.dataset.name, color: this._nextColor() });
        this._el.search.value = "";
        this._el.hits.innerHTML = "";
        this._changed();
      }));
    } catch (_) {
      this._el.hits.innerHTML = `<div class="muted">Routes are not available yet. The timetable is still downloading.</div>`;
    }
  }

  async _drawRoutes() {
    const L = window.L;
    const token = (this._routeToken = {});
    const lines = [];
    for (const sel of this._sel.routes) {
      try {
        const route = await this._hass.callWS({ type: WS + "route", route_id: sel.id });
        const shapeIds = route.directions.flatMap((d) => d.shape_ids.slice(0, 1));
        const shapes = await Promise.all(shapeIds.map((id) => this._hass.callWS({ type: WS + "shape", shape_id: id }).catch(() => null)));
        for (const s of shapes) if (s) lines.push({ points: s.points, color: this._colorFor(sel.id, route.mode, route.short_name), dashed: !!route.mode && route.mode !== "bus", routeId: sel.id });
      } catch (_) { /* a missing route must not stop the others */ }
      if (this._routeToken !== token) return;
    }
    this._layers.routes.clearLayers();
    this._routeLines = new Map();
    lines.forEach((l) => {
      const dash = l.dashed ? "10 8" : null;
      const casing = L.polyline(l.points, { color: casingColor(l.color), weight: 7, opacity: 0.5, dashArray: dash, lineCap: "butt" }).addTo(this._layers.routes);
      const line = L.polyline(l.points, { color: l.color, weight: 4, opacity: 0.95, dashArray: dash, lineCap: "butt" }).addTo(this._layers.routes);
      casing._casing = true;
      casing._baseDash = line._baseDash = dash;
      if (!this._routeLines.has(l.routeId)) this._routeLines.set(l.routeId, []);
      this._routeLines.get(l.routeId).push(casing, line);
    });
    this._markRoutes();
    if (lines.length && !this._fitted) {
      this._map.fitBounds(L.latLngBounds(lines.flatMap((l) => l.points)), { padding: [20, 20] });
      this._fitted = true;
    }
    if (!lines.length) this._fitted = false;
  }

  async _drawStops() {
    if (!this._map || !this._layers) return;
    const L = window.L;
    const sel = this._sel;
    const msg = { type: WS + "stops" };
    if (sel.routes.length) msg.route_ids = sel.routes.map((r) => r.id);
    else if (sel.modes.length === 1) msg.mode = sel.modes[0];
    else if (!sel.modes.length) { this._layers.stops.clearLayers(); return; }
    if (!sel.stops) { this._layers.stops.clearLayers(); return; }
    if (!sel.routes.length) {
      if (this._map.getZoom() < STOP_ZOOM) { this._layers.stops.clearLayers(); this._status("Zoom in to see stops."); return; }
      const b = this._map.getBounds();
      msg.bbox = [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()];
    }
    const token = (this._stopToken = {});
    try {
      let stops = await this._hass.callWS(msg);
      if (this._stopToken !== token) return;
      if (!sel.routes.length && sel.modes.length > 1) stops = stops.filter((s) => s.modes.some((m) => sel.modes.includes(m)));
      this._layers.stops.clearLayers();
      for (const s of stops) {
        const marker = L.circleMarker([s.lat, s.lon], this._stopStyle());
        marker.bindPopup("Loading…", { minWidth: 200 });
        marker.on("popupopen", () => this._stopPopup(marker, s));
        marker.addTo(this._layers.stops);
      }
      this._status("");
    } catch (_) {
      this._status("Stops are not available yet. The timetable is still downloading.");
    }
  }

  async _subscribeAlerts() {
    this._unsubscribeAlerts();
    const sel = this._sel;
    this._alerts = [];
    this._renderAlerts();
    if (!this._hass || (!sel.routes.length && !sel.modes.length)) return;
    const msg = { type: WS + "subscribe_alerts" };
    if (sel.routes.length) msg.route_ids = sel.routes.map((r) => r.id);
    else msg.modes = sel.modes;
    const token = (this._alertToken = {});
    try {
      const unsub = await this._hass.connection.subscribeMessage((alerts) => {
        this._alerts = alerts;
        this._renderAlerts();
        this._markRoutes();
      }, msg);
      if (this._alertToken !== token) { unsub(); return; }
      this._unsubAlerts = unsub;
    } catch (_) { /* alerts are optional; the map still works */ }
  }

  _unsubscribeAlerts() {
    this._alertToken = null;
    if (this._unsubAlerts) { try { this._unsubAlerts(); } catch (_) { /* socket closed */ } this._unsubAlerts = null; }
  }

  _renderAlerts() {
    const box = this._el && this._el.alerts;
    if (!box) return;
    const alerts = this._alerts || [];
    if (!alerts.length) { box.innerHTML = ""; return; }
    const pinned = alerts.filter((a) => a.replacement);
    const item = (a) => {
      const names = (a.routes || []).map((r) => this._sel.routes.find((p) => p.id === r)?.name).filter(Boolean);
      return `<div class="item"><b>${esc(a.header || "Service notice")}</b>${names.length ? ` <span class="muted">${esc(names.join(", "))}</span>` : ""}${a.description ? `<p>${esc(a.description)}</p>` : ""}</div>`;
    };
    box.innerHTML =
      pinned.map((a) => `<div class="pin">⚠ <b>${esc(a.header || "Replacement services")}</b></div>`).join("") +
      `<details><summary>⚠ ${alerts.length} service alert${alerts.length === 1 ? "" : "s"}</summary>${alerts.map(item).join("")}</details>`;
  }

  _markRoutes() {
    if (!this._routeLines) return;
    const byRoute = new Map();
    for (const a of this._alerts || []) for (const r of a.routes || []) {
      if (!byRoute.has(r)) byRoute.set(r, []);
      byRoute.get(r).push(a.header || "Service notice");
    }
    for (const [routeId, lines] of this._routeLines) {
      const notes = byRoute.get(routeId);
      for (const line of lines) {
        line.setStyle({ dashArray: notes ? "4 6" : line._baseDash });
        line.unbindTooltip();
        if (notes) line.bindTooltip(`⚠ ${notes.map(esc).join("<br>⚠ ")}`, { sticky: true });
      }
    }
  }

  async _stopPopup(marker, stop) {
    try {
      const [rows, alerts] = await Promise.all([
        this._hass.callWS({ type: WS + "departures", stop_id: stop.id, limit: 5 }),
        this._hass.callWS({ type: WS + "alerts", stop_ids: [stop.id] }).catch(() => []),
      ]);
      const now = Date.now() / 1000;
      const body = rows.length
        ? `<table>${rows.map((r) => {
            const mins = Math.round((r.timestamp_expected - now) / 60);
            const when = r.status === "canceled" ? "Cancelled" : mins < 1 ? "Due" : mins < 60 ? `${mins} min` : clock(r.timestamp_expected);
            const c = this._colorFor(r.route_id, r.mode, r.route);
            const late = r.status === "delayed" ? `<span class="mm-late">late</span>` : "";
            return `<tr style="background:${c};color:${textOn(c)}"><td><b>${esc(r.route)}</b></td><td>${esc(r.headsign || r.destination)}</td><td class="t">${esc(when)}</td><td class="l">${late}</td></tr>`;
          }).join("")}</table>`
        : "No departures soon.";
      const warn = alerts.map((a) => `<div class="warn">⚠ ${esc(a.header || "Service notice")}</div>`).join("");
      marker.setPopupContent(`<div class="mm-pop"><div class="head"><b>${esc(stop.name)}</b> <span class="muted">${esc(stop.id)}</span></div>${body}${warn}</div>`);
    } catch (_) {
      marker.setPopupContent(`<div class="mm-pop"><b>${esc(stop.name)}</b><br>Departures unavailable.</div>`);
    }
  }

  async _subscribe() {
    this._unsubscribe();
    const sel = this._sel;
    this._clearVehicles();
    if (!this._hass || (!sel.routes.length && !sel.modes.length)) return;
    const msg = { type: WS + "subscribe_vehicles" };
    if (sel.routes.length) msg.route_ids = sel.routes.map((r) => r.id);
    else msg.modes = sel.modes;
    const token = (this._subToken = {});
    try {
      const unsub = await this._hass.connection.subscribeMessage((vehicles) => this._drawVehicles(vehicles), msg);
      if (this._subToken !== token) { unsub(); return; }
      this._unsub = unsub;
    } catch (err) {
      this._status(`Live vehicles unavailable (${err.message || err.code}).`);
    }
  }

  _unsubscribe() {
    this._subToken = null;
    if (this._unsub) { try { this._unsub(); } catch (_) { /* socket closed */ } this._unsub = null; }
  }

  _clearVehicles() {
    if (this._layers) this._layers.vehicles.clearLayers();
    if (this._vehicleMarkers) this._vehicleMarkers.clear();
    this._lastVehicles = [];
  }

  _drawVehicles(vehicles) {
    if (!this._map) return;
    const L = window.L;
    this._lastVehicles = vehicles;
    const seen = new Set();
    for (const v of vehicles) {
      seen.add(v.id);
      const color = this._colorFor(v.route_id, v.mode, v.route);
      const fg = textOn(color);
      const label = esc(v.route || (v.mode === "ferry" ? "⛴" : "?"));
      const rotate = typeof v.bearing === "number" ? `<div style="position:absolute;inset:-9px;transform:rotate(${Math.round(v.bearing)}deg);pointer-events:none"><div style="margin:0 auto;width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-bottom:8px solid ${color};filter:drop-shadow(0 0 1px #000)"></div></div>` : "";
      const icon = L.divIcon({ className: "", iconSize: [28, 22], iconAnchor: [14, 11], html: `<div style="position:relative">${rotate}<div class="mm-badge" style="background:${color};color:${fg}">${label}</div></div>` });
      const title = (v.name || (v.route ? `Route ${v.route}` : "Vehicle")) + (v.canceled ? " (cancelled trip)" : "");
      let marker = this._vehicleMarkers.get(v.id);
      if (marker) { marker.setLatLng([v.lat, v.lon]); marker.setIcon(icon); marker.setOpacity(v.canceled ? 0.45 : 1); marker.setTooltipContent(esc(title)); }
      else {
        marker = L.marker([v.lat, v.lon], { icon, keyboard: false, opacity: v.canceled ? 0.45 : 1 }).bindTooltip(esc(title)).addTo(this._layers.vehicles);
        this._vehicleMarkers.set(v.id, marker);
      }
    }
    for (const [id, marker] of this._vehicleMarkers) {
      if (!seen.has(id)) { this._layers.vehicles.removeLayer(marker); this._vehicleMarkers.delete(id); }
    }
    this._status(vehicles.length ? "" : "No live vehicles right now.");
  }
}

const TAG = "metlink-map-card";
const define = (cls) => {
  try { customElements.define(TAG, cls); } catch (err) { console.warn("Metlink map card: define failed", err); }
  return !!customElements.get(TAG);
};
if (!customElements.get(TAG)) {
  const ok = define(MetlinkMapCard);
  console.info("Metlink map card: loaded, registered =", ok);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: TAG, name: "Metlink Map", description: "Live buses, trains and ferries, routes and stops on a street map." });
  // Home Assistant has been seen discarding the definition shortly after load; keep re-registering until it holds.
  let tries = 0;
  const watch = setInterval(() => {
    if (++tries > 240) { clearInterval(watch); return; }
    if (customElements.get(TAG)) return;
    console.warn(`Metlink map card: element missing after ${tries * 250} ms, registering again`);
    define(class extends MetlinkMapCard {});
  }, 250);
}
})();
