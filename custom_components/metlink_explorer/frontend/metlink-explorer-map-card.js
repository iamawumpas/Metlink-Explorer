import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit@2.0.0/index.js?module";

const loadMapLibre = new Promise((resolve) => {
  if (window.maplibregl) { resolve(); } else {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/maplibre-gl@4.1.2/dist/maplibre-gl.css";
    document.head.appendChild(link);
    const script = document.createElement("script");
    script.src = "https://unpkg.com/maplibre-gl@4.1.2/dist/maplibre-gl.js";
    script.onload = () => resolve();
    document.head.appendChild(script);
  }
});

const DASH_MAP = {
  "solid": [],
  "dotted": [1, 1],
  "dashed": [3, 3],
  "dash-dot": [4, 2, 1, 2],
  "sparse-dotted": [1, 5],
  "long-dash": [8, 4]
};

const VEHICLE_COLORS = {
  train: "#1e88e5",
  bus: "#43a047",
  ferry: "#00acc1",
};

class MetlinkExplorerCard extends LitElement {
  static get properties() {
    return { hass: {}, config: {} };
  }

  static async getConfigElement() {
    try {
      await import("/metlink_explorer_frontend/metlink-explorer-editor.js");
    } catch (e) { console.error("Failed to load editor:", e); }
    return document.createElement("metlink-explorer-map-editor");
  }

  static getStubConfig() {
    return { center_map: "zone.home", zoom: 12, map_style: "voyager" };
  }

  setConfig(config) {
    this.config = {
      train_entities: [],
      bus_entities: [],
      ferry_entities: [],
      live_max_age_seconds: 120,
      ...config,
    };
  }

  _hexToRgb(hex) {
    const normalized = String(hex || "").replace("#", "");
    if (normalized.length !== 6) return null;
    const value = Number.parseInt(normalized, 16);
    if (Number.isNaN(value)) return null;
    return {
      r: (value >> 16) & 255,
      g: (value >> 8) & 255,
      b: value & 255,
    };
  }

  _contrastTextColor(backgroundHex) {
    const rgb = this._hexToRgb(backgroundHex);
    if (!rgb) return "#ffffff";
    const luminance = (0.299 * rgb.r) + (0.587 * rgb.g) + (0.114 * rgb.b);
    return luminance > 150 ? "#000000" : "#ffffff";
  }

