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
      train_live_entities: [],
      bus_live_entities: [],
      ferry_live_entities: [],
      ...config,
    };
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
        properties: { entity_id: entityId }
      }));
  }

  _parseLiveTracker(entry, mode) {
    if (!entry || !entry.entity || !this.hass) return null;
    const state = this.hass.states[entry.entity];
    if (!state || !state.attributes) return null;

    const latitude = Number(state.attributes.latitude);
    const longitude = Number(state.attributes.longitude);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;

    const routeId = state.attributes.route_id;
    const labelBase = state.attributes.label || state.attributes.friendly_name || entry.entity;
    const label = routeId ? `${labelBase} (${routeId})` : labelBase;

    return {
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [longitude, latitude],
      },
      properties: {
        label,
        mode,
      },
    };
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
    categories.forEach((mode) => {
      const liveEntries = this.config[`${mode}_live_entities`] || [];
      [...liveEntries].reverse().forEach((entry) => {
        const feature = this._parseLiveTracker(entry, mode);
        if (!feature) return;

        const sourceId = `live-source-${sourceIndex}`;
        const circleLayerId = `layer-${sourceId}`;
        const textLayerId = `label-${sourceId}`;
        this.map.addSource(sourceId, {
          type: "geojson",
          data: {
            type: "FeatureCollection",
            features: [feature],
          },
        });

        this.map.addLayer({
          id: circleLayerId,
          type: "circle",
          source: sourceId,
          paint: {
            "circle-color": entry.color || VEHICLE_COLORS[mode] || "#ff9800",
            "circle-radius": entry.size || 7,
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 1.5,
          },
        });

        if (entry.show_label !== false) {
          this.map.addLayer({
            id: textLayerId,
            type: "symbol",
            source: sourceId,
            layout: {
              "text-field": ["get", "label"],
              "text-size": 11,
              "text-offset": [0, 1.2],
              "text-anchor": "top",
            },
            paint: {
              "text-color": "#ffffff",
              "text-halo-color": "#000000",
              "text-halo-width": 1.2,
            },
          });
        }

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
