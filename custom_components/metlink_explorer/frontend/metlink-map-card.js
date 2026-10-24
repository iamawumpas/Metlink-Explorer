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
const BASEMAPS = {
  street: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", "Tiles © Esri", 19],
  light: ["https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", "Tiles © Esri", 16],
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const hex = (c, fallback) => (/^[0-9a-fA-F]{6}$/.test(c || "") ? "#" + c : fallback);
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
      routes: this._config.routes || saved.routes || [],
      school: this._config.school ?? saved.school ?? false,
      stops: saved.stops ?? true,
      basemap: this._config.basemap || saved.basemap || "street",
    };
    this._height = this._config.height || 480;
    if (this._built) this._apply();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._build();
  }

  connectedCallback() { if (this._built) this._apply(); }

  disconnectedCallback() {
    this._unsubscribe();
    clearTimeout(this._moveTimer);
    if (this._observer) this._observer.disconnect();
    if (this._map) { this._map.remove(); this._map = null; }
  }

  getCardSize() { return 8; }
  static getStubConfig() { return {}; }

  _save() { try { localStorage.setItem(this._key, JSON.stringify(this._sel)); } catch (_) { /* private mode */ } }

  _build() {
    this._built = true;
    this.innerHTML = `
      <ha-card style="overflow:hidden">
        <link rel="stylesheet" href="${LEAFLET}.css" integrity="${LEAFLET_SRI.css}" crossorigin="">
        <style>
          .mm{padding:8px 12px}.mm .chips{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0}
          .mm button.chip{border:1px solid var(--divider-color);border-radius:16px;padding:4px 12px;background:var(--card-background-color);color:var(--primary-text-color);cursor:pointer}
          .mm button.chip.on{background:var(--primary-color);color:#fff;border-color:var(--primary-color)}
          .mm input[type=search]{width:100%;box-sizing:border-box;padding:6px 8px;margin:4px 0;border:1px solid var(--divider-color);border-radius:6px;background:var(--card-background-color);color:var(--primary-text-color)}
          .mm .hits{max-height:160px;overflow:auto}.mm .hits button{display:block;width:100%;text-align:left;padding:4px 6px;border:0;background:none;color:var(--primary-text-color);cursor:pointer}
          .mm .hits button:hover{background:var(--secondary-background-color)}.mm .muted{color:var(--secondary-text-color)}
          .mm .opts{display:flex;gap:16px;flex-wrap:wrap;margin:4px 0}.mm .status{font-size:.85em;min-height:1.2em}
          .mm-map{width:100%;position:relative;overflow:hidden;isolation:isolate;z-index:0}.mm-badge{display:flex;align-items:center;justify-content:center;border-radius:12px;color:#fff;font:600 11px/1 sans-serif;min-width:22px;height:22px;padding:0 4px;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.5);box-sizing:border-box}
          .mm-pop td{padding:1px 6px 1px 0}.mm-pop .late{color:#c62828}
        </style>
        <details class="mm" open>
          <summary>Filters</summary>
          <div class="chips modes"></div>
          <div class="opts">
            <label><input type="checkbox" class="school"> School buses</label>
            <label><input type="checkbox" class="stops"> Stops</label>
            <label><input type="checkbox" class="light"> Light map</label>
          </div>
          <input class="search" type="search" placeholder="Add routes: search by number or name…" autocomplete="off">
          <div class="hits"></div>
          <div class="chips picked"></div>
        </details>
        <div class="mm-map"></div>
        <div class="mm"><div class="status muted"></div></div>
      </ha-card>`;
    const q = (s) => this.querySelector(s);
    this._el = { modes: q(".modes"), school: q(".school"), stops: q(".stops"), light: q(".light"), search: q(".search"), hits: q(".hits"), picked: q(".picked"), mapDiv: q(".mm-map"), status: q(".status") };
    this._el.mapDiv.style.height = this._height + "px";
    this._el.modes.innerHTML = MODES.map(([id, label]) => `<button class="chip" data-mode="${id}">${label}</button>`).join("");
    this._el.modes.addEventListener("click", (e) => {
      const id = e.target.dataset?.mode;
      if (!id) return;
      this._sel.modes = this._sel.modes.includes(id) ? this._sel.modes.filter((m) => m !== id) : [...this._sel.modes, id];
      this._changed();
    });
    this._el.school.addEventListener("change", () => { this._sel.school = this._el.school.checked; this._changed(); });
    this._el.stops.addEventListener("change", () => { this._sel.stops = this._el.stops.checked; this._changed(); });
    this._el.light.addEventListener("change", () => { this._sel.basemap = this._el.light.checked ? "light" : "street"; this._setBasemap(); this._save(); });
    this._el.search.addEventListener("input", () => this._search());
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
  }

  _syncControls() {
    this._el.school.checked = !!this._sel.school;
    this._el.stops.checked = !!this._sel.stops;
    this._el.light.checked = this._sel.basemap === "light";
    this._el.modes.querySelectorAll("button").forEach((b) => b.classList.toggle("on", this._sel.modes.includes(b.dataset.mode)));
    this._el.picked.innerHTML = this._sel.routes.map((r) => `<button class="chip on" data-route="${esc(r.id)}" title="Remove">${esc(r.name)} ✕</button>`).join("");
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
    const [url, attribution, nativeZoom] = BASEMAPS[this._sel.basemap] || BASEMAPS.street;
    this._base = L.tileLayer(url, { attribution, maxZoom: 19, maxNativeZoom: nativeZoom }).addTo(this._map);
    this._base.bringToBack();
    this._basemapName = this._sel.basemap;
  }

  _status(text) { if (this._el) this._el.status.textContent = text || ""; }

  async _search() {
    const text = this._el.search.value.trim().toLowerCase();
    if (!text) { this._el.hits.innerHTML = ""; return; }
    try {
      const routes = await loadRoutes(this._hass);
      const hits = routes
        .filter((r) => (this._sel.school || !r.is_school) && (!this._sel.modes.length || this._sel.modes.includes(r.mode)))
        .filter((r) => r.short_name.toLowerCase().startsWith(text) || r.long_name.toLowerCase().includes(text))
        .slice(0, 20);
      this._el.hits.innerHTML = hits.map((r) => `<button data-id="${esc(r.route_id)}" data-name="${esc(r.short_name)}">${esc(r.short_name)} <span class="muted">${esc(r.long_name)}</span></button>`).join("") || `<div class="muted">No routes found</div>`;
      this._el.hits.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
        if (this._sel.routes.length >= MAX_ROUTES) { this._status(`Up to ${MAX_ROUTES} routes at a time.`); return; }
        if (!this._sel.routes.some((r) => r.id === b.dataset.id)) this._sel.routes.push({ id: b.dataset.id, name: b.dataset.name });
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
        for (const s of shapes) if (s) lines.push({ points: s.points, color: hex(route.color, "#1976d2") });
      } catch (_) { /* a missing route must not stop the others */ }
      if (this._routeToken !== token) return;
    }
    this._layers.routes.clearLayers();
    lines.forEach((l) => L.polyline(l.points, { color: l.color, weight: 4, opacity: 0.8 }).addTo(this._layers.routes));
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
    const msg = { type: WS + "stops", include_school: !!sel.school };
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
        const marker = L.circleMarker([s.lat, s.lon], { radius: 5, weight: 2, color: "#37474f", fillColor: "#fff", fillOpacity: 1 });
        marker.bindPopup("Loading…", { minWidth: 200 });
        marker.on("popupopen", () => this._stopPopup(marker, s));
        marker.addTo(this._layers.stops);
      }
      this._status("");
    } catch (_) {
      this._status("Stops are not available yet. The timetable is still downloading.");
    }
  }

  async _stopPopup(marker, stop) {
    try {
      const rows = await this._hass.callWS({ type: WS + "departures", stop_id: stop.id, limit: 5 });
      const now = Date.now() / 1000;
      const body = rows.length
        ? `<table>${rows.map((r) => {
            const mins = Math.round((r.timestamp_expected - now) / 60);
            const when = r.status === "canceled" ? "Cancelled" : mins < 1 ? "Due" : mins < 60 ? `${mins} min` : clock(r.timestamp_expected);
            return `<tr><td><b>${esc(r.route)}</b></td><td>${esc(r.headsign || r.destination)}</td><td class="${r.status === "delayed" ? "late" : ""}">${esc(when)}</td></tr>`;
          }).join("")}</table>`
        : "No departures soon.";
      marker.setPopupContent(`<div class="mm-pop"><b>${esc(stop.name)}</b> <span class="muted">${esc(stop.id)}</span><br>${body}</div>`);
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
  }

  _drawVehicles(vehicles) {
    if (!this._map) return;
    const L = window.L;
    const showSchool = this._sel.school || this._sel.routes.length > 0;
    const seen = new Set();
    for (const v of vehicles) {
      if (v.is_school && !showSchool) continue;
      seen.add(v.id);
      const color = hex(v.color, v.mode === "ferry" ? "#0277bd" : v.mode === "train" ? "#2e7d32" : "#455a64");
      const label = esc(v.route || (v.mode === "ferry" ? "⛴" : "?"));
      const rotate = typeof v.bearing === "number" ? `<div style="position:absolute;inset:-9px;transform:rotate(${Math.round(v.bearing)}deg);pointer-events:none"><div style="margin:0 auto;width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-bottom:8px solid ${color}"></div></div>` : "";
      const icon = L.divIcon({ className: "", iconSize: [28, 22], iconAnchor: [14, 11], html: `<div style="position:relative">${rotate}<div class="mm-badge" style="background:${color}">${label}</div></div>` });
      const title = v.name || (v.route ? `Route ${v.route}` : "Vehicle");
      let marker = this._vehicleMarkers.get(v.id);
      if (marker) { marker.setLatLng([v.lat, v.lon]); marker.setIcon(icon); marker.setTooltipContent(esc(title)); }
      else {
        marker = L.marker([v.lat, v.lon], { icon, keyboard: false }).bindTooltip(esc(title)).addTo(this._layers.vehicles);
        this._vehicleMarkers.set(v.id, marker);
      }
    }
    for (const [id, marker] of this._vehicleMarkers) {
      if (!seen.has(id)) { this._layers.vehicles.removeLayer(marker); this._vehicleMarkers.delete(id); }
    }
    this._status(vehicles.length ? "" : "No live vehicles right now.");
  }
}

if (!customElements.get("metlink-map-card")) {
  customElements.define("metlink-map-card", MetlinkMapCard);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: "metlink-map-card", name: "Metlink Map", description: "Live buses, trains and ferries, routes and stops on a street map." });
}
})();