  _parseTrackerTimestamp(value) {
    if (value === null || value === undefined) return null;
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric <= 0) return null;
    return numeric;
  }

  _routeMetaFromFeatures(features) {
    if (!Array.isArray(features) || features.length === 0) return null;
    const first = features[0];
    const props = first?.properties || {};
    const routeId = props.route_id ? String(props.route_id) : null;
    const routeShort = props.route_short_name ? String(props.route_short_name) : routeId;
    if (!routeId) return null;
    return {
      routeId,
      routeLabel: routeShort || routeId,
    };
  }

  _tripRouteKey(tripId) {
    if (!tripId) return "";
    const tripText = String(tripId);
    const underscoreIdx = tripText.indexOf("_");
    if (underscoreIdx <= 0) return "";
    return tripText.slice(0, underscoreIdx).trim();
  }

  _routeKeys(routeMeta) {
    const keys = new Set();
    if (!routeMeta) return keys;
    keys.add(String(routeMeta.routeId || "").trim());
    keys.add(String(routeMeta.routeLabel || "").trim());
    return new Set([...keys].filter(Boolean));
  }

  _vehicleRouteKeys(state) {
    const attrs = state?.attributes || {};
    const keys = new Set();
    const fromTrip = this._tripRouteKey(attrs.trip_id);
    if (fromTrip) keys.add(fromTrip);
    const routeId = attrs.route_id ? String(attrs.route_id).trim() : "";
    if (routeId) keys.add(routeId);
    return keys;
  }

  _matchesRoute(state, routeMeta) {
    const routeKeys = this._routeKeys(routeMeta);
    if (routeKeys.size === 0) return false;
    const vehicleKeys = this._vehicleRouteKeys(state);
    if (vehicleKeys.size === 0) return false;
    for (const key of vehicleKeys) {
      if (routeKeys.has(key)) return true;
    }
    return false;
  }

  _liveFeaturesForRoute(routeEntry, mode, routeMeta) {
    if (!this.hass || !routeMeta) return [];
    const maxAge = Number(this.config.live_max_age_seconds || 120);
    const nowEpoch = Date.now() / 1000;
    const markerColor = routeEntry.color || VEHICLE_COLORS[mode] || "#ff9800";
    const textColor = this._contrastTextColor(markerColor);

    return Object.entries(this.hass.states)
      .filter(([entityId, state]) => {
        if (!entityId.startsWith("device_tracker.")) return false;
        if (!state || !state.attributes) return false;
        if (state.attributes.restored === true) return false;

        if (!this._matchesRoute(state, routeMeta)) return false;

        const lat = Number(state.attributes.latitude);
        const lon = Number(state.attributes.longitude);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return false;

        const ts = this._parseTrackerTimestamp(state.attributes.timestamp);
        if (!ts) return false;
        return (nowEpoch - ts) <= maxAge;
      })
      .map(([entityId, state]) => {
        const lat = Number(state.attributes.latitude);
        const lon = Number(state.attributes.longitude);
        return {
          type: "Feature",
          geometry: {
            type: "Point",
            coordinates: [lon, lat],
          },
          properties: {
            entity_id: entityId,
            route_label: routeMeta.routeLabel,
            marker_color: markerColor,
            text_color: textColor,
          },
        };
      });
  }

  connectedCallback() {
    super.connectedCallback();
    setTimeout(() => this._forceSectionBreakout(), 500);
  }

  _forceSectionBreakout() {
    let el = this;
    while (el) {
      if (el.tagName === 'HUI-CARD' || el.style?.gridColumnEnd || el.classList?.contains('card')) {
        el.style.setProperty('grid-column', '1 / -1', 'important');
        el.style.setProperty('width', '100%', 'important');
      }
      if (el.tagName === 'HUI-SECTION') break;
      el = el.parentElement || el.parentNode;
    }
  }

  _getStyleUrl(style) {
    const styles = {
      'voyager': 'https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
      'positron': 'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
      'standard': 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      'satellite': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      'topo': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}'
    };
    return styles[style] || styles['voyager'];
  }

  _parseRouteGeometry(entityId) {
    const state = this.hass.states[entityId];
    if (!state || !state.attributes || !state.attributes.geojson) return null;

    let geojson = state.attributes.geojson;
    if (typeof geojson === 'string') {
      try { geojson = JSON.parse(geojson); } catch (e) { return null; }
    }

    return geojson.features
      .filter(f => f.geometry && (f.geometry.type === "MultiLineString" || f.geometry.type === "LineString"))
      .map(f => ({
        type: "Feature",
        geometry: f.geometry,
        properties: {
          ...(f.properties || {}),
          entity_id: entityId,
        }
      }));
  }

  _renderLiveVehicles() {
    if (!this.map || !this.map.isStyleLoaded()) return;

    const liveSources = Array.from({ length: 200 }, (_, i) => `live-source-${i}`);
    liveSources.forEach((sourceId) => {
      const circleLayerId = `layer-${sourceId}`;
      const textLayerId = `label-${sourceId}`;
      if (this.map.getLayer(textLayerId)) this.map.removeLayer(textLayerId);
      if (this.map.getLayer(circleLayerId)) this.map.removeLayer(circleLayerId);
      if (this.map.getSource(sourceId)) this.map.removeSource(sourceId);
    });

    const categories = ["train", "bus", "ferry"];
    let sourceIndex = 0;
    const nowEpoch = Date.now() / 1000;
    const maxAge = Number(this.config.live_max_age_seconds || 120);
    const allTrackers = Object.entries(this.hass?.states || {})
      .filter(([id]) => id.startsWith("device_tracker."));
    console.log(`[MetlinkExplorer] _renderLiveVehicles: ${allTrackers.length} device_tracker entities; nowEpoch=${nowEpoch.toFixed(0)}, maxAge=${maxAge}s`);

    categories.forEach((mode) => {
      const routeEntries = this.config[`${mode}_entities`] || [];
      [...routeEntries].reverse().forEach((entry) => {
        if (entry.live_tracking !== true) {
          console.log(`[MetlinkExplorer] ${mode} entry ${entry.entity}: live_tracking=${JSON.stringify(entry.live_tracking)} — skipping`);
          return;
        }

        const routeFeatures = this._parseRouteGeometry(entry.entity);
        const routeMeta = this._routeMetaFromFeatures(routeFeatures || []);
        console.log(`[MetlinkExplorer] ${mode} entry ${entry.entity}: routeFeatures=${routeFeatures?.length ?? "null"}, routeMeta=${JSON.stringify(routeMeta)}`);
        if (!routeMeta) return;

        const vehicleFeatures = this._liveFeaturesForRoute(entry, mode, routeMeta);
        console.log(`[MetlinkExplorer] ${mode} entry ${entry.entity}: vehicleFeatures=${vehicleFeatures.length}`);
        if (vehicleFeatures.length === 0) {
          // Log why each tracker was rejected
          allTrackers.forEach(([entityId, state]) => {
            const attrs = state?.attributes || {};
            const restored = attrs.restored === true;
            const matches = this._matchesRoute(state, routeMeta);
            const lat = Number(attrs.latitude);
            const lon = Number(attrs.longitude);
            const hasCoords = Number.isFinite(lat) && Number.isFinite(lon);
            const ts = this._parseTrackerTimestamp(attrs.timestamp);
            const fresh = ts ? (nowEpoch - ts) <= maxAge : false;
            if (matches) {
              console.log(`[MetlinkExplorer]   MATCHED ${entityId}: restored=${restored}, hasCoords=${hasCoords}, ts=${ts}, fresh=${fresh}, lat=${lat}, lon=${lon}`);
            }
          });
          return;
        }

        const sourceId = `live-source-${sourceIndex}`;
        const circleLayerId = `layer-${sourceId}`;
        const textLayerId = `label-${sourceId}`;
        this.map.addSource(sourceId, {
          type: "geojson",
          data: {
            type: "FeatureCollection",
            features: vehicleFeatures,
          },
        });

        this.map.addLayer({
          id: circleLayerId,
          type: "circle",
          source: sourceId,
          paint: {
            "circle-color": ["get", "marker_color"],
            "circle-radius": 11,
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 1.5,
          },
        });

        this.map.addLayer({
          id: textLayerId,
          type: "symbol",
          source: sourceId,
          layout: {
            "text-field": ["get", "route_label"],
            "text-size": 10,
            "text-offset": [0, 0],
            "text-anchor": "center",
            "text-allow-overlap": true,
          },
          paint: {
            "text-color": ["get", "text_color"],
            "text-halo-color": "#000000",
            "text-halo-width": 0.8,
          },
        });

        sourceIndex += 1;
      });
    });
  }

  _renderRoutes() {
    if (!this.map || !this.map.isStyleLoaded()) return;

    const categories = ['ferry', 'bus', 'train'];
    
    // Clear existing
    const currentSources = Array.from({length: 100}, (_, i) => `route-source-${i}`);
    currentSources.forEach(s => {
      if (this.map.getLayer(`layer-${s}`)) this.map.removeLayer(`layer-${s}`);
      if (this.map.getSource(s)) this.map.removeSource(s);
    });

    let layerIdx = 0;
    categories.forEach(cat => {
      const entries = this.config[`${cat}_entities`] || [];
      [...entries].reverse().forEach(entry => {
        const features = this._parseRouteGeometry(entry.entity);
        if (!features) return;

        const sourceId = `route-source-${layerIdx}`;
        this.map.addSource(sourceId, {
          type: 'geojson',
          data: { type: 'FeatureCollection', features: features }
        });

        const weight = entry.weight || 6;
        const dashBase = DASH_MAP[entry.style] || [];
        // Scale dasharray by weight to keep gaps visible at lower zooms
        const dashArray = dashBase.map(v => v * (weight / 3));

        this.map.addLayer({
          id: `layer-${sourceId}`,
          type: 'line',
          source: sourceId,
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': entry.color || '#ffa500',
            'line-width': weight,
            ...(dashArray.length > 0 ? { 'line-dasharray': dashArray } : {})
          }
        });
        layerIdx++;
      });
    });

    this._renderLiveVehicles();
  }

  updated(changedProps) {
    if (this.map) {
      if (changedProps.has('config')) {
        const oldConfig = changedProps.get('config');
        if (oldConfig?.map_style !== this.config.map_style) this._updateMapStyle();
        this._centerMap();
        this._renderRoutes();
      }
      if (changedProps.has('hass')) this._renderRoutes();
    }
    this._forceSectionBreakout();
  }

  async firstUpdated() {
    await loadMapLibre;
    this._initMap();
  }

  _initMap() {
    const container = this.shadowRoot.getElementById('map');
    if (!container || this.map) return;

    this.map = new maplibregl.Map({
      container: container,
      style: {
        version: 8,
        sources: {
          'raster-tiles': {
            type: 'raster',
            tiles: [this._getStyleUrl(this.config.map_style)],
            tileSize: 256,
          }
        },
        layers: [{ id: 'simple-tiles', type: 'raster', source: 'raster-tiles' }]
      },
      center: [174.88, -41.20],
      zoom: this.config.zoom || 12,
      attributionControl: false
    });

    this.map.on('load', () => {
      this.map.resize();
      this._centerMap();
      this._renderRoutes();
    });

    this._resizeObserver = new ResizeObserver(() => {
      if (this.map) this.map.resize();
    });
    this._resizeObserver.observe(this);
  }

  _centerMap() {
    if (!this.map || !this.hass || !this.config.center_map) return;
    const zone = this.hass.states[this.config.center_map];
    if (zone?.attributes.latitude) {
      this.map.easeTo({
        center: [zone.attributes.longitude, zone.attributes.latitude],
        zoom: this.config.zoom || 12,
        duration: 1000
      });
    }
  }

  _updateMapStyle() {
    if (!this.map) return;
    const newUrl = this._getStyleUrl(this.config.map_style);
    if (this.map.getSource('raster-tiles')) {
      this.map.removeLayer('simple-tiles');
      this.map.removeSource('raster-tiles');
    }
    this.map.addSource('raster-tiles', {
      type: 'raster',
      tiles: [newUrl],
      tileSize: 256,
    });
    this.map.addLayer({ id: 'simple-tiles', type: 'raster', source: 'raster-tiles' });
    this.map.once('idle', () => this._renderRoutes());
  }

  render() {
    return html`<ha-card><div id="map"></div></ha-card>`;
  }

  static get styles() {
    return css`
      :host { display: block; width: 100% !important; height: calc(100vh - 64px); grid-column: 1 / -1 !important; }
      ha-card { height: 100%; width: 100%; position: relative; overflow: hidden; background: #1c1c1c; border: none; }
      #map { height: 100%; width: 100%; }
    `;
  }
}

customElements.define("metlink-explorer-map-card", MetlinkExplorerCard);
