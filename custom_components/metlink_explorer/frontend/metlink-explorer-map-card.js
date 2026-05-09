import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit@2.0.0/index.js?module";

console.log("[MetlinkExplorer] map card script loaded (build 0.7.26)");

const loadMapLibre = new Promise((resolve, reject) => {
  if (window.maplibregl) { resolve(); } else {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/maplibre-gl@4.1.2/dist/maplibre-gl.css";
    document.head.appendChild(link);
    const script = document.createElement("script");
    script.src = "https://unpkg.com/maplibre-gl@4.1.2/dist/maplibre-gl.js";
    script.onload = () => {
      console.log("[MetlinkExplorer] MapLibre script loaded");
      resolve();
    };
    script.onerror = () => {
      console.error("[MetlinkExplorer] MapLibre script failed to load");
      reject(new Error("MapLibre load failed"));
    };
    document.head.appendChild(script);

    setTimeout(() => {
      if (!window.maplibregl) {
        console.error("[MetlinkExplorer] MapLibre still unavailable after timeout");
        reject(new Error("MapLibre timeout"));
      }
    }, 10000);
  }
});

// Dash values are in line-width units (MapLibre native). No pixel conversion.
// A value of 1 = one line-width. Round line-caps close a 1-unit dash into a circle (dot).
const DASH_MAP = {
  "solid": [],
  "dotted": [1, 2.5],
  "dashed": [4, 2],
  "dash-dot": [4, 2, 1, 2],
  "sparse-dotted": [1, 5],
  "long-dash": [10, 3],
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
    return { center_map: "zone.home", zoom: 12, map_style: "voyager", icon_size: 33 };
  }

  setConfig(config) {
    console.log("[MetlinkExplorer] setConfig called", {
      trainEntities: Array.isArray(config?.train_entities) ? config.train_entities.length : 0,
      busEntities: Array.isArray(config?.bus_entities) ? config.bus_entities.length : 0,
      ferryEntities: Array.isArray(config?.ferry_entities) ? config.ferry_entities.length : 0,
      centerMap: config?.center_map,
      zoom: config?.zoom,
      iconSize: config?.icon_size,
    });
    this.config = {
      train_entities: [],
      bus_entities: [],
      ferry_entities: [],
      live_max_age_seconds: 120,
      icon_size: 33,
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

  _badgeShapeId(markerColor, diameter, borderWidth) {
    const safeBg = String(markerColor || "").replace("#", "");
    return `metlink-shape-${safeBg}-${diameter}-${borderWidth}`;
  }

  _badgeTextId(routeLabel, textColor, diameter, fontSize) {
    const safeLabel = String(routeLabel || "").replace(/[^a-zA-Z0-9_-]/g, "_");
    const safeFg = String(textColor || "").replace("#", "");
    return `metlink-text-${safeLabel}-${safeFg}-${diameter}-${fontSize}`;
  }

  _ensureBadgeShape(imageId, markerColor, diameter, borderWidth, dpr) {
    if (!this.map || this.map.hasImage(imageId)) return;

    // Teardrop canvas: 1.3× taller than wide so the tail fits above the circle.
    // Circle center sits at canvas center so icon-anchor:"center" = vehicle coordinate.
    const tailFactor = 1.3;
    const pixelW = Math.max(1, Math.round(diameter * dpr));
    const pixelH = Math.max(1, Math.round(diameter * tailFactor * dpr));
    const canvas = document.createElement("canvas");
    canvas.width = pixelW;
    canvas.height = pixelH;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.scale(dpr, dpr);

    const cssH = diameter * tailFactor;
    const cx   = diameter / 2;
    const cy   = cssH / 2;          // circle center at canvas center
    const r    = Math.max(8, diameter / 2 - borderWidth);
    const tipY = borderWidth;        // tip at top (bearing=0 → north)

    ctx.beginPath();
    ctx.moveTo(cx, tipY);
    ctx.quadraticCurveTo(cx - r * 0.15, cy - r, cx - r, cy); // left side
    ctx.arc(cx, cy, r, Math.PI, 0, true);                      // bottom arc
    ctx.quadraticCurveTo(cx + r * 0.15, cy - r, cx, tipY);   // right side
    ctx.closePath();

    ctx.fillStyle = markerColor;
    ctx.fill();
    ctx.lineWidth = borderWidth;
    ctx.strokeStyle = "#ffffff";
    ctx.stroke();

    const imageData = ctx.getImageData(0, 0, pixelW, pixelH);
    this.map.addImage(imageId, imageData, { pixelRatio: dpr });
  }

  _ensureBadgeText(imageId, routeLabel, textColor, haloColor, diameter, fontSize, dpr) {
    if (!this.map || this.map.hasImage(imageId) || !routeLabel) return;

    // Square canvas matching the circle diameter. Rendered as a separate non-rotating
    // symbol layer so the route label always stays upright regardless of vehicle heading.
    const pixelSize = Math.max(1, Math.round(diameter * dpr));
    const canvas = document.createElement("canvas");
    canvas.width = pixelSize;
    canvas.height = pixelSize;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.scale(dpr, dpr);

    const center = diameter / 2;
    ctx.font = `700 ${fontSize}px Arial, Helvetica, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.lineJoin = "round";
    ctx.strokeStyle = haloColor || "rgba(0,0,0,0.45)";
    ctx.lineWidth = Math.max(2, Math.round(fontSize * 0.14));
    ctx.strokeText(routeLabel, center, center + 0.5);
    ctx.fillStyle = textColor;
    ctx.fillText(routeLabel, center, center + 0.5);

    const imageData = ctx.getImageData(0, 0, pixelSize, pixelSize);
    this.map.addImage(imageId, imageData, { pixelRatio: dpr });
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

  _routeMetaFallback(entry) {
    const state = this.hass?.states?.[entry?.entity] || null;
    const attrs = state?.attributes || {};

    const attrRouteId = attrs.route_id ? String(attrs.route_id).trim() : "";
    const attrRouteShort = attrs.route_short_name ? String(attrs.route_short_name).trim() : "";
    if (attrRouteId || attrRouteShort) {
      return {
        routeId: attrRouteId || attrRouteShort,
        routeLabel: attrRouteShort || attrRouteId,
      };
    }

    const entityId = String(entry?.entity || "");
    const parts = entityId.split(".");
    const objectId = parts.length > 1 ? parts[1] : entityId;
    const match = objectId.match(/^(?:train|bus|ferry)_(.+?)_(?:route_)?geometry$/i);
    if (!match) return null;

    const token = String(match[1] || "").trim();
    if (!token) return null;
    return {
      routeId: token,
      routeLabel: token.toUpperCase(),
    };
  }

  _normalizeKey(key) {
    return String(key || "").trim().toLowerCase();
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
    keys.add(this._normalizeKey(routeMeta.routeId));
    keys.add(this._normalizeKey(routeMeta.routeLabel));
    return new Set([...keys].filter(Boolean));
  }

  _vehicleRouteKeys(state) {
    const attrs = state?.attributes || {};
    const keys = new Set();
    const fromTrip = this._tripRouteKey(attrs.trip_id);
    if (fromTrip) keys.add(this._normalizeKey(fromTrip));
    const routeId = attrs.route_id ? String(attrs.route_id).trim() : "";
    if (routeId) keys.add(this._normalizeKey(routeId));
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
        const rawBearing = state.attributes.bearing;
        const bearing = (rawBearing !== null && rawBearing !== undefined && Number.isFinite(Number(rawBearing)))
          ? Number(rawBearing) : 0;
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
            text_halo_color: textColor === "#000000" ? "rgba(255,255,255,0.85)" : "rgba(0,0,0,0.45)",
            bearing: bearing,
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

  _normalizeCoordinatePair(pair) {
    if (!Array.isArray(pair) || pair.length < 2) return pair;

    const first = Number(pair[0]);
    const second = Number(pair[1]);
    if (!Number.isFinite(first) || !Number.isFinite(second)) return pair;

    const firstLooksLikeLat = Math.abs(first) <= 90;
    const secondLooksLikeLon = Math.abs(second) <= 180;
    const secondLooksLikeLat = Math.abs(second) <= 90;
    const firstLooksLikeLon = Math.abs(first) <= 180;

    if (firstLooksLikeLat && secondLooksLikeLon && (!firstLooksLikeLon || Math.abs(second) > 90)) {
      return [second, first];
    }

    return [first, second];
  }

  _normalizeGeometryCoordinates(coordinates) {
    if (!Array.isArray(coordinates) || coordinates.length === 0) return coordinates;

    if (typeof coordinates[0]?.[0] === "number") {
      return coordinates.map((pair) => this._normalizeCoordinatePair(pair));
    }

    return coordinates.map((segment) => this._normalizeGeometryCoordinates(segment));
  }

  _normalizeRouteGeometry(geometry) {
    if (!geometry || typeof geometry !== "object") return geometry;
    const type = geometry.type;
    if (type !== "LineString" && type !== "MultiLineString") return geometry;

    const coordinates = this._normalizeGeometryCoordinates(geometry.coordinates);
    return {
      ...geometry,
      coordinates,
    };
  }

  _parseRouteGeometry(entityId) {
    const states = this.hass?.states;
    if (!states) return null;

    const state = states[entityId];
    if (!state || !state.attributes || !state.attributes.geojson) return null;

    let geojson = state.attributes.geojson;
    if (typeof geojson === 'string') {
      try { geojson = JSON.parse(geojson); } catch (e) { return null; }
    }

    if (!geojson || !Array.isArray(geojson.features)) return null;

    return geojson.features
      .filter(f => f.geometry && (f.geometry.type === "MultiLineString" || f.geometry.type === "LineString"))
      .map(f => ({
        type: "Feature",
        geometry: this._normalizeRouteGeometry(f.geometry),
        properties: {
          ...(f.properties || {}),
          entity_id: entityId,
        }
      }));
  }

  _renderLiveVehicles() {
    if (!this.map) return;

    if (!this.map.isStyleLoaded()) {
      console.log("[MetlinkExplorer] _renderLiveVehicles deferred: style not loaded");
      this.map.once('idle', () => this._renderLiveVehicles());
      return;
    }

    const liveSources = Array.from({ length: 200 }, (_, i) => `live-source-${i}`);
    liveSources.forEach((sourceId) => {
      const textLayerId  = `text-${sourceId}`;
      const shapeLayerId = `shape-${sourceId}`;
      if (this.map.getLayer(textLayerId))  this.map.removeLayer(textLayerId);
      if (this.map.getLayer(shapeLayerId)) this.map.removeLayer(shapeLayerId);
      if (this.map.getSource(sourceId))    this.map.removeSource(sourceId);
    });

    const categories = ["train", "bus", "ferry"];
    const nowEpoch = Date.now() / 1000;
    const maxAge = Number(this.config.live_max_age_seconds || 120);
    const allTrackers = Object.entries(this.hass?.states || {})
      .filter(([id]) => id.startsWith("device_tracker."));
    console.log(`[MetlinkExplorer] _renderLiveVehicles: ${allTrackers.length} device_tracker entities; nowEpoch=${nowEpoch.toFixed(0)}, maxAge=${maxAge}s`);

    const iconSize = Number(this.config.icon_size || 33);
    const badgeDiameter = Math.max(24, Math.round(iconSize * 2));
    const fontSize = Math.max(12, Math.round(iconSize * 0.78));
    const borderWidth = Math.max(2, Math.round(iconSize * 0.12));
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    let sourceIndex = 0;

    categories.forEach((mode) => {
      const routeEntries = this.config[`${mode}_entities`] || [];
      [...routeEntries].reverse().forEach((entry) => {
        const liveTrackingEnabled = entry.live_tracking !== false;
        if (!liveTrackingEnabled) {
          console.log(`[MetlinkExplorer] ${mode} entry ${entry.entity}: live_tracking=${JSON.stringify(entry.live_tracking)} — skipping`);
          return;
        }

        const routeFeatures = this._parseRouteGeometry(entry.entity);
        const routeMeta = this._routeMetaFromFeatures(routeFeatures || []) || this._routeMetaFallback(entry);
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
        const shapeLayerId = `shape-${sourceId}`;
        const textLayerId  = `text-${sourceId}`;

        const featuresWithBadge = vehicleFeatures.map((feature) => {
          const routeLabel  = feature.properties.route_label || "";
          const markerColor = feature.properties.marker_color || VEHICLE_COLORS[mode] || "#ff9800";
          const textColor   = feature.properties.text_color || "#ffffff";
          const haloColor   = feature.properties.text_halo_color || "rgba(0,0,0,0.45)";
          const shapeId = this._badgeShapeId(markerColor, badgeDiameter, borderWidth);
          const textId  = this._badgeTextId(routeLabel, textColor, badgeDiameter, fontSize);
          this._ensureBadgeShape(shapeId, markerColor, badgeDiameter, borderWidth, dpr);
          this._ensureBadgeText(textId, routeLabel, textColor, haloColor, badgeDiameter, fontSize, dpr);

          return {
            ...feature,
            properties: {
              ...feature.properties,
              shape_badge_id: shapeId,
              text_badge_id:  textId,
            },
          };
        });

        this.map.addSource(sourceId, {
          type: "geojson",
          data: {
            type: "FeatureCollection",
            features: featuresWithBadge,
          },
        });

        // Shape layer: teardrop icon rotates with vehicle bearing.
        this.map.addLayer({
          id: shapeLayerId,
          type: "symbol",
          source: sourceId,
          layout: {
            "icon-image": ["get", "shape_badge_id"],
            "icon-anchor": "center",
            "icon-allow-overlap": true,
            "icon-ignore-placement": true,
            "icon-rotate": ["get", "bearing"],
            "icon-rotation-alignment": "map",
            "icon-pitch-alignment": "map",
          },
        });

        // Text layer: separate non-rotating layer so the label stays upright.
        this.map.addLayer({
          id: textLayerId,
          type: "symbol",
          source: sourceId,
          layout: {
            "icon-image": ["get", "text_badge_id"],
            "icon-anchor": "center",
            "icon-allow-overlap": true,
            "icon-ignore-placement": true,
            "icon-rotation-alignment": "viewport",
            "icon-pitch-alignment": "viewport",
          },
        });

        console.log(`[MetlinkExplorer] Teardrop symbol layers added for ${sourceId}, features=${featuresWithBadge.length}`);

        sourceIndex += 1;
      });
    });
  }

  _renderRoutes() {
    if (!this.map) return;
    if (!this.map.isStyleLoaded()) {
      console.log("[MetlinkExplorer] _renderRoutes skipped: style not loaded");
      return;
    }

    console.log('[MetlinkExplorer] _renderRoutes start');

    try {
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

          const weight = Math.max(1, Number(entry.weight || 6));
          const dashArray = DASH_MAP[entry.style] || [];

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
    } catch (err) {
      console.error('[MetlinkExplorer] _renderRoutes error', err);
    }
    this.map.once('idle', () => this._renderLiveVehicles());
    console.log('[MetlinkExplorer] _renderRoutes end');
  }

  updated(changedProps) {
    if (changedProps.has('config')) {
      console.log('[MetlinkExplorer] updated(config)');
    }
    if (changedProps.has('hass')) {
      console.log('[MetlinkExplorer] updated(hass)');
    }
    if (this.map) {
      if (changedProps.has('config')) {
        const oldConfig = changedProps.get('config');
        if (oldConfig?.map_style !== this.config.map_style) this._updateMapStyle();
        this._centerMap();
        this._renderRoutes();
      }
      if (changedProps.has('hass')) this._renderLiveVehicles();
    }
    this._forceSectionBreakout();
  }

  async firstUpdated() {
    console.log('[MetlinkExplorer] firstUpdated start');
    try {
      await loadMapLibre;
      console.log('[MetlinkExplorer] firstUpdated MapLibre ready');
      this._initMap();
    } catch (err) {
      console.error('[MetlinkExplorer] firstUpdated failed before _initMap', err);
    }
  }

  _initMap() {
    const container = this.shadowRoot.getElementById('map');
    if (!container || this.map) {
      console.log('[MetlinkExplorer] _initMap skipped', { hasContainer: !!container, hasMap: !!this.map });
      return;
    }

    console.log('[MetlinkExplorer] _initMap creating map');

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
      console.log('[MetlinkExplorer] map load event');
      this.map.resize();
      this._centerMap();
      this._renderRoutes();
    });

    this.map.on('error', (event) => {
      console.error('[MetlinkExplorer] map error event', event?.error || event);
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

if (!customElements.get("metlink-explorer-map-card")) {
  customElements.define("metlink-explorer-map-card", MetlinkExplorerCard);
  console.log("[MetlinkExplorer] custom element registered: metlink-explorer-map-card");
} else {
  console.log("[MetlinkExplorer] custom element already registered: metlink-explorer-map-card");
}
