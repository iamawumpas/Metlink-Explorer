import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit@2.0.0/index.js?module";

console.log("[MetlinkExplorer] map card script loaded (build 0.9.5)");

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
      cable_entities: [],
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

    // Map-pin canvas: taller than wide so the pointed tail fits below the circle.
    // Circle center sits at canvas center so icon-anchor:"center" = vehicle coordinate.
    const tailFactor = 1.5;
    const pixelW = Math.max(1, Math.round(diameter * dpr));
    const pixelH = Math.max(1, Math.round(diameter * tailFactor * dpr));
    const canvas = document.createElement("canvas");
    canvas.width = pixelW;
    canvas.height = pixelH;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return;

    ctx.scale(dpr, dpr);

    const cssH = diameter * tailFactor;
    const cx = diameter / 2;
    const cy = cssH / 2; // circle center at canvas center
    const r = Math.max(8, diameter / 2 - borderWidth);
    const tipY = cssH - borderWidth; // classic map-pin point at bottom

    ctx.beginPath();
    ctx.moveTo(cx, tipY);
    ctx.quadraticCurveTo(cx - r * 0.35, cy + r * 1.05, cx - r, cy + r * 0.15);
    ctx.bezierCurveTo(cx - r, cy - r * 0.65, cx - r * 0.45, cy - r, cx, cy - r);
    ctx.bezierCurveTo(cx + r * 0.45, cy - r, cx + r, cy - r * 0.65, cx + r, cy + r * 0.15);
    ctx.quadraticCurveTo(cx + r * 0.35, cy + r * 1.05, cx, tipY);
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
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
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

  _ensureHubMarkerImage(imageId, diameter, mode, dpr) {
    if (!this.map || this.map.hasImage(imageId)) return;

    const pixelSize = Math.max(1, Math.round(diameter * dpr));
    const canvas = document.createElement("canvas");
    canvas.width = pixelSize;
    canvas.height = pixelSize;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return;

    ctx.scale(dpr, dpr);

    const center = diameter / 2;
    const radius = Math.max(4, center - 2);
    ctx.clearRect(0, 0, diameter, diameter);

    if (mode === "bus") {
      // Bus stop markers: octagon fallback if bus-stop.png cannot load.
      const sides = 8;
      const octRadius = Math.max(4, radius);
      ctx.beginPath();
      for (let i = 0; i < sides; i++) {
        const angle = (Math.PI / sides) + (i * (Math.PI * 2 / sides));
        const x = center + Math.cos(angle) * octRadius;
        const y = center + Math.sin(angle) * octRadius;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.fillStyle = "#000000";
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#ffffff";
      ctx.stroke();
    } else if (mode === "train") {
      // Train hubs: square badge with simple train glyph.
      const inset = Math.max(2, Math.round(diameter * 0.1));
      const size = diameter - (inset * 2);
      ctx.fillStyle = "#f2d318";
      ctx.fillRect(inset, inset, size, size);
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#111111";
      ctx.strokeRect(inset, inset, size, size);

      const glyphY = center + (diameter * 0.05);
      ctx.fillStyle = "#111111";
      ctx.fillRect(center - (diameter * 0.2), glyphY - (diameter * 0.12), diameter * 0.4, diameter * 0.18);
      ctx.fillRect(center - (diameter * 0.14), glyphY - (diameter * 0.2), diameter * 0.18, diameter * 0.08);
      ctx.beginPath();
      ctx.arc(center - (diameter * 0.11), glyphY + (diameter * 0.1), diameter * 0.05, 0, Math.PI * 2);
      ctx.arc(center + (diameter * 0.11), glyphY + (diameter * 0.1), diameter * 0.05, 0, Math.PI * 2);
      ctx.fill();
    } else if (mode === "ferry") {
      // Ferry stops: equilateral triangle.
      const triRadius = Math.max(4, radius);
      ctx.beginPath();
      for (let i = 0; i < 3; i++) {
        const angle = (-Math.PI / 2) + (i * (Math.PI * 2 / 3));
        const x = center + Math.cos(angle) * triRadius;
        const y = center + Math.sin(angle) * triRadius;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.fillStyle = "#000000";
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#ffffff";
      ctx.stroke();
    } else if (mode === "cable") {
      // Cable car stops: hexagon.
      const sides = 6;
      const hexRadius = Math.max(4, radius);
      ctx.beginPath();
      for (let i = 0; i < sides; i++) {
        const angle = (Math.PI / 6) + (i * (Math.PI * 2 / sides));
        const x = center + Math.cos(angle) * hexRadius;
        const y = center + Math.sin(angle) * hexRadius;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.fillStyle = "#000000";
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#ffffff";
      ctx.stroke();
    } else {
      // Default: square stop badge.
      const inset = Math.max(2, Math.round(diameter * 0.1));
      const size = diameter - (inset * 2);
      ctx.fillStyle = "#000000";
      ctx.fillRect(inset, inset, size, size);
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#ffffff";
      ctx.strokeRect(inset, inset, size, size);
    }

    const imageData = ctx.getImageData(0, 0, pixelSize, pixelSize);
    this.map.addImage(imageId, imageData, { pixelRatio: dpr });
  }

  async _ensureBusHubImage(imageId, diameter, dpr) {
    if (!this.map || this.map.hasImage(imageId)) return;

    const pixelSize = Math.max(1, Math.round(diameter * dpr));
    let rawImg;
    try {
      const result = await this.map.loadImage('/metlink_explorer_frontend/bus-stop.png');
      rawImg = result.data;
    } catch (e) {
      console.warn('[MetlinkExplorer] Failed to load bus-stop.png, falling back to canvas badge', e);
      this._ensureHubMarkerImage(imageId, diameter, 'bus', dpr);
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = pixelSize;
    canvas.height = pixelSize;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return;

    ctx.scale(dpr, dpr);
    const center = diameter / 2;
    const radius = Math.max(4, center - 2);

    // Black octagon background.
    const sides = 8;
    const octRadius = Math.max(4, radius);
    ctx.beginPath();
    for (let i = 0; i < sides; i++) {
      const angle = (Math.PI / sides) + (i * (Math.PI * 2 / sides));
      const x = center + Math.cos(angle) * octRadius;
      const y = center + Math.sin(angle) * octRadius;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fillStyle = '#000000';
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#ffffff';
    ctx.stroke();

    // Bus icon overlay.
    const iconSize = diameter * 0.56;
    const iconX = center - (iconSize / 2);
    const iconY = center - (iconSize / 2);
    ctx.drawImage(rawImg, iconX, iconY, iconSize, iconSize);

    const imageData = ctx.getImageData(0, 0, pixelSize, pixelSize);
    if (this.map.hasImage(imageId)) return;
    this.map.addImage(imageId, imageData, { pixelRatio: dpr });
  }

  async _ensureTrainHubImage(imageId, diameter, dpr) {
    if (!this.map || this.map.hasImage(imageId)) return;

    const pixelSize = Math.max(1, Math.round(diameter * dpr));
    let rawImg;
    try {
      const result = await this.map.loadImage('/metlink_explorer_frontend/train.png');
      rawImg = result.data;
    } catch (e) {
      console.warn('[MetlinkExplorer] Failed to load train.png, falling back to canvas badge', e);
      this._ensureHubMarkerImage(imageId, diameter, 'train', dpr);
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = pixelSize;
    canvas.height = pixelSize;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return;

    // Draw the image as-is; rotation is applied via MapLibre icon-rotate on the layer.
    ctx.drawImage(rawImg, 0, 0, pixelSize, pixelSize);

    // Strip white/near-white background pixels.
    const imgData = ctx.getImageData(0, 0, pixelSize, pixelSize);
    const d = imgData.data;
    for (let i = 0; i < d.length; i += 4) {
      if (d[i] > 230 && d[i + 1] > 230 && d[i + 2] > 230) {
        d[i + 3] = 0;
      }
    }
    ctx.putImageData(imgData, 0, 0);

    const finalData = ctx.getImageData(0, 0, pixelSize, pixelSize);
    if (this.map.hasImage(imageId)) return; // Guard against double-add during await.
    this.map.addImage(imageId, finalData, { pixelRatio: dpr });
  }

  _computeHubCollisionOffsets(hubs, separationMeters = 24) {
    const grouped = new Map();
    const precision = 1e-5;

    for (const hub of hubs || []) {
      const lat = Number(hub.stop_lat);
      const lon = Number(hub.stop_lon);
      const stopId = String(hub.stop_id || "");
      if (!stopId || !Number.isFinite(lat) || !Number.isFinite(lon)) continue;
      const key = `${Math.round(lat / precision) * precision},${Math.round(lon / precision) * precision}`;
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push({ ...hub, stop_id: stopId });
    }

    const offsets = {};
    for (const group of grouped.values()) {
      if (group.length === 1) {
        offsets[group[0].stop_id] = { dLon: 0, dLat: 0 };
        continue;
      }

      const latRef = Number(group[0].stop_lat);
      const latRad = (Number.isFinite(latRef) ? latRef : 0) * (Math.PI / 180);
      const metersPerDegLat = 111320;
      const metersPerDegLon = Math.max(1, 111320 * Math.cos(latRad));
      const radiusMeters = Math.max(12, Number(separationMeters));
      for (let i = 0; i < group.length; i++) {
        const angle = (i / group.length) * Math.PI * 2;
        const dLon = (Math.cos(angle) * radiusMeters) / metersPerDegLon;
        const dLat = (Math.sin(angle) * radiusMeters) / metersPerDegLat;
        offsets[group[i].stop_id] = {
          dLon,
          dLat,
        };
      }
    }

    return offsets;
  }

  _hubCoordKey(lon, lat, precision = 1e-5) {
    const safeLon = Number(lon);
    const safeLat = Number(lat);
    if (!Number.isFinite(safeLon) || !Number.isFinite(safeLat)) return "";
    const lonKey = Math.round(safeLon / precision) * precision;
    const latKey = Math.round(safeLat / precision) * precision;
    return `${latKey},${lonKey}`;
  }

  _sharedHubSideOffset(lat, mode) {
    if (mode !== "train" && mode !== "bus") return { dLon: 0, dLat: 0 };
    const latRad = (Number.isFinite(Number(lat)) ? Number(lat) : 0) * (Math.PI / 180);
    const metersPerDegLon = Math.max(1, 111320 * Math.cos(latRad));
    const sideMeters = 18;
    const dir = mode === "train" ? -1 : 1;
    return {
      dLon: (dir * sideMeters) / metersPerDegLon,
      dLat: 0,
    };
  }

  _bringHubLayersToFront() {
    if (!this.map) return;
    for (let i = 0; i < 200; i++) {
      const layerId = `hub-layer-route-source-${i}`;
      if (!this.map.getLayer(layerId)) continue;
      try {
        this.map.moveLayer(layerId);
      } catch (_) {
        // Best effort: if layer ordering changes mid-render, next refresh will retry.
      }
    }
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
    const match = objectId.match(/^(?:train|bus|ferry|cable|school_bus)_(.+?)_(?:route_)?geometry$/i);
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

  _stripTrailingZerosNumeric(value) {
    const text = String(value || "").trim();
    if (!/^\d+$/.test(text)) return text;
    const stripped = text.replace(/0+$/g, "");
    return stripped || text;
  }

  _expandRouteKeyVariants(value) {
    const variants = new Set();
    const raw = this._normalizeKey(value);
    if (!raw) return variants;

    variants.add(raw);

    const compact = raw.replace(/[^a-z0-9]/g, "");
    if (compact) variants.add(compact);

    const digits = compact.replace(/[^0-9]/g, "");
    if (digits) {
      variants.add(digits);
      variants.add(this._stripTrailingZerosNumeric(digits));
      variants.add(String(Number(digits)));
    }

    return new Set([...variants].filter(Boolean));
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
    this._expandRouteKeyVariants(routeMeta.routeId).forEach((k) => keys.add(k));
    this._expandRouteKeyVariants(routeMeta.routeLabel).forEach((k) => keys.add(k));
    return keys;
  }

  _vehicleRouteKeys(state) {
    const attrs = state?.attributes || {};
    const keys = new Set();
    const fromTrip = this._tripRouteKey(attrs.trip_id);
    this._expandRouteKeyVariants(fromTrip).forEach((k) => keys.add(k));
    const routeId = attrs.route_id ? String(attrs.route_id).trim() : "";
    this._expandRouteKeyVariants(routeId).forEach((k) => keys.add(k));
    return keys;
  }

  _backendLiveTrackingFromFeatures(routeFeatures) {
    if (!Array.isArray(routeFeatures) || routeFeatures.length === 0) return null;
    const first = routeFeatures[0];
    const featureValue = first?.properties?.live_tracking;
    if (typeof featureValue === "boolean") return featureValue;
    return null;
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
        // The pin artwork points down at 0deg, so rotate by +180deg to align tip with travel bearing.
        const iconBearing = (bearing + 180) % 360;
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
            bearing: iconBearing,
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
        const routeFeatures = this._parseRouteGeometry(entry.entity);
        const backendLiveTracking = this._backendLiveTrackingFromFeatures(routeFeatures);
        const cardLiveTracking = typeof entry.live_tracking === "boolean" ? entry.live_tracking : null;
        const liveTrackingEnabled =
          cardLiveTracking !== null
            ? cardLiveTracking
            : (typeof backendLiveTracking === "boolean" ? backendLiveTracking : true);
        if (!liveTrackingEnabled) {
          console.log(
            `[MetlinkExplorer] ${mode} entry ${entry.entity}: card_live_tracking=${JSON.stringify(cardLiveTracking)}, backend_live_tracking=${JSON.stringify(backendLiveTracking)} -> skipping`
          );
          return;
        }

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

    // Hub layers are rendered by _renderRoutes; ensure they stay above vehicle badges.
    this._bringHubLayersToFront();
  }

  async _renderRoutes() {
    if (!this.map) return;
    if (!this.map.isStyleLoaded()) {
      console.log("[MetlinkExplorer] _renderRoutes skipped: style not loaded");
      return;
    }

    console.log('[MetlinkExplorer] _renderRoutes start');

    try {
      const categories = ['ferry', 'bus', 'cable', 'train'];
      const hubCoordModes = new Map();

      // First pass: collect shared selected-stop coordinates across all route entries.
      categories.forEach((cat) => {
        const entries = this.config[`${cat}_entities`] || [];
        [...entries].reverse().forEach((entry) => {
          const selectedStopIds = new Set((entry.selected_stops || []).map((id) => String(id)));
          if (selectedStopIds.size === 0) return;
          const features = this._parseRouteGeometry(entry.entity);
          if (!features) return;

          for (const feature of features) {
            const timelineStops = feature?.properties?.timeline_stops || {};
            for (const directionStops of Object.values(timelineStops)) {
              if (!Array.isArray(directionStops)) continue;
              for (const stop of directionStops) {
                const stopId = String(stop?.stop_id || '');
                const lon = Number(stop?.stop_lon);
                const lat = Number(stop?.stop_lat);
                if (!selectedStopIds.has(stopId) || !Number.isFinite(lon) || !Number.isFinite(lat)) continue;

                const key = this._hubCoordKey(lon, lat);
                if (!key) continue;
                if (!hubCoordModes.has(key)) hubCoordModes.set(key, new Set());
                hubCoordModes.get(key).add(cat);
              }
            }
          }
        });
      });
      
      // Clear existing
      const currentSources = Array.from({length: 100}, (_, i) => `route-source-${i}`);
      currentSources.forEach(s => {
        if (this.map.getLayer(`hub-layer-${s}`)) this.map.removeLayer(`hub-layer-${s}`);
        if (this.map.getLayer(`layer-${s}`)) this.map.removeLayer(`layer-${s}`);
        if (this.map.getSource(`hub-source-${s}`)) this.map.removeSource(`hub-source-${s}`);
        if (this.map.getSource(s)) this.map.removeSource(s);
      });

      let layerIdx = 0;
      const topHubLayerIds = [];
      for (const cat of categories) {
        const entries = this.config[`${cat}_entities`] || [];
        for (const entry of [...entries].reverse()) {
          const features = this._parseRouteGeometry(entry.entity);
          if (!features) continue;

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

          const selectedStopIds = new Set((entry.selected_stops || []).map((id) => String(id)));
          if (selectedStopIds.size > 0) {
            const selectedStops = [];
            for (const feature of features) {
              const props = feature?.properties || {};
              const timelineStops = props.timeline_stops || {};
              for (const directionStops of Object.values(timelineStops)) {
                if (!Array.isArray(directionStops)) continue;
                for (const stop of directionStops) {
                  const stopId = String(stop?.stop_id || '');
                  if (selectedStopIds.has(stopId) && Number.isFinite(Number(stop.stop_lat)) && Number.isFinite(Number(stop.stop_lon))) {
                    selectedStops.push(stop);
                  }
                }
              }
            }

            if (selectedStops.length > 0) {
              const hubDiameter = Math.max(16, Math.round(33 * 0.78));
              const markerDiameter = (cat === 'train' || cat === 'bus') ? Math.max(32, Math.round(hubDiameter * 2)) : hubDiameter;
              const uniqueStops = new Map();
              selectedStops.forEach((stop) => {
                const key = `${String(stop.stop_id || "")}:${Number(stop.stop_lat)}:${Number(stop.stop_lon)}`;
                if (!uniqueStops.has(key)) uniqueStops.set(key, stop);
              });
              const dedupedStops = [...uniqueStops.values()];
              const offsets = this._computeHubCollisionOffsets(dedupedStops, 24);
              const hubFeatures = dedupedStops.map((stop) => {
                const stopId = String(stop.stop_id || '');
                const offset = offsets[stopId] || { dLon: 0, dLat: 0 };
                const baseLon = Number(stop.stop_lon);
                const baseLat = Number(stop.stop_lat);
                const coordKey = this._hubCoordKey(baseLon, baseLat);
                const sharedModes = hubCoordModes.get(coordKey);
                const hasTrainBusShare = sharedModes?.has('train') && sharedModes?.has('bus');
                const sharedOffset = hasTrainBusShare ? this._sharedHubSideOffset(baseLat, cat) : { dLon: 0, dLat: 0 };
                return {
                  type: 'Feature',
                  geometry: {
                    type: 'Point',
                    coordinates: [baseLon + offset.dLon + sharedOffset.dLon, baseLat + offset.dLat + sharedOffset.dLat],
                  },
                  properties: {
                    stop_id: stopId,
                    stop_name: String(stop.stop_name || 'Hub'),
                    mode: cat,
                  },
                };
              });

              const hubSourceId = `hub-source-${sourceId}`;
              if (!this.map.getSource(hubSourceId)) {
                this.map.addSource(hubSourceId, {
                  type: 'geojson',
                  data: { type: 'FeatureCollection', features: hubFeatures },
                });
              } else {
                this.map.getSource(hubSourceId).setData({ type: 'FeatureCollection', features: hubFeatures });
              }

              const hubImageId = `hub-marker-${cat}-${markerDiameter}`;
              if (cat === 'train') {
                await this._ensureTrainHubImage(hubImageId, markerDiameter, Math.max(1, window.devicePixelRatio || 1));
              } else if (cat === 'bus') {
                await this._ensureBusHubImage(hubImageId, markerDiameter, Math.max(1, window.devicePixelRatio || 1));
              } else {
                this._ensureHubMarkerImage(hubImageId, markerDiameter, cat, Math.max(1, window.devicePixelRatio || 1));
              }

              const hubLayerId = `hub-layer-${sourceId}`;
              if (this.map.getLayer(hubLayerId)) this.map.removeLayer(hubLayerId);
              this.map.addLayer({
                id: hubLayerId,
                type: 'symbol',
                source: hubSourceId,
                layout: {
                  'icon-image': hubImageId,
                  'icon-anchor': 'center',
                  'icon-allow-overlap': true,
                  'icon-ignore-placement': true,
                  ...(cat === 'train' ? { 'icon-rotate': 0, 'icon-rotation-alignment': 'viewport' } : {}),
                },
              });
              if (cat === 'train' || cat === 'bus') {
                topHubLayerIds.push(hubLayerId);
              }
            } else {
              console.log(`[MetlinkExplorer] No selected stops found for ${entry.entity} (${cat})`);
            }
          }

          layerIdx++;
        }
      }

      // Keep train and bus hub badges at the very top, above vehicle icons.
      topHubLayerIds.forEach((layerId) => {
        if (this.map.getLayer(layerId)) {
          try {
            this.map.moveLayer(layerId);
          } catch (_) {
            // Best effort.
          }
        }
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
