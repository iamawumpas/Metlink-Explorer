import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit@2.0.0/index.js?module";

const RANDOM_COLORS = [
  '#FF0000', '#FFC0CB', '#FFA500', '#FFFF00', '#A52A2A', 
  '#90EE90', '#006400', '#00FFFF', '#ADD8E6', '#00008B', 
  '#FF00FF', '#EE82EE', '#FFFFFF'
];

const DASH_MAP = {
  "solid": [],
  "dotted": [1, 1],
  "dashed": [3, 3],
  "dash-dot": [4, 2, 1, 2],
  "sparse-dotted": [1, 5],
  "long-dash": [8, 4]
};

const DB_META_URL = "/local/metlink_explorer/db/meta.json";
const DB_META_POLL_MS = 5 * 60 * 1000;

class MetlinkExplorerEditor extends LitElement {
  static get properties() {
    return { hass: {}, _config: {} };
  }

  constructor() {
    super();
    this._dbCache = new Map();
    this._dbMetaPollTimer = null;
    this._dbMetaFingerprint = "";
  }

  connectedCallback() {
    super.connectedCallback();
    this._startDbPolling();
  }

  disconnectedCallback() {
    this._stopDbPolling();
    super.disconnectedCallback();
  }

  setConfig(config) {
    this._config = {
      train_entities: [],
      bus_entities: [],
      ferry_entities: [],
      cable_entities: [],
      icon_size: 25,
      map_projection: "normal",
      ...config
    };
  }

  async _fetchDbJson(url) {
    try {
      const res = await fetch(String(url || ""), { cache: "no-store" });
      if (!res.ok) return null;
      return await res.json();
    } catch (_) {
      return null;
    }
  }

  _dbFingerprint(meta) {
    if (!meta || typeof meta !== "object") return "";
    return Object.keys(meta).sort().map((k) => `${k}:${JSON.stringify(meta[k])}`).join("|");
  }

  async _refreshDbCache(force = false) {
    const meta = await this._fetchDbJson(DB_META_URL);
    if (!meta || typeof meta !== "object") return;
    const nextFingerprint = this._dbFingerprint(meta);
    if (!force && nextFingerprint === this._dbMetaFingerprint) return;
    this._dbMetaFingerprint = nextFingerprint;

    const modes = ["train", "bus", "ferry", "cable_car"];
    await Promise.all(modes.map(async (mode) => {
      const payload = await this._fetchDbJson(`/local/metlink_explorer/db/${mode}_route_geometry.json`);
      if (payload) this._dbCache.set(`${mode}_route_geometry`, payload);
    }));
    this.requestUpdate();
  }

  _startDbPolling() {
    if (this._dbMetaPollTimer) return;
    this._refreshDbCache(true);
    this._dbMetaPollTimer = window.setInterval(() => this._refreshDbCache(false), DB_META_POLL_MS);
  }

  _stopDbPolling() {
    if (!this._dbMetaPollTimer) return;
    window.clearInterval(this._dbMetaPollTimer);
    this._dbMetaPollTimer = null;
  }

  _dbModeFromEntityState(entityId, stateObj) {
    const attrs = stateObj?.attributes || {};
    const dataUrl = String(attrs.data_url || "").toLowerCase();
    if (dataUrl.includes("/geometry/train_")) return "train";
    if (dataUrl.includes("/geometry/bus_") || dataUrl.includes("/geometry/school_bus_")) return "bus";
    if (dataUrl.includes("/geometry/ferry_")) return "ferry";
    if (dataUrl.includes("/geometry/cable_")) return "cable_car";

    const objectId = String(entityId || "").split(".")[1] || "";
    if (/^train_/i.test(objectId)) return "train";
    if (/^(bus_|school_bus_)/i.test(objectId)) return "bus";
    if (/^ferry_/i.test(objectId)) return "ferry";
    if (/^cable_/i.test(objectId)) return "cable_car";
    return null;
  }

  _dbRouteIdFromEntity(entityId, stateObj) {
    const attrs = stateObj?.attributes || {};
    const explicit = String(attrs.route_id || "").trim();
    if (explicit) return explicit;

    const objectId = String(entityId).split(".")[1] || "";
    const match = objectId.match(/^(?:train|bus|ferry|cable|school_bus)_(.+?)_(?:route_)?geometry$/i);
    return match && match[1] ? String(match[1]).trim() : null;
  }

  _featuresFromDb(entityId, stateObj) {
    const mode = this._dbModeFromEntityState(entityId, stateObj);
    if (!mode) return [];
    const payload = this._dbCache.get(`${mode}_route_geometry`);
    const features = payload?.features;
    if (!Array.isArray(features)) return [];

    const routeId = this._dbRouteIdFromEntity(entityId, stateObj);
    if (!routeId) return features;
    return features.filter((f) => String(f?.properties?.route_id || "") === routeId);
  }

  _updateConfig(changes) {
    const event = new CustomEvent("config-changed", {
      detail: { config: { ...this._config, ...changes } },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }

  _addEntity(type) {
    const key = `${type}_entities`;
    const randomColor = RANDOM_COLORS[Math.floor(Math.random() * RANDOM_COLORS.length)];
    const newEntities = [...(this._config[key] || []), { 
      entity: '', 
      color: randomColor, 
      weight: 6, 
      style: 'solid',
      live_tracking: true,
      selected_stops: [],
    }];
    this._updateConfig({ [key]: newEntities });
  }

  _handleEntryChange(type, index, field, value) {
    const key = `${type}_entities`;
    const newEntities = this._config[key].map((item, i) => 
      i === index ? { ...item, [field]: value } : item
    );
    this._updateConfig({ [key]: newEntities });

    if (field === 'entity' && (type === 'train' || type === 'bus')) {
      const updated = newEntities[index] || {};
      const hasSelectedStops = Array.isArray(updated.selected_stops) && updated.selected_stops.length > 0;
      if (!hasSelectedStops) {
        const autoTerminalStops = this._terminalStopIdsForEntity(String(value || ''), type);
        if (autoTerminalStops.length > 0) {
          const withTermini = newEntities.map((item, i) => (
            i === index ? { ...item, selected_stops: autoTerminalStops } : item
          ));
          this._updateConfig({ [key]: withTermini });
        }
      }
    }

    // Persist live tracking to integration route config (backend source of truth)
    if (field === 'live_tracking') {
      const updated = newEntities[index];
      this._syncLiveTracking(type, updated, Boolean(value));
    }
  }

  _routeMetaFromEntity(entityId) {
    if (!entityId) return null;

    const state = this.hass?.states?.[entityId];
    const attrs = state?.attributes || {};
    let routeId = attrs.route_id ? String(attrs.route_id).trim() : "";
    let routeLabel = attrs.route_short_name ? String(attrs.route_short_name).trim() : "";

    if (!routeId) {
      const features = this._parseFeatures(entityId);
      const first = Array.isArray(features) ? features[0] : null;
      const props = first?.properties || {};
      routeId = props.route_id ? String(props.route_id).trim() : "";
      if (!routeLabel) {
        routeLabel = props.route_short_name ? String(props.route_short_name).trim() : "";
      }
    }

    if (!routeId) {
      const objectId = String(entityId).split(".")[1] || "";
      const match = objectId.match(/^(?:train|bus|ferry|cable|school_bus)_(.+?)_(?:route_)?geometry$/i);
      if (match && match[1]) {
        routeId = String(match[1]).trim();
      }
    }

    if (!routeId) return null;
    return {
      routeId,
      routeLabel: routeLabel || routeId,
    };
  }

  _syncLiveTracking(type, entry, liveTrackingEnabled) {
    if (!this.hass || !entry?.entity) return;
    const routeMeta = this._routeMetaFromEntity(entry.entity);
    if (!routeMeta?.routeId) return;

    this.hass.callService("metlink_explorer", "set_live_tracking", {
      route_id: routeMeta.routeId,
      live_tracking: Boolean(liveTrackingEnabled),
      transportation_type: type,
    });
  }

  _moveEntity(type, index, direction) {
    const key = `${type}_entities`;
    const newEntities = [...this._config[key]];
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= newEntities.length) return;
    [newEntities[index], newEntities[newIndex]] = [newEntities[newIndex], newEntities[index]];
    this._updateConfig({ [key]: newEntities });
  }

  _removeEntity(type, index) {
    const key = `${type}_entities`;
    const newEntities = this._config[key].filter((_, i) => i !== index);
    this._updateConfig({ [key]: newEntities });
  }

  _entityMatchesType(type, eid, stateObj) {
    if (!eid.startsWith("sensor.")) return false;
    const entityIdLower = String(eid || "").toLowerCase();
    const friendlyNameLower = String(stateObj?.attributes?.friendly_name || "").toLowerCase();
    const haystack = `${entityIdLower} ${friendlyNameLower}`;
    if (!haystack.includes("geometry")) return false;

    if (type === "train") return haystack.includes("train");
    if (type === "bus") return haystack.includes("bus") || haystack.includes("school");
    if (type === "ferry") return haystack.includes("ferry");
    if (type === "cable") return haystack.includes("cable");
    return false;
  }

  _parseFeatures(entityId) {
    if (!entityId || !this.hass?.states?.[entityId]) return [];
    const stateObj = this.hass.states[entityId];

    const dbFeatures = this._featuresFromDb(entityId, stateObj);
    if (Array.isArray(dbFeatures) && dbFeatures.length > 0) return dbFeatures;

    let geojson = stateObj.attributes?.geojson;
    if (!geojson) return [];
    if (typeof geojson === "string") {
      try {
        geojson = JSON.parse(geojson);
      } catch (_) {
        return [];
      }
    }
    if (!geojson || !Array.isArray(geojson.features)) return [];
    return geojson.features;
  }

  _normalizeStopIdForMode(stopId, mode) {
    const raw = String(stopId || '').trim();
    if (!raw) return '';
    if (mode === 'train') {
      return raw.toUpperCase().replace(/[\s_-]*\d+$/, '');
    }
    return raw;
  }

  _terminalStopIdsForFeatures(features, mode) {
    const ids = new Set();
    (features || []).forEach((feature) => {
      const timelineStops = feature?.properties?.timeline_stops || {};
      Object.values(timelineStops).forEach((directionStops) => {
        if (!Array.isArray(directionStops) || directionStops.length === 0) return;
        const first = this._normalizeStopIdForMode(directionStops[0]?.stop_id, mode);
        const last = this._normalizeStopIdForMode(directionStops[directionStops.length - 1]?.stop_id, mode);
        if (first) ids.add(first);
        if (last) ids.add(last);
      });
    });
    return [...ids];
  }

  _terminalStopIdsForEntity(entityId, mode) {
    const features = this._parseFeatures(entityId);
    if (!Array.isArray(features) || features.length === 0) return [];
    return this._terminalStopIdsForFeatures(features, mode);
  }

  _timelineStopsFromFeature(feature) {
    const timelineStops = feature?.properties?.timeline_stops || {};
    const dirKeys = Object.keys(timelineStops);

    // If only one direction exists, return it directly.
    if (dirKeys.length <= 1) {
      const key = dirKeys[0];
      return Array.isArray(timelineStops[key]) ? [...timelineStops[key]] : [];
    }

    // Collect all stops from all directions with their lat/lon.
    const allStops = [];
    for (const key of dirKeys) {
      const stops = timelineStops[key];
      if (!Array.isArray(stops)) continue;
      for (const stop of stops) {
        allStops.push({ ...stop, _dirKey: key });
      }
    }

    // Use direction "0" as the geographic spine. Sort all stops by their
    // projected distance along that spine so inbound+outbound stops that
    // are physically close appear adjacent in the list.
    const spine = Array.isArray(timelineStops["0"]) ? timelineStops["0"] : allStops;
    if (spine.length === 0) return allStops;

    // Build a cumulative arc-length index along the spine.
    const toRad = Math.PI / 180;
    const haversine = (lat1, lon1, lat2, lon2) => {
      const dLat = (lat2 - lat1) * toRad;
      const dLon = (lon2 - lon1) * toRad;
      const a = Math.sin(dLat / 2) ** 2
        + Math.cos(lat1 * toRad) * Math.cos(lat2 * toRad) * Math.sin(dLon / 2) ** 2;
      return 6371000 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    };

    const spineArc = [0];
    for (let i = 1; i < spine.length; i++) {
      const prev = spine[i - 1];
      const curr = spine[i];
      const d = haversine(
        Number(prev?.stop_lat), Number(prev?.stop_lon),
        Number(curr?.stop_lat), Number(curr?.stop_lon),
      );
      spineArc.push(spineArc[i - 1] + (Number.isFinite(d) ? d : 0));
    }
    const totalArc = spineArc[spineArc.length - 1] || 1;

    // Project each stop to its closest point on the spine (0–1 normalised position).
    const projectToSpine = (lat, lon) => {
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return 0;
      let bestArc = 0;
      let bestDist = Infinity;
      for (let i = 0; i < spine.length; i++) {
        const d = haversine(lat, lon, Number(spine[i]?.stop_lat), Number(spine[i]?.stop_lon));
        if (d < bestDist) { bestDist = d; bestArc = spineArc[i]; }
      }
      return bestArc / totalArc;
    };

    // Sort by spine position.
    allStops.sort((a, b) => {
      const pa = projectToSpine(Number(a?.stop_lat), Number(a?.stop_lon));
      const pb = projectToSpine(Number(b?.stop_lat), Number(b?.stop_lon));
      return pa - pb;
    });

    return allStops;
  }

  _normalizeStops(type, rawStops) {
    const unique = new Map();
    for (const stop of rawStops || []) {
      const stopId = this._normalizeStopIdForMode(stop?.stop_id, type);
      const stopName = String(stop?.stop_name || "").trim();
      if (!stopId || !stopName) continue;
      const key = stopId;
      if (!unique.has(key)) {
        unique.set(key, {
          stop_id: stopId,
          stop_name: stopName,
          label: `Stop ${stopId} :: ${stopName}.`,
        });
      }
    }
    const stops = [...unique.values()];

    if (type === "train") {
      const wellingtonIdx = stops.findIndex((s) => s.stop_name.toLowerCase().includes("wellington station"));
      if (wellingtonIdx > 0) {
        return [...stops.slice(wellingtonIdx), ...stops.slice(0, wellingtonIdx)];
      }
    }

    return stops;
  }

  _stopsForEntry(type, entry) {
    const features = this._parseFeatures(entry?.entity);
    const rawStops = [];
    for (const feature of features) {
      rawStops.push(...this._timelineStopsFromFeature(feature));
    }
    return this._normalizeStops(type, rawStops);
  }

  _addSelectedStop(type, index, stopId) {
    const key = `${type}_entities`;
    const normalized = this._normalizeStopIdForMode(stopId, type);
    if (!normalized) return;
    const newEntities = (this._config[key] || []).map((item, i) => {
      if (i !== index) return item;
      const current = Array.isArray(item.selected_stops)
        ? item.selected_stops.map((id) => this._normalizeStopIdForMode(id, type)).filter(Boolean)
        : [];
      if (current.includes(normalized)) return item;
      return { ...item, selected_stops: [...current, normalized] };
    });
    this._updateConfig({ [key]: newEntities });
  }

  _removeSelectedStop(type, index, stopId) {
    const key = `${type}_entities`;
    const normalized = this._normalizeStopIdForMode(stopId, type);
    const newEntities = (this._config[key] || []).map((item, i) => {
      if (i !== index) return item;
      const current = Array.isArray(item.selected_stops)
        ? item.selected_stops.map((id) => this._normalizeStopIdForMode(id, type)).filter(Boolean)
        : [];
      return { ...item, selected_stops: current.filter((id) => id !== normalized) };
    });
    this._updateConfig({ [key]: newEntities });
  }

  render() {
    if (!this.hass || !this._config) return html`<div>Loading...</div>`;
    return html`
      <div class="card-config">
        <div class="header">MAP DISPLAY SETTINGS</div>
        <div class="manual-grid">
          <div class="grid-item">
            <label class="manual-label">Map Style</label>
            <ha-selector
              .hass=${this.hass}
              .selector=${{ select: { mode: "dropdown", options: [
                { value: "voyager", label: "Voyager" },
                { value: "positron", label: "Light" },
                { value: "satellite", label: "Satellite" },
                { value: "topo", label: "Topo" }
              ]}}}
              .value=${this._config.map_style || 'voyager'}
              @value-changed=${(e) => this._updateConfig({map_style: e.detail.value})}
            ></ha-selector>
          </div>
          <div class="grid-item">
            <label class="manual-label">Center map on...</label>
            <ha-selector
              .hass=${this.hass}
              .selector=${{ entity: { domain: "zone" } }}
              .value=${this._config.center_map}
              @value-changed=${(e) => this._updateConfig({center_map: e.detail.value})}
            ></ha-selector>
          </div>
        </div>
        <div class="full-width">
            <label class="manual-label">Zoom Level</label>
            <ha-selector
             .hass=${this.hass}
             .selector=${{ number: { min: 10, max: 18, step: 1, mode: "slider" } }}
             .value=${this._config.zoom}
             @value-changed=${(e) => this._updateConfig({zoom: e.detail.value})}
           ></ha-selector>
        </div>
        <div class="full-width">
            <label class="manual-label">Icon Size</label>
            <ha-selector
             .hass=${this.hass}
             .selector=${{ number: { min: 19, max: 31, step: 1, mode: "slider" } }}
             .value=${this._config.icon_size ?? 25}
             @value-changed=${(e) => this._updateConfig({icon_size: Number(e.detail.value)})}
           ></ha-selector>
        </div>
        <div class="full-width map-projection-row">
          <label class="manual-label">Map Projection</label>
          <div class="projection-toggle" role="group" aria-label="Map Projection">
            <span class="projection-label">Normal View</span>
            <label class="projection-switch" title="Map Projection">
              <input
                type="checkbox"
                .checked=${String(this._config.map_projection || "normal") === "isometric"}
                @change=${(e) => this._updateConfig({ map_projection: e.target.checked ? "isometric" : "normal" })}
              >
              <span class="projection-slider"></span>
            </label>
            <span class="projection-label">Isometric View</span>
          </div>
        </div>
        ${this._renderSection('train', 'Train Routes', ['train', 'geometry'])}
        ${this._renderSection('bus', 'Bus Routes', ['bus', 'school', 'geometry'])}
        ${this._renderSection('ferry', 'Ferry Routes', ['ferry', 'geometry'])}
        ${this._renderSection('cable', 'Cable Car Routes', ['cable', 'geometry'])}
      </div>
    `;
  }

  _renderSection(type, title, filters) {
    const entities = this._config[`${type}_entities`] || [];
    const allSelected = [
        ...(this._config.train_entities || []),
        ...(this._config.bus_entities || []),
        ...(this._config.ferry_entities || []),
        ...(this._config.cable_entities || [])
    ].map(e => e.entity).filter(e => e !== '');

    return html`
      <div class="section">
        <div class="section-header">${title}</div>
        <div class="entity-list">
          ${entities.map((entry, idx) => {
            const filteredEntities = Object.keys(this.hass.states).filter(eid => {
                const stateObj = this.hass.states[eid];
                const matchesFilter = this._entityMatchesType(type, eid, stateObj) || filters.every(f => {
                  const token = f.toLowerCase();
                  return eid.toLowerCase().includes(token) || String(stateObj.attributes.friendly_name || "").toLowerCase().includes(token);
                });
                const isNotSelected = !allSelected.includes(eid) || eid === entry.entity;
                return eid.startsWith("sensor.") && matchesFilter && isNotSelected;
            });

            const allStops = this._stopsForEntry(type, entry);
            const selectedStops = Array.isArray(entry.selected_stops)
              ? entry.selected_stops
                  .map((id) => this._normalizeStopIdForMode(id, type))
                  .filter(Boolean)
              : [];
            const selectedSet = new Set(selectedStops);
            const availableStops = allStops.filter((s) => !selectedSet.has(String(s.stop_id)));
            const selectedStopObjects = selectedStops
              .map((id) => allStops.find((s) => String(s.stop_id) === String(id)) || {
                stop_id: String(id),
                stop_name: String(id),
                label: `Stop ${id} :: ${id}.`,
              });

            return html`
              <div class="entity-row">
                <div class="row-main">
                  <ha-selector
                    .hass=${this.hass}
                    .selector=${{ select: { mode: "dropdown", options: filteredEntities.map(eid => ({
                        value: eid,
                        label: this.hass.states[eid].attributes.friendly_name || eid
                    }))}}}
                    .value=${entry.entity}
                    @value-changed=${(e) => this._handleEntryChange(type, idx, 'entity', e.detail.value)}
                  ></ha-selector>
                  <div class="controls">
                    <ha-icon icon="mdi:arrow-up" @click=${() => this._moveEntity(type, idx, -1)}></ha-icon>
                    <ha-icon icon="mdi:arrow-down" @click=${() => this._moveEntity(type, idx, 1)}></ha-icon>
                    <ha-icon icon="mdi:delete" @click=${() => this._removeEntity(type, idx)}></ha-icon>
                  </div>
                </div>
                <div class="row-styling">
                  <div class="style-item">
                    <label>Color</label>
                    <input type="color" .value=${entry.color} @input=${(e) => this._handleEntryChange(type, idx, 'color', e.target.value)}>
                  </div>
                  <div class="style-item">
                    <label>Weight (${entry.weight}px)</label>
                    <input type="range" min="2" max="12" .value=${entry.weight} @input=${(e) => this._handleEntryChange(type, idx, 'weight', parseInt(e.target.value))}>
                  </div>
                  <div class="style-item">
                    <label>Style</label>
                    <select .value=${entry.style} @change=${(e) => this._handleEntryChange(type, idx, 'style', e.target.value)}>
                      ${Object.keys(DASH_MAP).map(s => html`<option value="${s}">${s.charAt(0).toUpperCase() + s.slice(1)}</option>`)}
                    </select>
                  </div>
                  <div class="style-item">
                    <label>Live Tracking</label>
                    <input type="checkbox" .checked=${entry.live_tracking === true} @change=${(e) => this._handleEntryChange(type, idx, 'live_tracking', e.target.checked)}>
                  </div>
                </div>
                <div class="stop-config">
                  <label class="stop-label">Selected Stops</label>
                  <div class="stop-picker-row">
                    <select @change=${(e) => {
                      const stopId = e.target.value;
                      if (!stopId) return;
                      this._addSelectedStop(type, idx, stopId);
                      e.target.value = "";
                    }}>
                      <option value="">Add stop...</option>
                      ${availableStops.map((stop) => html`<option value=${stop.stop_id}>${stop.label}</option>`) }
                    </select>
                  </div>
                  <div class="selected-stop-list">
                    ${selectedStopObjects.length === 0
                      ? html`<div class="empty-stop-text">No stops selected.</div>`
                      : selectedStopObjects.map((stop) => html`
                          <div class="selected-stop-item">
                            <span>${stop.label}</span>
                            <ha-icon icon="mdi:delete" @click=${() => this._removeSelectedStop(type, idx, stop.stop_id)}></ha-icon>
                          </div>
                        `)}
                  </div>
                </div>
              </div>
            `;
          })}
        </div>
        <mwc-button @click=${() => this._addEntity(type)}>
          <ha-icon icon="mdi:plus"></ha-icon> Add ${type} Route
        </mwc-button>
      </div>
    `;
  }

  static get styles() {
    return css`
      .card-config { padding: 4px; }
      .header { font-weight: 500; margin-bottom: 20px; text-transform: uppercase; font-size: 12px; color: var(--secondary-text-color); }
      .section { margin-top: 24px; border-top: 1px solid var(--divider-color); padding-top: 16px; }
      .section-header { font-size: 14px; font-weight: 500; margin-bottom: 12px; color: var(--primary-text-color); }
      .entity-row { background: var(--secondary-background-color); padding: 12px; border-radius: 8px; margin-bottom: 12px; border: 1px solid var(--divider-color); }
      .row-main { display: flex; align-items: center; gap: 8px; }
      ha-selector { flex: 1; }
      .controls ha-icon { cursor: pointer; padding: 4px; opacity: 0.7; }
      .controls ha-icon:hover { opacity: 1; color: var(--primary-color); }
      .row-styling { display: flex; gap: 16px; margin-top: 12px; padding-top: 12px; border-top: 1px dashed var(--divider-color); }
      .style-item { flex: 1; display: flex; flex-direction: column; font-size: 11px; color: var(--secondary-text-color); }
      .style-item label { margin-bottom: 4px; }
      .manual-grid { display: flex; gap: 16px; margin-bottom: 16px; }
      .grid-item { flex: 1; }
      .manual-label { display: block; font-size: 14px; margin-bottom: 8px; }
      .full-width { margin-top: 16px; }
      input[type="color"] { width: 100%; height: 30px; border: none; background: none; cursor: pointer; }
      .stop-config { margin-top: 12px; padding-top: 12px; border-top: 1px dashed var(--divider-color); }
      .stop-label { display: block; margin-bottom: 8px; font-size: 12px; color: var(--secondary-text-color); }
      .stop-picker-row select { width: 100%; padding: 6px; border-radius: 6px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); }
      .selected-stop-list { margin-top: 8px; display: flex; flex-direction: column; gap: 6px; }
      .selected-stop-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 12px; background: var(--secondary-background-color); border: 1px solid var(--divider-color); border-radius: 6px; padding: 6px 8px; }
      .selected-stop-item ha-icon { cursor: pointer; opacity: 0.75; }
      .selected-stop-item ha-icon:hover { opacity: 1; color: var(--error-color); }
      .empty-stop-text { font-size: 12px; color: var(--secondary-text-color); opacity: 0.85; }
      .map-projection-row { margin-top: 18px; }
      .projection-toggle { display: inline-flex; align-items: center; gap: 10px; }
      .projection-label { font-size: 12px; color: var(--secondary-text-color); user-select: none; }
      .projection-switch { position: relative; display: inline-block; width: 50px; height: 28px; }
      .projection-switch input { opacity: 0; width: 0; height: 0; position: absolute; }
      .projection-slider {
        position: absolute;
        inset: 0;
        cursor: pointer;
        background: rgba(127, 127, 127, 0.35);
        border: 1px solid var(--divider-color);
        transition: background-color 160ms ease;
        border-radius: 999px;
      }
      .projection-slider:before {
        content: "";
        position: absolute;
        width: 22px;
        height: 22px;
        left: 2px;
        top: 2px;
        background: #fff;
        border-radius: 50%;
        transition: transform 160ms ease;
      }
      .projection-switch input:checked + .projection-slider {
        background: var(--primary-color);
      }
      .projection-switch input:checked + .projection-slider:before {
        transform: translateX(22px);
      }
    `;
  }
}
customElements.define("metlink-explorer-map-editor", MetlinkExplorerEditor);
