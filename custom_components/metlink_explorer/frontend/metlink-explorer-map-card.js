import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit@2.0.0/index.js?module";

console.log("[MetlinkExplorer] map card script loaded (build 0.12.23)");

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

// Intentionally slow raster tile visual load/fade.
const TILE_FADE_DURATION_MS = 250000;
const STARTUP_REDRAW_INTERVAL_MS = 10000;
const STARTUP_STABLE_TICKS_REQUIRED = 2;

class MetlinkExplorerCard extends LitElement {
  static get properties() {
    return { hass: {}, config: {} };
  }

  constructor() {
    super();
    this._liveGpsSnapshot = "";
    this._liveSlotHashes = new Map();
    this._vehicleLastPositions = new Map();
    this._activeVehicleSources = new Set();
    this._pendingLiveRender = false;
    this._hubLayerIds = new Set();
    this._boardPayloadCache = new Map();
    this._departureBubble = null;
    this._bubbleAutoCloseTimer = null;
    this._bubbleOpenSequence = 0;
    this._boundMapClick = (event) => this._onMapClick(event);
    this._boundMapMove = () => this._updateDepartureBubbleAnchor();
    this._boundStopLayoutChange = () => this._scheduleStopBadgeOverlapLayout();
    this._boundDocumentPointerDown = (event) => this._onDocumentPointerDown(event);
    // Layer visibility toggles: type -> mode -> boolean
    this._layerVisibility = {
      routes: { train: true, bus: true, ferry: true, cable: true },
      live:   { train: true, bus: true, ferry: true, cable: true },
      stops:  { train: true, bus: true, ferry: true, cable: true },
    };
    // Maps from mode -> Set of MapLibre layer IDs for that mode+type combo
    this._routeLayersByMode = new Map();
    this._stopLayersByMode  = new Map();
    this._liveLayersByMode  = new Map();
    this._layerPanelOpen    = false;
    this._layerResetTimer   = null;
    this._isEditorPreview   = false;
    this._appliedHostHeight = "";
    this._startupRedrawTimer = null;
    this._startupStableTicks = 0;
    this._startupSettled = false;
    this._stopBadgeLayoutSources = new Map();
    this._stopLayoutDebounceTimer = null;
  }

  connectedCallback() {
    super.connectedCallback();
    window.addEventListener('pointerdown', this._boundDocumentPointerDown, true);
  }

  static async getConfigElement() {
    try {
      await import("/metlink_explorer_frontend/metlink-explorer-editor.js");
    } catch (e) { console.error("Failed to load editor:", e); }
    return document.createElement("metlink-explorer-map-editor");
  }

  static getStubConfig() {
    return { center_map: "zone.home", zoom: 12, map_style: "voyager", icon_size: 25, map_projection: "normal" };
  }

  _clampIconSize(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return 25;
    return Math.max(19, Math.min(31, n));
  }

  _cloneLayerVisibilityState(state) {
    return {
      routes: { ...(state?.routes || {}) },
      live: { ...(state?.live || {}) },
      stops: { ...(state?.stops || {}) },
    };
  }

  _layerVisibilityFromConfig(cfg) {
    const defaults = {
      routes: { train: true, bus: true, ferry: true, cable: true },
      live:   { train: true, bus: true, ferry: true, cable: true },
      stops:  { train: true, bus: true, ferry: true, cable: true },
    };
    const modes = ['train', 'bus', 'ferry', 'cable'];
    modes.forEach((mode) => {
      const entries = cfg?.[`${mode}_entities`] || [];
      if (entries.length === 0) return;
      // Live defaults follow YAML route settings: if every route for a mode has
      // live_tracking explicitly false, default the mode toggle to off.
      defaults.live[mode] = entries.some((entry) => entry?.live_tracking !== false);
    });
    return defaults;
  }

  _applyAllLayerVisibility() {
    const modes = ['train', 'bus', 'ferry', 'cable'];
    const types = ['routes', 'live', 'stops'];
    types.forEach((type) => {
      modes.forEach((mode) => this._applyLayerVisibility(type, mode));
    });
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
      icon_size: 25,
      map_projection: "normal",
      ...config,
    };
    this.config.icon_size = this._clampIconSize(this.config.icon_size);

    this._layerDefaultVisibility = this._layerVisibilityFromConfig(this.config);
    this._layerVisibility = this._cloneLayerVisibilityState(this._layerDefaultVisibility);
    if (this._layerResetTimer) {
      clearTimeout(this._layerResetTimer);
      this._layerResetTimer = null;
    }
    this._applyAllLayerVisibility();
  }

  _isIsometricProjection() {
    return String(this.config?.map_projection || "normal") === "isometric";
  }

  _applyMapProjection(animate = true) {
    if (!this.map) return;
    const isometric = this._isIsometricProjection();
    const targetPitch = isometric ? 55 : 0;
    const targetBearing = isometric ? -20 : 0;
    if (animate) {
      this.map.easeTo({
        pitch: targetPitch,
        bearing: targetBearing,
        duration: 450,
      });
      return;
    }
    this.map.jumpTo({ pitch: targetPitch, bearing: targetBearing });
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

  _ferryLiveShapeId(diameter, borderWidth, directionVariant) {
    const dir = String(directionVariant || "east").toLowerCase();
    return `metlink-ferry-live-${dir}-${diameter}-${borderWidth}`;
  }

  _ferryDirectionVariant(bearing) {
    const deg = Number.isFinite(Number(bearing)) ? Number(bearing) : 90;
    const rad = (deg * Math.PI) / 180;
    // EAST uses default icon, WEST uses flipped icon.
    return Math.sin(rad) >= 0 ? "east" : "west";
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

  async _ensureFerryLiveBadge(imageId, diameter, borderWidth, dpr, flipHorizontal = false) {
    if (!this.map || this.map.hasImage(imageId)) return;

    const pixelSize = Math.max(1, Math.round(diameter * dpr));
    let rawImg;
    try {
      const result = await this.map.loadImage('/metlink_explorer_frontend/ferry-stop.png');
      rawImg = result.data;
    } catch (e) {
      console.warn('[MetlinkExplorer] Failed to load ferry-stop.png for live badge, fallback to default shape', e);
      this._ensureBadgeShape(imageId, '#ffffff', diameter, borderWidth, dpr);
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = pixelSize;
    canvas.height = pixelSize;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    const center = diameter / 2;
    const radius = Math.max(6, center - borderWidth - 0.5);

    // Circular badge with no pointer.
    ctx.beginPath();
    ctx.arc(center, center, radius, 0, Math.PI * 2);
    ctx.closePath();
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    ctx.lineWidth = borderWidth;
    ctx.strokeStyle = '#111111';
    ctx.stroke();

    // Build a transparent ferry icon source by stripping cyan background.
    const sourceCanvas = document.createElement('canvas');
    sourceCanvas.width = rawImg.width;
    sourceCanvas.height = rawImg.height;
    const sourceCtx = sourceCanvas.getContext('2d', { willReadFrequently: true });
    if (!sourceCtx) return;
    sourceCtx.drawImage(rawImg, 0, 0);

    const sourceData = sourceCtx.getImageData(0, 0, sourceCanvas.width, sourceCanvas.height);
    const sourcePixels = sourceData.data;
    let minX = sourceCanvas.width;
    let minY = sourceCanvas.height;
    let maxX = -1;
    let maxY = -1;

    for (let i = 0; i < sourcePixels.length; i += 4) {
      const r = sourcePixels[i];
      const g = sourcePixels[i + 1];
      const b = sourcePixels[i + 2];
      // Remove cyan background.
      if (b > 180 && g > 120 && r < 80) {
        sourcePixels[i + 3] = 0;
      }
      if (sourcePixels[i + 3] === 0) continue;
      const pixelIndex = i / 4;
      const x = pixelIndex % sourceCanvas.width;
      const y = Math.floor(pixelIndex / sourceCanvas.width);
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
    sourceCtx.putImageData(sourceData, 0, 0);

    const hasBounds = maxX >= minX && maxY >= minY;
    const cropX = hasBounds ? minX : 0;
    const cropY = hasBounds ? minY : 0;
    const cropWidth = hasBounds ? (maxX - minX + 1) : sourceCanvas.width;
    const cropHeight = hasBounds ? (maxY - minY + 1) : sourceCanvas.height;

    const iconSize = diameter * 0.64;
    const iconHalf = iconSize / 2;

    ctx.save();
    ctx.beginPath();
    ctx.arc(center, center, Math.max(4, radius - borderWidth), 0, Math.PI * 2);
    ctx.clip();
    ctx.translate(center, center);
    if (flipHorizontal) ctx.scale(-1, 1);
    ctx.drawImage(sourceCanvas, cropX, cropY, cropWidth, cropHeight, -iconHalf, -iconHalf, iconSize, iconSize);
    ctx.restore();

    const imageData = ctx.getImageData(0, 0, pixelSize, pixelSize);
    if (this.map.hasImage(imageId)) return;
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

  async _ensureFerryHubImage(imageId, diameter, dpr) {
    if (!this.map || this.map.hasImage(imageId)) return;

    const pixelSize = Math.max(1, Math.round(diameter * dpr));
    let rawImg;
    try {
      const result = await this.map.loadImage('/metlink_explorer_frontend/ferry-stop.png');
      rawImg = result.data;
    } catch (e) {
      console.warn('[MetlinkExplorer] Failed to load ferry-stop.png, falling back to canvas badge', e);
      this._ensureHubMarkerImage(imageId, diameter, 'ferry', dpr);
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

    // Cyan square background.
    const squareHalf = Math.max(4, radius);
    const sqX = center - squareHalf;
    const sqY = center - squareHalf;
    const sqSize = squareHalf * 2;
    ctx.fillStyle = '#12cfe3';
    ctx.fillRect(sqX, sqY, sqSize, sqSize);
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#ffffff';
    ctx.strokeRect(sqX, sqY, sqSize, sqSize);

    // Strip the solid cyan background, crop to the visible ferry silhouette,
    // then zoom the icon by 25% while keeping it clipped inside the triangle.
    const sourceCanvas = document.createElement('canvas');
    sourceCanvas.width = rawImg.width;
    sourceCanvas.height = rawImg.height;
    const sourceCtx = sourceCanvas.getContext('2d', { willReadFrequently: true });
    if (!sourceCtx) return;
    sourceCtx.drawImage(rawImg, 0, 0);

    const sourceData = sourceCtx.getImageData(0, 0, sourceCanvas.width, sourceCanvas.height);
    const sourcePixels = sourceData.data;
    let minX = sourceCanvas.width;
    let minY = sourceCanvas.height;
    let maxX = -1;
    let maxY = -1;
    for (let i = 0; i < sourcePixels.length; i += 4) {
      const r = sourcePixels[i];
      const g = sourcePixels[i + 1];
      const b = sourcePixels[i + 2];

      // Convert the flat cyan background to transparency.
      if (b > 180 && g > 120 && r < 80) {
        sourcePixels[i + 3] = 0;
      }

      if (sourcePixels[i + 3] === 0) continue;
      const pixelIndex = i / 4;
      const x = pixelIndex % sourceCanvas.width;
      const y = Math.floor(pixelIndex / sourceCanvas.width);
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
    sourceCtx.putImageData(sourceData, 0, 0);

    const hasBounds = maxX >= minX && maxY >= minY;
    const cropX = hasBounds ? Math.max(0, minX - Math.round(sourceCanvas.width * 0.02)) : 0;
    const cropY = hasBounds ? Math.max(0, minY - Math.round(sourceCanvas.height * 0.02)) : 0;
    const cropWidth = hasBounds
      ? Math.min(sourceCanvas.width - cropX, (maxX - minX + 1) + Math.round(sourceCanvas.width * 0.04))
      : sourceCanvas.width;
    const cropHeight = hasBounds
      ? Math.min(sourceCanvas.height - cropY, (maxY - minY + 1) + Math.round(sourceCanvas.height * 0.04))
      : sourceCanvas.height;

    const iconSize = diameter * 0.56;
    const iconX = center - (iconSize / 2);
    const iconY = center - (iconSize / 2) - (diameter * 0.01);

    ctx.save();
    ctx.beginPath();
    const clipInset = 3;
    ctx.rect(center - squareHalf + clipInset, center - squareHalf + clipInset, sqSize - clipInset * 2, sqSize - clipInset * 2);
    ctx.closePath();
    ctx.clip();
    ctx.drawImage(sourceCanvas, cropX, cropY, cropWidth, cropHeight, iconX, iconY, iconSize, iconSize);
    ctx.restore();

    const imageData = ctx.getImageData(0, 0, pixelSize, pixelSize);
    if (this.map.hasImage(imageId)) return;
    this.map.addImage(imageId, imageData, { pixelRatio: dpr });
  }

  async _ensureTrainHubImage(imageId, diameter, dpr) {
    if (!this.map || this.map.hasImage(imageId)) return;

    const pixelSize = Math.max(1, Math.round(diameter * dpr));
    let rawImg;
    try {
      const result = await this.map.loadImage('/metlink_explorer_frontend/train-stop.png');
      rawImg = result.data;
    } catch (e) {
      console.warn('[MetlinkExplorer] Failed to load train-stop.png, falling back to canvas badge', e);
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

  _modeBucket(mode) {
    const raw = String(mode || "").trim().toLowerCase();
    if (!raw) return "";
    if (raw === "school_bus" || raw === "schoolbus" || raw === "school-bus" || raw === "school bus") return "bus";
    if (raw === "bus") return "bus";
    if (raw === "train" || raw === "ferry" || raw === "cable") return raw;
    return raw;
  }

  _haversineMeters(lat1, lon1, lat2, lon2) {
    const r = 6371000;
    const toRad = Math.PI / 180;
    const dLat = (lat2 - lat1) * toRad;
    const dLon = (lon2 - lon1) * toRad;
    const a = (Math.sin(dLat / 2) ** 2)
      + Math.cos(lat1 * toRad) * Math.cos(lat2 * toRad) * (Math.sin(dLon / 2) ** 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return r * c;
  }

  _bearingBetweenPoints(lat1, lon1, lat2, lon2) {
    const toRad = Math.PI / 180;
    const toDeg = 180 / Math.PI;
    const phi1 = lat1 * toRad;
    const phi2 = lat2 * toRad;
    const lambda = (lon2 - lon1) * toRad;
    const y = Math.sin(lambda) * Math.cos(phi2);
    const x = Math.cos(phi1) * Math.sin(phi2)
      - Math.sin(phi1) * Math.cos(phi2) * Math.cos(lambda);
    const theta = Math.atan2(y, x) * toDeg;
    return (theta + 360) % 360;
  }

  _angularDifferenceDegrees(a, b) {
    if (!Number.isFinite(a) || !Number.isFinite(b)) return 0;
    const diff = Math.abs(a - b) % 360;
    return diff > 180 ? (360 - diff) : diff;
  }

  _routeTokenForFeature(feature) {
    const props = feature?.properties || {};
    const routeShort = String(props.route_short_name || "").trim();
    const routeId = String(props.route_id || "").trim();
    const serviceLabel = String(props.service_label || "").trim();
    return (routeShort || routeId || serviceLabel || "").toUpperCase();
  }

  _buildSelectedStopContextIndex(configCategory, entry, features, indexByMode) {
    const modeBucket = this._modeBucket(configCategory);
    if (!modeBucket) return;

    const selectedStopIds = new Set((entry?.selected_stops || []).map((id) => String(id)));
    if (selectedStopIds.size === 0) return;
    if (!Array.isArray(features) || features.length === 0) return;

    if (!indexByMode.has(modeBucket)) indexByMode.set(modeBucket, new Map());
    const modeMap = indexByMode.get(modeBucket);

    const upsertContext = (stop, routeToken, directionToken, bearingValue) => {
      const rawStopId = String(stop?.stop_id || "").trim();
      const lon = Number(stop?.stop_lon);
      const lat = Number(stop?.stop_lat);
      if (!selectedStopIds.has(rawStopId) || !Number.isFinite(lat) || !Number.isFinite(lon)) return;

      const normalizedStopId = modeBucket === "train"
        ? (this._normalizeTrainStationStopId(rawStopId) || rawStopId)
        : rawStopId;
      const key = modeBucket === "train"
        ? normalizedStopId.toUpperCase()
        : `${normalizedStopId.toUpperCase()}:${lat.toFixed(6)}:${lon.toFixed(6)}`;

      if (!modeMap.has(key)) {
        modeMap.set(key, {
          stopId: normalizedStopId,
          stopName: String(stop?.stop_name || `Stop ${normalizedStopId}`),
          lat,
          lon,
          routeSignatures: [],
        });
      }

      const ctx = modeMap.get(key);
      const signature = {
        routeToken: String(routeToken || "").trim().toUpperCase(),
        directionToken: String(directionToken || "").trim().toUpperCase(),
        bearing: Number.isFinite(bearingValue) ? Number(bearingValue) : null,
      };

      if (!signature.routeToken) return;
      const dedupeSignatureKey = `${signature.routeToken}|${signature.directionToken}|${signature.bearing === null ? "" : signature.bearing.toFixed(1)}`;
      if (!ctx._sigKeys) ctx._sigKeys = new Set();
      if (ctx._sigKeys.has(dedupeSignatureKey)) return;
      ctx._sigKeys.add(dedupeSignatureKey);
      ctx.routeSignatures.push(signature);
    };

    for (const feature of features) {
      const routeToken = this._routeTokenForFeature(feature);
      if (!routeToken) continue;
      const timelineStops = feature?.properties?.timeline_stops || {};
      for (const [directionToken, directionStops] of Object.entries(timelineStops)) {
        if (!Array.isArray(directionStops)) continue;
        for (let idx = 0; idx < directionStops.length; idx++) {
          const stop = directionStops[idx];
          const prev = idx > 0 ? directionStops[idx - 1] : null;
          const next = idx < (directionStops.length - 1) ? directionStops[idx + 1] : null;

          let bearing = null;
          const stopLat = Number(stop?.stop_lat);
          const stopLon = Number(stop?.stop_lon);
          if (Number.isFinite(stopLat) && Number.isFinite(stopLon)) {
            const prevLat = Number(prev?.stop_lat);
            const prevLon = Number(prev?.stop_lon);
            const nextLat = Number(next?.stop_lat);
            const nextLon = Number(next?.stop_lon);
            if (Number.isFinite(prevLat) && Number.isFinite(prevLon)) {
              bearing = this._bearingBetweenPoints(prevLat, prevLon, stopLat, stopLon);
            }
            if (!Number.isFinite(bearing) && Number.isFinite(nextLat) && Number.isFinite(nextLon)) {
              bearing = this._bearingBetweenPoints(stopLat, stopLon, nextLat, nextLon);
            }
          }

          upsertContext(stop, routeToken, directionToken, bearing);
        }
      }
    }
  }

  _stopsAreInfluenceCompatible(anchorCtx, candidateCtx) {
    if (!anchorCtx || !candidateCtx) return false;
    const distanceMeters = this._haversineMeters(anchorCtx.lat, anchorCtx.lon, candidateCtx.lat, candidateCtx.lon);
    if (!Number.isFinite(distanceMeters) || distanceMeters > 75) return false;

    const anchorRoutes = new Set((anchorCtx.routeSignatures || []).map((sig) => sig.routeToken).filter(Boolean));
    const candidateRoutes = new Set((candidateCtx.routeSignatures || []).map((sig) => sig.routeToken).filter(Boolean));
    const sharedRoutes = [...anchorRoutes].filter((routeToken) => candidateRoutes.has(routeToken));
    if (sharedRoutes.length === 0) return false;

    for (const routeToken of sharedRoutes) {
      const aSigs = (anchorCtx.routeSignatures || []).filter((sig) => sig.routeToken === routeToken);
      const bSigs = (candidateCtx.routeSignatures || []).filter((sig) => sig.routeToken === routeToken);
      let minBearingDiff = null;
      for (const aSig of aSigs) {
        for (const bSig of bSigs) {
          if (!Number.isFinite(aSig?.bearing) || !Number.isFinite(bSig?.bearing)) continue;
          const diff = this._angularDifferenceDegrees(aSig.bearing, bSig.bearing);
          if (minBearingDiff === null || diff < minBearingDiff) minBearingDiff = diff;
        }
      }
      if (Number.isFinite(minBearingDiff) && minBearingDiff > 25 && distanceMeters > 100) {
        return false;
      }
    }

    return true;
  }

  _influenceStopIdsForContext(anchorCtx, modeIndex) {
    if (!anchorCtx || !modeIndex) return [String(anchorCtx?.stopId || "")].filter(Boolean);

    const stopIds = new Set([String(anchorCtx.stopId || "")]);
    for (const candidateCtx of modeIndex.values()) {
      if (!candidateCtx) continue;
      if (!this._stopsAreInfluenceCompatible(anchorCtx, candidateCtx)) continue;
      stopIds.add(String(candidateCtx.stopId || ""));
    }
    return [...stopIds].filter(Boolean).sort();
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

  // ── Layer visibility toggle controls ───────────────────────────────────────

  /**
   * Toggle a layer-type+mode visibility. Schedules a 10-minute auto-revert
   * back to YAML-configured defaults after any user interaction.
   * @param {'routes'|'live'|'stops'} type
   * @param {'train'|'bus'|'ferry'|'cable'} mode
   */
  _toggleLayerVisibility(type, mode) {
    if (!this._layerVisibility[type]) return;
    this._layerVisibility[type][mode] = !this._layerVisibility[type][mode];
    this._applyLayerVisibility(type, mode);
    if (type === 'stops') {
      this._scheduleStopBadgeOverlapLayout();
    }
    this._scheduleLayerRevert();
    this.requestUpdate();
  }

  _onDocumentPointerDown(event) {
    if (!this._layerPanelOpen) return;
    const path = typeof event.composedPath === 'function' ? event.composedPath() : [];
    const clickedInsidePanel = path.some((node) => node?.classList?.contains?.('layer-panel-wrap'));
    if (clickedInsidePanel) return;
    this._layerPanelOpen = false;
    this.requestUpdate();
  }

  _applyLayerVisibility(type, mode) {
    if (!this.map) return;
    const vis = this._layerVisibility[type][mode] !== false ? 'visible' : 'none';
    let layerMap;
    if (type === 'routes') layerMap = this._routeLayersByMode;
    else if (type === 'stops') layerMap = this._stopLayersByMode;
    else if (type === 'live')  layerMap = this._liveLayersByMode;
    if (!layerMap) return;
    const ids = layerMap.get(mode) || new Set();
    ids.forEach((id) => {
      if (this.map.getLayer(id)) {
        try { this.map.setLayoutProperty(id, 'visibility', vis); } catch (_) {}
      }
    });
  }

  /**
   * Reset visibility state from YAML config defaults (all true unless the
   * config explicitly disables them — currently all default to visible).
   */
  _revertLayerVisibilityToDefaults() {
    const modes = ['train', 'bus', 'ferry', 'cable'];
    const types = ['routes', 'live', 'stops'];
    const defaults = this._layerDefaultVisibility || this._layerVisibilityFromConfig(this.config);
    types.forEach((type) => {
      modes.forEach((mode) => {
        this._layerVisibility[type][mode] = defaults[type]?.[mode] !== false;
        this._applyLayerVisibility(type, mode);
      });
    });
    this._scheduleStopBadgeOverlapLayout();
    this.requestUpdate();
  }

  _scheduleLayerRevert() {
    if (this._layerResetTimer) clearTimeout(this._layerResetTimer);
    this._layerResetTimer = setTimeout(() => {
      this._layerResetTimer = null;
      this._revertLayerVisibilityToDefaults();
    }, 10 * 60 * 1000); // 10 minutes
  }

  // ───────────────────────────────────────────────────────────────────────────

  _parseTrackerTimestamp(value) {
    if (value === null || value === undefined) return null;
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric <= 0) return null;
    return numeric;
  }

  // Calculate bearing (degrees) between two [lon, lat] points
  _bearing(lon1, lat1, lon2, lat2) {
    const dLon = (Number(lon2) - Number(lon1)) * Math.PI / 180;
    const lat1Rad = Number(lat1) * Math.PI / 180;
    const lat2Rad = Number(lat2) * Math.PI / 180;
    const y = Math.sin(dLon) * Math.cos(lat2Rad);
    const x = Math.cos(lat1Rad) * Math.sin(lat2Rad) - Math.sin(lat1Rad) * Math.cos(lat2Rad) * Math.cos(dLon);
    const bearingRad = Math.atan2(y, x);
    const bearingDeg = (bearingRad * 180 / Math.PI + 360) % 360;
    return bearingDeg;
  }

  // Calculate distance in meters between two [lon, lat] points
  _distanceMeters(lon1, lat1, lon2, lat2) {
    const R = 6371000; // Earth radius in meters
    const lat1Rad = Number(lat1) * Math.PI / 180;
    const lat2Rad = Number(lat2) * Math.PI / 180;
    const dLat = (Number(lat2) - Number(lat1)) * Math.PI / 180;
    const dLon = (Number(lon2) - Number(lon1)) * Math.PI / 180;
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(lat1Rad) * Math.cos(lat2Rad) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  // Project a point onto a line segment; returns { lon, lat, tParam: 0-1 along segment }
  _projectPointOntoSegment(lon, lat, segStart, segEnd) {
    const [x0, y0] = [Number(lon), Number(lat)];
    const [x1, y1] = [Number(segStart[0]), Number(segStart[1])];
    const [x2, y2] = [Number(segEnd[0]), Number(segEnd[1])];

    const dx = x2 - x1, dy = y2 - y1;
    const len2 = dx * dx + dy * dy;
    if (len2 < 1e-10) return { lon: x1, lat: y1, tParam: 0 };

    let t = ((x0 - x1) * dx + (y0 - y1) * dy) / len2;
    t = Math.max(0, Math.min(1, t)); // Clamp to segment

    return {
      lon: x1 + t * dx,
      lat: y1 + t * dy,
      tParam: t,
    };
  }

  // Find closest point on entire route path and compute tangent bearing
  _pathBearingForCoords(lon, lat, routeCoordinates) {
    if (!Array.isArray(routeCoordinates) || routeCoordinates.length < 2) return null;

    let minDist = Infinity;
    let bestSegIdx = -1;
    let bestProj = null;

    // Find closest segment
    for (let i = 0; i < routeCoordinates.length - 1; i++) {
      const proj = this._projectPointOntoSegment(lon, lat, routeCoordinates[i], routeCoordinates[i + 1]);
      const dist = this._distanceMeters(lon, lat, proj.lon, proj.lat);
      if (dist < minDist) {
        minDist = dist;
        bestSegIdx = i;
        bestProj = proj;
      }
    }

    if (bestSegIdx < 0 || !bestProj) return null;

    // Calculate bearing along the segment
    const segStart = routeCoordinates[bestSegIdx];
    const segEnd = routeCoordinates[bestSegIdx + 1];
    const tangentBearing = this._bearing(segStart[0], segStart[1], segEnd[0], segEnd[1]);

    return {
      bearing: tangentBearing,
      reverseBearing: (tangentBearing + 180) % 360,
      minDistance: minDist,
    };
  }

  _angularDifference(a, b) {
    const diff = Math.abs(Number(a) - Number(b)) % 360;
    return diff > 180 ? 360 - diff : diff;
  }

  // Compute best bearing: route tangent primary, vehicle bearing as fallback
  _computeVehicleBearing(state, routeFeatures) {
    const lon = Number(state.attributes.longitude);
    const lat = Number(state.attributes.latitude);
    const rawBearing = state.attributes.bearing;
    const vehicleBearing = (rawBearing !== null && rawBearing !== undefined && Number.isFinite(Number(rawBearing)))
      ? Number(rawBearing) : null;

    // Try to get tangent bearing from route geometry
    if (routeFeatures && Array.isArray(routeFeatures) && routeFeatures.length > 0) {
      for (const feature of routeFeatures) {
        const geom = feature.geometry;
        if (!geom) continue;

        let coords = null;
        if (geom.type === 'LineString') {
          coords = geom.coordinates;
        } else if (geom.type === 'MultiLineString') {
          // Use the first segment for now
          coords = geom.coordinates[0];
        }

        if (coords && Array.isArray(coords) && coords.length >= 2) {
          const pathBearing = this._pathBearingForCoords(lon, lat, coords);
          if (pathBearing) {
            if (vehicleBearing !== null) {
              const directDiff = this._angularDifference(pathBearing.bearing, vehicleBearing);
              const reverseDiff = this._angularDifference(pathBearing.reverseBearing, vehicleBearing);
              const chosenBearing = directDiff <= reverseDiff
                ? pathBearing.bearing
                : pathBearing.reverseBearing;
              // Add 180 for pin rotation (pin points down at 0°)
              return (chosenBearing + 180) % 360;
            }

            // Without a vehicle bearing, keep the route tangent as the best available heading.
            return (pathBearing.bearing + 180) % 360;
          }
        }
      }
    }

    // Fallback to vehicle bearing if route geometry unavailable or doesn't help
    if (vehicleBearing !== null) {
      return (vehicleBearing + 180) % 360;
    }

    return 0; // Default north
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

    // Metlink ferry schedules can expose MIF/QDF as service labels while live
    // ferry trackers remain attached to the shared published ferry route id.
    if (raw === "mif" || raw === "qdf" || digits === "8" || digits === "14") {
      variants.add("mif");
      variants.add("qdf");
      variants.add("8");
      variants.add("14");
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

  _liveFeaturesForRoute(routeEntry, mode, routeMeta, routeFeatures) {
    if (!this.hass || !routeMeta) return [];
    const maxAge = Number(this.config.live_max_age_seconds || 120);
    const skipAgeFilter = mode === "ferry";
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

        if (skipAgeFilter) return true;

        const ts = this._parseTrackerTimestamp(state.attributes.timestamp);
        if (!ts) return false;
        return (nowEpoch - ts) <= maxAge;
      })
      .map(([entityId, state]) => {
        const iconBearing = this._computeVehicleBearing(state, routeFeatures);
        return {
          type: "Feature",
          geometry: {
            type: "Point",
            coordinates: [Number(state.attributes.longitude), Number(state.attributes.latitude)],
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

  _featureCollectionHash(features) {
    if (!Array.isArray(features) || features.length === 0) return "";
    return features
      .map((feature) => {
        const props = feature?.properties || {};
        const coords = feature?.geometry?.coordinates || [];
        const lon = Number(coords[0]);
        const lat = Number(coords[1]);
        return [
          props.entity_id || "",
          Number.isFinite(lon) ? lon.toFixed(6) : "",
          Number.isFinite(lat) ? lat.toFixed(6) : "",
          Number.isFinite(Number(props.bearing)) ? Number(props.bearing).toFixed(1) : "",
          props.shape_badge_id || "",
          props.text_badge_id || "",
        ].join("|");
      })
      .join(";");
  }

  _setLiveSourceData(sourceId, features) {
    if (!this.map) return;

    const nextHash = this._featureCollectionHash(features);
    if (this._liveSlotHashes.get(sourceId) === nextHash) {
      return;
    }

    const data = {
      type: "FeatureCollection",
      features: Array.isArray(features) ? features : [],
    };

    const source = this.map.getSource(sourceId);
    if (source) {
      source.setData(data);
    } else {
      this.map.addSource(sourceId, {
        type: "geojson",
        data,
      });
    }

    this._liveSlotHashes.set(sourceId, nextHash);
  }

  _ensureLiveLayers(sourceId, mode) {
    if (!this.map) return;

    const shapeLayerId = `shape-${sourceId}`;
    const textLayerId = `text-${sourceId}`;

    if (!this.map.getLayer(shapeLayerId)) {
      this.map.addLayer({
        id: shapeLayerId,
        type: "symbol",
        source: sourceId,
        layout: {
          "icon-image": ["get", "shape_badge_id"],
          "icon-anchor": "center",
          "icon-allow-overlap": true,
          "icon-ignore-placement": true,
          "icon-rotate": ["coalesce", ["get", "icon_rotation"], 0],
          "icon-rotation-alignment": "map",
          "icon-pitch-alignment": "map",
        },
      });
    }

    if (!this.map.getLayer(textLayerId)) {
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
    }

    // Track live layers by mode for visibility toggling
    if (mode) {
      if (!this._liveLayersByMode.has(mode)) this._liveLayersByMode.set(mode, new Set());
      this._liveLayersByMode.get(mode).add(shapeLayerId);
      this._liveLayersByMode.get(mode).add(textLayerId);
      // Apply current visibility state
      const vis = this._layerVisibility.live[mode] !== false ? 'visible' : 'none';
      if (this.map.getLayer(shapeLayerId)) this.map.setLayoutProperty(shapeLayerId, 'visibility', vis);
      if (this.map.getLayer(textLayerId))  this.map.setLayoutProperty(textLayerId,  'visibility', vis);
    }
  }

  _computeGpsSnapshot() {
    const states = this.hass?.states || {};
    return Object.entries(states)
      .filter(([id]) => id.startsWith("device_tracker."))
      .map(([id, state]) => {
        const a = state?.attributes || {};
        const lat = Number(a.latitude);
        const lon = Number(a.longitude);
        const bearing = Number.isFinite(Number(a.bearing)) ? Number(a.bearing) : 0;
        return `${id}:${Number.isFinite(lat) ? lat.toFixed(5) : "?"}:${Number.isFinite(lon) ? lon.toFixed(5) : "?"}:${bearing.toFixed(0)}`;
      })
      .sort()
      .join(";");
  }

  _resetBubbleAutoCloseTimer() {
    if (this._bubbleAutoCloseTimer) {
      clearTimeout(this._bubbleAutoCloseTimer);
      this._bubbleAutoCloseTimer = null;
    }
    if (!this._departureBubble) return;
    this._bubbleAutoCloseTimer = setTimeout(() => {
      this._closeDepartureBubble();
    }, 30000);
  }

  _closeDepartureBubble() {
    if (this._bubbleAutoCloseTimer) {
      clearTimeout(this._bubbleAutoCloseTimer);
      this._bubbleAutoCloseTimer = null;
    }
    if (!this._departureBubble) return;
    this._departureBubble = null;
    this.requestUpdate();
  }

  _stopBubbleSide(anchorX) {
    if (!this.map) return "right";
    const width = this.map.getContainer()?.clientWidth || 0;
    return anchorX > (width * 0.6) ? "left" : "right";
  }

  _updateDepartureBubbleAnchor() {
    if (!this.map || !this._departureBubble?.stop) return;
    const [lon, lat] = this._departureBubble.stop.coordinates;
    const projected = this.map.project([lon, lat]);
    const nextSide = this._stopBubbleSide(projected.x);
    this._departureBubble = {
      ...this._departureBubble,
      anchorX: projected.x,
      anchorY: projected.y,
      side: nextSide,
    };
    this.requestUpdate();
  }

  _boardEntitiesFromStates() {
    const states = this.hass?.states || {};
    return Object.entries(states)
      .filter(([entityId, state]) => {
        if (!entityId.startsWith("sensor.")) return false;
        const attrs = state?.attributes || {};
        const dataUrl = String(attrs.data_url || "");
        return dataUrl.includes("/local/metlink_explorer/board/") && dataUrl.endsWith("_departures.json");
      })
      .map(([, state]) => state);
  }

  async _fetchBoardPayload(dataUrl) {
    const now = Date.now();
    const cached = this._boardPayloadCache.get(dataUrl);
    if (cached && (now - cached.ts) < 10000) return cached.payload;

    try {
      const response = await fetch(dataUrl, { cache: "no-store" });
      if (!response.ok) return null;
      const payload = await response.json();
      this._boardPayloadCache.set(dataUrl, { ts: now, payload });
      return payload;
    } catch (_) {
      return null;
    }
  }

  _parseDepartureDateTime(serviceDate, departureTime) {
    const raw = String(departureTime || "").replace(/^Scheduled:\s*/i, "").trim();
    const match = raw.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
    if (!match) return null;

    const hours = Number(match[1]);
    const minutes = Number(match[2]);
    const seconds = Number(match[3] || 0);
    if (!Number.isFinite(hours) || !Number.isFinite(minutes) || !Number.isFinite(seconds)) return null;

    let year;
    let month;
    let day;

    const serviceText = String(serviceDate || "");
    if (/^\d{8}$/.test(serviceText)) {
      year = Number(serviceText.slice(0, 4));
      month = Number(serviceText.slice(4, 6));
      day = Number(serviceText.slice(6, 8));
    } else {
      const now = new Date();
      year = now.getFullYear();
      month = now.getMonth() + 1;
      day = now.getDate();
    }

    const dt = new Date(year, month - 1, day, 0, 0, 0, 0);
    dt.setSeconds((hours * 3600) + (minutes * 60) + seconds);
    return dt;
  }

  _formatCountdown(deltaMs) {
    const totalMinutes = Math.max(0, Math.floor(deltaMs / 60000));
    if (totalMinutes < 60) {
      return `${totalMinutes}min`;
    }
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return `${hours}h ${minutes}min`;
  }

  _formatDepartureLine(departureDate, deltaMs) {
    const timeFmt = new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
    const dayFmt = new Intl.DateTimeFormat(undefined, {
      weekday: "short",
      day: "numeric",
      month: "short",
    });
    return `Departs ${timeFmt.format(departureDate)} on ${dayFmt.format(departureDate)}, in ${this._formatCountdown(deltaMs)}.`;
  }

  _deriveDirectionMeta(rows) {
    const uniqueKeys = [];
    const seen = new Set();
    (rows || []).forEach((row) => {
      const key = String(row?.directionKey || "").trim();
      if (!key || seen.has(key)) return;
      seen.add(key);
      uniqueKeys.push(key);
    });

    const inboundKey = uniqueKeys.length > 0 ? uniqueKeys[0] : null;
    const outboundKey = uniqueKeys.length > 1 ? uniqueKeys[1] : null;
    return {
      inboundKey,
      outboundKey,
      hasBoth: Boolean(inboundKey && outboundKey),
    };
  }

  _filteredBubbleDepartures(bubble) {
    const rows = Array.isArray(bubble?.departures) ? bubble.departures : [];
    const filter = String(bubble?.directionFilter || "all");
    const inboundKey = bubble?.directionMeta?.inboundKey;
    const outboundKey = bubble?.directionMeta?.outboundKey;

    if (filter === "inbound" && inboundKey) {
      return rows.filter((row) => String(row?.directionKey || "") === inboundKey);
    }
    if (filter === "outbound" && outboundKey) {
      return rows.filter((row) => String(row?.directionKey || "") === outboundKey);
    }
    return rows;
  }

  _departureDirectionTag(dep, bubble) {
    if (!bubble?.directionMeta?.hasBoth) return "";
    const key = String(dep?.directionKey || "");
    if (key && key === bubble.directionMeta.inboundKey) return "Inbound";
    if (key && key === bubble.directionMeta.outboundKey) return "Outbound";
    return "";
  }

  _setBubbleDirectionFilter(filter) {
    if (!this._departureBubble) return;
    const next = String(filter || "all");
    const inboundKey = this._departureBubble?.directionMeta?.inboundKey;
    const outboundKey = this._departureBubble?.directionMeta?.outboundKey;
    if (next === "inbound" && !inboundKey) return;
    if (next === "outbound" && !outboundKey) return;
    if (this._departureBubble.directionFilter === next) return;
    this._departureBubble = {
      ...this._departureBubble,
      directionFilter: next,
    };
    this.requestUpdate();
    this._resetBubbleAutoCloseTimer();
  }

  _isTrainDepartureRow(row, payloadTransportationType = "") {
    const rowType = String(row?.route_type || "").trim().toLowerCase();
    const payloadType = String(payloadTransportationType || "").trim().toLowerCase();
    return rowType === "train" || payloadType === "train";
  }

  _normalizeTrainStationStopId(stopId) {
    const raw = String(stopId || "").trim().toUpperCase();
    if (!raw) return "";
    // Collapse platform/index suffixes such as WELL1/WELL2, WELL_1, WELL-2, WELL 3.
    return raw.replace(/[\s_-]*\d+$/, "");
  }

  _stopIdMatchesBubbleStop(row, bubbleStopId, payloadTransportationType = "") {
    const rowStopId = String(row?.stop_id || "").trim();
    const targetStopId = String(bubbleStopId || "").trim();
    if (!rowStopId || !targetStopId) return false;
    if (rowStopId === targetStopId) return true;
    if (!this._isTrainDepartureRow(row, payloadTransportationType)) return false;

    const rowStationId = this._normalizeTrainStationStopId(rowStopId);
    const targetStationId = this._normalizeTrainStationStopId(targetStopId);
    return Boolean(rowStationId && targetStationId && rowStationId === targetStationId);
  }

  async _departuresForStops(stopIds, modeBucket = "") {
    const now = Date.now();
    const maxFutureMs = 24 * 3600 * 1000;
    const maxPastMs = -60 * 1000;
    const targetMode = this._modeBucket(modeBucket);
    const rawStopIds = Array.isArray(stopIds) ? stopIds : [stopIds];
    const normalizedStopIds = [...new Set(rawStopIds.map((id) => String(id || "").trim()).filter(Boolean))];
    if (normalizedStopIds.length === 0) return [];

    const entities = this._boardEntitiesFromStates();
    if (entities.length === 0) return [];

    const payloads = await Promise.all(
      entities.map((state) => this._fetchBoardPayload(String(state?.attributes?.data_url || "")))
    );

    const rows = [];
    const seenKeys = new Set();
    payloads.forEach((payload) => {
      const departures = payload?.departures;
      const payloadTransportationType = String(payload?.transportation_type || "").trim().toLowerCase();
      const payloadModeBucket = this._modeBucket(payloadTransportationType);
      if (targetMode && payloadModeBucket && payloadModeBucket !== targetMode) return;
      if (!Array.isArray(departures)) return;

      departures.forEach((row) => {
        const matchesStop = normalizedStopIds.some((candidateStopId) =>
          this._stopIdMatchesBubbleStop(row, candidateStopId, payloadTransportationType)
        );
        if (!matchesStop) return;

        const rowModeBucket = this._modeBucket(row?.route_type || payloadTransportationType);
        if (targetMode && rowModeBucket && rowModeBucket !== targetMode) return;

        const depDate = this._parseDepartureDateTime(row?.service_date, row?.scheduled_departure_time || row?.departure_time);
        if (!depDate) return;
        const deltaMs = depDate.getTime() - now;
        if (deltaMs < maxPastMs || deltaMs > maxFutureMs) return;

        const routeShortName = String(row?.route_short_name || row?.service_label || row?.route_id || "?");
        const directionLabel = String(row?.direction_label || row?.destination || "Unknown direction");
        const directionIdRaw = row?.direction_id;
        const directionId = directionIdRaw === undefined || directionIdRaw === null
          ? ""
          : String(directionIdRaw).trim();
        const directionKey = directionId || directionLabel;
        const routeCanonical = routeShortName.trim().toUpperCase();
        const directionCanonical = directionLabel.trim().toUpperCase();
        const stopCanonical = this._isTrainDepartureRow(row, payloadTransportationType)
          ? (this._normalizeTrainStationStopId(row?.stop_id) || String(row?.stop_id || "").trim().toUpperCase())
          : String(row?.stop_id || "").trim().toUpperCase();
        const dedupeKey = `row:${stopCanonical}:${routeCanonical}:${directionCanonical}:${depDate.getTime()}`;
        if (seenKeys.has(dedupeKey)) return;
        seenKeys.add(dedupeKey);

        rows.push({
          routeShortName,
          directionLabel,
          directionKey,
          departureDate: depDate,
          departureText: this._formatDepartureLine(depDate, deltaMs),
          sortTime: depDate.getTime(),
        });
      });
    });

    rows.sort((a, b) => a.sortTime - b.sortTime);
    return rows;
  }

  async _openDepartureBubble(stopFeature) {
    const openSequence = ++this._bubbleOpenSequence;

    const coords = stopFeature?.geometry?.coordinates || [];
    const lon = Number(coords[0]);
    const lat = Number(coords[1]);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;

    const stopId = String(stopFeature?.properties?.stop_id || "");
    const stopName = String(stopFeature?.properties?.stop_name || `Stop ${stopId}`);
    const modeBucket = this._modeBucket(stopFeature?.properties?.mode || "");
    const influenceIdsRaw = String(stopFeature?.properties?.influence_stop_ids || "");
    const influenceStopIds = influenceIdsRaw
      .split("|")
      .map((id) => String(id || "").trim())
      .filter(Boolean);
    const stopScopeIds = [...new Set([stopId, ...influenceStopIds].filter(Boolean))];

    // Always close any existing bubble first so the next one can replay its entry animation.
    if (this._departureBubble) {
      this._closeDepartureBubble();
      await new Promise((resolve) => setTimeout(resolve, 180));
      if (openSequence !== this._bubbleOpenSequence) return;
    }

    const projected = this.map.project([lon, lat]);
    const side = this._stopBubbleSide(projected.x);

    this._departureBubble = {
      loading: true,
      side,
      anchorX: projected.x,
      anchorY: projected.y,
      stop: {
        id: stopId,
        name: stopName,
        coordinates: [lon, lat],
        influenceStopIds: stopScopeIds,
      },
      departures: [],
      directionFilter: "all",
      directionMeta: {
        inboundKey: null,
        outboundKey: null,
        hasBoth: false,
      },
    };
    this.requestUpdate();
    this._resetBubbleAutoCloseTimer();

    const departures = await this._departuresForStops(stopScopeIds, modeBucket);
    if (openSequence !== this._bubbleOpenSequence) return;
    if (!this._departureBubble || this._departureBubble.stop?.id !== stopId) return;
    this._departureBubble = {
      ...this._departureBubble,
      loading: false,
      departures,
      directionFilter: "all",
      directionMeta: this._deriveDirectionMeta(departures),
    };
    this.requestUpdate();
  }

  _hubFeatureAtPoint(point) {
    if (!this.map || this._hubLayerIds.size === 0) return null;
    const features = this.map.queryRenderedFeatures(point, {
      layers: [...this._hubLayerIds],
    });
    return features && features.length > 0 ? features[0] : null;
  }

  _onMapClick(event) {
    const feature = this._hubFeatureAtPoint(event.point);
    if (!feature) {
      this._closeDepartureBubble();
      return;
    }
    this._runAsyncTask(this._openDepartureBubble(feature), "open departure bubble");
  }

  _runAsyncTask(promise, label = "async task") {
    Promise.resolve(promise).catch((err) => {
      const msg = String(err?.message || "");
      if (err?.name === "AbortError" || /Transition was skipped/i.test(msg)) {
        return;
      }
      console.error(`[MetlinkExplorer] ${label} failed`, err);
    });
  }

  _renderDepartureBubble() {
    const bubble = this._departureBubble;
    if (!bubble) return null;
    const visibleDepartures = this._filteredBubbleDepartures(bubble);
    const canFilterInbound = Boolean(bubble?.directionMeta?.inboundKey);
    const canFilterOutbound = Boolean(bubble?.directionMeta?.outboundKey);
    const influenceCount = Array.isArray(bubble?.stop?.influenceStopIds)
      ? bubble.stop.influenceStopIds.length
      : 0;
    const showInfluenceHint = influenceCount > 1;

    const cardWidth = 360;
    const offset = 30;
    const anchorX = Number(bubble.anchorX || 0);
    const anchorY = Number(bubble.anchorY || 0);
    const left = bubble.side === "right"
      ? (anchorX + offset)
      : (anchorX - cardWidth - offset);
    const top = anchorY - 22;

    return html`
      <div
        class=${`departure-bubble open ${bubble.side}`}
        style=${`left:${left}px;top:${top}px;width:${cardWidth}px;`}
        @click=${(e) => { e.stopPropagation(); this._resetBubbleAutoCloseTimer(); }}
        @mousemove=${() => this._resetBubbleAutoCloseTimer()}
      >
        <div class="departure-head-shell">
          <div class="departure-heading">${bubble.stop?.id || ""} ${bubble.stop?.name || "Stop"}</div>
          ${showInfluenceHint
            ? html`<div class="departure-subheading">Aggregated from ${influenceCount} nearby stops</div>`
            : null}
        </div>
        <div class="departure-body-shell">
          <div class="departure-filters" role="tablist" aria-label="Direction filter">
            <button
              class=${`departure-filter-btn ${bubble.directionFilter === "all" ? "active" : ""}`}
              @click=${() => this._setBubbleDirectionFilter("all")}
            >All</button>
            <button
              class=${`departure-filter-btn ${bubble.directionFilter === "inbound" ? "active" : ""}`}
              ?disabled=${!canFilterInbound}
              @click=${() => this._setBubbleDirectionFilter("inbound")}
            >Inbound</button>
            <button
              class=${`departure-filter-btn ${bubble.directionFilter === "outbound" ? "active" : ""}`}
              ?disabled=${!canFilterOutbound}
              @click=${() => this._setBubbleDirectionFilter("outbound")}
            >Outbound</button>
          </div>
          <div class="departure-list">
            ${bubble.loading ? html`<div class="departure-empty">Loading departures...</div>` : null}
            ${!bubble.loading && visibleDepartures.length === 0 ? html`<div class="departure-empty">No departures for this direction in the next 24h.</div>` : null}
            ${!bubble.loading ? visibleDepartures.map((dep) => html`
              <div class="departure-item">
                <div class="departure-route-line">
                  <div class="departure-route">${dep.routeShortName}</div>
                  ${this._departureDirectionTag(dep, bubble)
                    ? html`<div class="departure-direction-chip">${this._departureDirectionTag(dep, bubble)}</div>`
                    : null}
                </div>
                <div class="departure-destination">${dep.directionLabel}</div>
                <div class="departure-time">${dep.departureText}</div>
              </div>
            `) : null}
          </div>
        </div>
      </div>
    `;
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

  async _renderLiveVehicles() {
    if (!this.map) return;

    if (!this.map.isStyleLoaded()) {
      if (!this._pendingLiveRender) {
        this._pendingLiveRender = true;
        this.map.once('idle', () => {
          this._pendingLiveRender = false;
          this._runAsyncTask(this._renderLiveVehicles(), "render live vehicles (idle)");
        });
      }
      return;
    }

    const categories = ["train", "bus", "ferry"];
    const iconSize = this._clampIconSize(this.config.icon_size || 25);
    const badgeDiameter = Math.max(24, Math.round(iconSize * 2));
    const fontSize = Math.max(12, Math.round(iconSize * 0.78));
    const borderWidth = Math.max(2, Math.round(iconSize * 0.12));
    const dpr = Math.max(1, window.devicePixelRatio || 1);

    // Collect matched vehicles across all route entries; last entry wins per entity.
    const vehicleMap = new Map(); // entityId -> { feature, mode }
    categories.forEach((mode) => {
      const routeEntries = this.config[`${mode}_entities`] || [];
      [...routeEntries].reverse().forEach((entry) => {
        if (entry.live_tracking === false) return;
        const routeFeatures = this._parseRouteGeometry(entry.entity);
        const routeMeta = this._routeMetaFromFeatures(routeFeatures || []) || this._routeMetaFallback(entry);
        if (!routeMeta) return;
        const vehicleFeatures = this._liveFeaturesForRoute(entry, mode, routeMeta, routeFeatures);
        vehicleFeatures.forEach((feature) => {
          const entityId = feature.properties.entity_id;
          if (entityId) vehicleMap.set(entityId, { feature, mode });
        });
      });
    });

    const newActiveSources = new Set();
    let updatedCount = 0;

    for (const [entityId, { feature, mode }] of vehicleMap.entries()) {
      const coords = feature.geometry?.coordinates || [];
      const lon = Number(coords[0]);
      const lat = Number(coords[1]);
      const bearing = Number.isFinite(Number(feature.properties.bearing)) ? Number(feature.properties.bearing) : 0;

      // Epsilon guard: skip setData when vehicle hasn't moved meaningfully.
      const last = this._vehicleLastPositions.get(entityId);
      const safeId = entityId.replace(/\./g, '-');
      const sourceId = `live-vehicle-${safeId}`;
      newActiveSources.add(sourceId);

      if (last &&
          Math.abs(lat - last.lat) < 0.00001 &&
          Math.abs(lon - last.lon) < 0.00001 &&
          Math.abs(bearing - last.bearing) < 0.5) {
        this._ensureLiveLayers(sourceId, mode);
        continue;
      }

      this._vehicleLastPositions.set(entityId, { lat, lon, bearing });

      const routeLabel  = mode === 'ferry' ? "" : (feature.properties.route_label || "");
      const markerColor = feature.properties.marker_color || VEHICLE_COLORS[mode] || "#ff9800";
      const textColor   = feature.properties.text_color || "#ffffff";
      const haloColor   = feature.properties.text_halo_color || "rgba(0,0,0,0.45)";
      let shapeId = this._badgeShapeId(markerColor, badgeDiameter, borderWidth);
      let textId = "";
      if (mode === 'ferry') {
        const directionVariant = this._ferryDirectionVariant(bearing);
        shapeId = this._ferryLiveShapeId(badgeDiameter, borderWidth, directionVariant);
        await this._ensureFerryLiveBadge(shapeId, badgeDiameter, borderWidth, dpr, directionVariant === 'west');
      } else {
        this._ensureBadgeShape(shapeId, markerColor, badgeDiameter, borderWidth, dpr);
        textId = this._badgeTextId(routeLabel, textColor, badgeDiameter, fontSize);
        this._ensureBadgeText(textId, routeLabel, textColor, haloColor, badgeDiameter, fontSize, dpr);
      }

      const featureWithBadge = {
        ...feature,
        properties: {
          ...feature.properties,
          shape_badge_id: shapeId,
          text_badge_id: textId,
          icon_rotation: mode === 'ferry' ? 0 : bearing,
        },
      };

      this._setLiveSourceData(sourceId, [featureWithBadge]);
      this._ensureLiveLayers(sourceId, mode);
      updatedCount++;
    }

    // Clear sources for vehicles that are no longer active.
    this._activeVehicleSources.forEach((sourceId) => {
      if (!newActiveSources.has(sourceId)) {
        this._setLiveSourceData(sourceId, []);
      }
    });
    this._activeVehicleSources = newActiveSources;

    console.log(`[MetlinkExplorer] live vehicles: ${vehicleMap.size} matched, ${updatedCount} setData calls`);

    // Hub layers must remain above vehicle badges.
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
      const selectedStopContextsByMode = new Map();
      this._stopBadgeLayoutSources = new Map();

      // First pass: collect shared selected-stop coordinates across all route entries.
      categories.forEach((cat) => {
        const entries = this.config[`${cat}_entities`] || [];
        [...entries].reverse().forEach((entry) => {
          const selectedStopIds = new Set((entry.selected_stops || []).map((id) => String(id)));
          if (selectedStopIds.size === 0) return;
          const features = this._parseRouteGeometry(entry.entity);
          if (!features) return;

          this._buildSelectedStopContextIndex(cat, entry, features, selectedStopContextsByMode);

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
      this._hubLayerIds.clear();
      // Rebuild mode→layer maps for routes and stops
      this._routeLayersByMode = new Map();
      this._stopLayersByMode  = new Map();

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
          // Track route layer by mode for visibility toggling
          if (!this._routeLayersByMode.has(cat)) this._routeLayersByMode.set(cat, new Set());
          this._routeLayersByMode.get(cat).add(`layer-${sourceId}`);
          // Apply current visibility state immediately
          if (!this._layerVisibility.routes[cat]) {
            this.map.setLayoutProperty(`layer-${sourceId}`, 'visibility', 'none');
          }

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
              const iconSize = this._clampIconSize(this.config.icon_size || 25);
              const markerDiameter = Math.max(24, Math.round(iconSize * 2));
              const uniqueStops = new Map();
              selectedStops.forEach((stop) => {
                const rawStopId = String(stop.stop_id || "").trim();
                const normalizedTrainStopId = this._normalizeTrainStationStopId(rawStopId);
                const stopLon = Number(stop.stop_lon);
                const stopLat = Number(stop.stop_lat);
                const coordKey = this._hubCoordKey(stopLon, stopLat);
                const key = cat === 'train'
                  ? `train:${normalizedTrainStopId || rawStopId.toUpperCase()}:${coordKey || `${stopLat}:${stopLon}`}`
                  : `${rawStopId}:${Number(stop.stop_lat)}:${Number(stop.stop_lon)}`;
                if (!uniqueStops.has(key)) {
                  uniqueStops.set(
                    key,
                    cat === 'train'
                      ? { ...stop, stop_id: normalizedTrainStopId || rawStopId }
                      : stop
                  );
                }
              });
              const dedupedStops = [...uniqueStops.values()];
              const modeBucket = this._modeBucket(cat);
              const modeIndex = selectedStopContextsByMode.get(modeBucket) || new Map();

              const groupedDisplayStops = new Map();
              dedupedStops.forEach((stop) => {
                const rawStopId = String(stop.stop_id || '').trim();
                const stopId = cat === 'train'
                  ? (this._normalizeTrainStationStopId(rawStopId) || rawStopId)
                  : rawStopId;
                const normalizedKey = modeBucket === 'train'
                  ? stopId.toUpperCase()
                  : `${stopId.toUpperCase()}:${Number(stop.stop_lat).toFixed(6)}:${Number(stop.stop_lon).toFixed(6)}`;
                const ctx = modeIndex.get(normalizedKey);
                const influenceStopIds = this._influenceStopIdsForContext(
                  ctx || {
                    stopId,
                    stopName: String(stop.stop_name || 'Hub'),
                    lat: Number(stop.stop_lat),
                    lon: Number(stop.stop_lon),
                    routeSignatures: [],
                  },
                  modeIndex
                );
                const groupKey = influenceStopIds.join('|') || stopId;
                if (!groupedDisplayStops.has(groupKey)) {
                  groupedDisplayStops.set(groupKey, {
                    stop,
                    stopId,
                    influenceStopIds,
                  });
                }
              });

              const displayStops = [...groupedDisplayStops.values()];
              const offsets = this._computeHubCollisionOffsets(displayStops.map((s) => ({
                ...s.stop,
                stop_id: s.stopId,
              })), 24);
              const hubFeatures = displayStops.map((entryStop) => {
                const stop = entryStop.stop;
                const stopId = entryStop.stopId;
                const rawStopId = String(stop.stop_id || '').trim();
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
                    influence_stop_ids: entryStop.influenceStopIds.join('|'),
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

              this._stopBadgeLayoutSources.set(hubSourceId, {
                markerDiameter,
                mode: cat,
                baseFeatures: hubFeatures.map((feature) => ({
                  ...feature,
                  geometry: {
                    ...feature.geometry,
                    coordinates: [...(feature.geometry?.coordinates || [])],
                  },
                  properties: {
                    ...(feature.properties || {}),
                  },
                })),
              });

              const hubImageId = `hub-marker-${cat}-${markerDiameter}`;
              if (cat === 'train') {
                await this._ensureTrainHubImage(hubImageId, markerDiameter, Math.max(1, window.devicePixelRatio || 1));
              } else if (cat === 'bus') {
                await this._ensureBusHubImage(hubImageId, markerDiameter, Math.max(1, window.devicePixelRatio || 1));
              } else if (cat === 'ferry') {
                await this._ensureFerryHubImage(hubImageId, markerDiameter, Math.max(1, window.devicePixelRatio || 1));
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
              this._hubLayerIds.add(hubLayerId);
              // Track stop layer by mode for visibility toggling
              if (!this._stopLayersByMode.has(cat)) this._stopLayersByMode.set(cat, new Set());
              this._stopLayersByMode.get(cat).add(hubLayerId);
              if (!this._layerVisibility.stops[cat]) {
                this.map.setLayoutProperty(hubLayerId, 'visibility', 'none');
              }
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
      this._scheduleStopBadgeOverlapLayout();
    } catch (err) {
      console.error('[MetlinkExplorer] _renderRoutes error', err);
    }
    this.map.once('idle', () => this._runAsyncTask(this._renderLiveVehicles(), "render live vehicles (post routes)"));
    console.log('[MetlinkExplorer] _renderRoutes end');
  }

  _stopBadgeCentersOverlapPx(a, b) {
    const dx = Number(a?.x) - Number(b?.x);
    const dy = Number(a?.y) - Number(b?.y);
    if (!Number.isFinite(dx) || !Number.isFinite(dy)) return false;
    const distance = Math.sqrt((dx * dx) + (dy * dy));
    const rA = Math.max(1, Number(a?.diameter || 0) / 2);
    const rB = Math.max(1, Number(b?.diameter || 0) / 2);
    return distance < (rA + rB);
  }

  _slotOffsets(count, spacingPx) {
    const n = Math.max(0, Number(count) || 0);
    const spacing = Math.max(1, Number(spacingPx) || 1);
    if (n === 0) return [];
    const mid = (n - 1) / 2;
    const offsets = [];
    for (let i = 0; i < n; i++) {
      offsets.push((i - mid) * spacing);
    }
    return offsets;
  }

  _buildInlineLayoutForGroup(group, axis) {
    if (!Array.isArray(group) || group.length === 0) return [];

    const centerX = group.reduce((sum, item) => sum + item.x, 0) / group.length;
    const centerY = group.reduce((sum, item) => sum + item.y, 0) / group.length;
    const maxDiameter = Math.max(...group.map((item) => Math.max(1, Number(item.diameter) || 1)));
    const spacing = maxDiameter + 3;
    const offsets = this._slotOffsets(group.length, spacing);

    const sorted = [...group].sort((a, b) => {
      const keyA = axis === 'x' ? a.x : a.y;
      const keyB = axis === 'x' ? b.x : b.y;
      if (keyA !== keyB) return keyA - keyB;
      const modeWeight = { ferry: 0, train: 1, bus: 2, cable: 3 };
      const wA = modeWeight[String(a.mode || '').toLowerCase()] ?? 9;
      const wB = modeWeight[String(b.mode || '').toLowerCase()] ?? 9;
      return wA - wB;
    });

    return sorted.map((item, index) => {
      const along = offsets[index];
      const x = axis === 'x' ? (centerX + along) : centerX;
      const y = axis === 'y' ? (centerY + along) : centerY;
      return {
        ...item,
        layoutX: x,
        layoutY: y,
      };
    });
  }

  _totalLayoutDisplacement(layoutItems) {
    return (layoutItems || []).reduce((sum, item) => {
      const dx = Number(item.layoutX) - Number(item.x);
      const dy = Number(item.layoutY) - Number(item.y);
      if (!Number.isFinite(dx) || !Number.isFinite(dy)) return sum;
      return sum + Math.sqrt((dx * dx) + (dy * dy));
    }, 0);
  }

  _scheduleStopBadgeOverlapLayout() {
    if (!this.map) return;
    if (this._stopLayoutDebounceTimer) clearTimeout(this._stopLayoutDebounceTimer);
    this._stopLayoutDebounceTimer = setTimeout(() => {
      this._stopLayoutDebounceTimer = null;
      this._applyStopBadgeOverlapLayout();
    }, 80);
  }

  _applyStopBadgeOverlapLayout() {
    if (!this.map || !this.map.isStyleLoaded()) return;
    if (!this._stopBadgeLayoutSources || this._stopBadgeLayoutSources.size === 0) return;

    const markers = [];
    this._stopBadgeLayoutSources.forEach((entry, hubSourceId) => {
      const source = this.map.getSource(hubSourceId);
      if (!source || !Array.isArray(entry?.baseFeatures)) return;
      const mode = String(entry?.mode || '').toLowerCase();
      if (mode && this._layerVisibility?.stops?.[mode] === false) return;
      entry.baseFeatures.forEach((feature, featureIndex) => {
        const coords = feature?.geometry?.coordinates || [];
        const lon = Number(coords[0]);
        const lat = Number(coords[1]);
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;
        const projected = this.map.project([lon, lat]);
        markers.push({
          hubSourceId,
          featureIndex,
          mode: String(feature?.properties?.mode || ''),
          diameter: Number(entry?.markerDiameter || 0),
          x: projected.x,
          y: projected.y,
          lon,
          lat,
          feature,
        });
      });
    });

    if (markers.length === 0) return;

    const parent = markers.map((_, i) => i);
    const find = (i) => {
      let p = i;
      while (parent[p] !== p) {
        parent[p] = parent[parent[p]];
        p = parent[p];
      }
      return p;
    };
    const union = (a, b) => {
      const pa = find(a);
      const pb = find(b);
      if (pa !== pb) parent[pb] = pa;
    };

    for (let i = 0; i < markers.length; i++) {
      for (let j = i + 1; j < markers.length; j++) {
        if (this._stopBadgeCentersOverlapPx(markers[i], markers[j])) {
          union(i, j);
        }
      }
    }

    const groups = new Map();
    markers.forEach((marker, index) => {
      const root = find(index);
      if (!groups.has(root)) groups.set(root, []);
      groups.get(root).push(marker);
    });

    const perSourceFeatures = new Map();
    this._stopBadgeLayoutSources.forEach((entry, hubSourceId) => {
      perSourceFeatures.set(hubSourceId, entry.baseFeatures.map((f) => ({ ...f })));
    });

    groups.forEach((group) => {
      if (!Array.isArray(group) || group.length <= 1) return;
      const horizontal = this._buildInlineLayoutForGroup(group, 'x');
      const vertical = this._buildInlineLayoutForGroup(group, 'y');
      const best = this._totalLayoutDisplacement(horizontal) <= this._totalLayoutDisplacement(vertical)
        ? horizontal
        : vertical;

      best.forEach((item) => {
        const srcFeatures = perSourceFeatures.get(item.hubSourceId);
        if (!Array.isArray(srcFeatures)) return;
        const existing = srcFeatures[item.featureIndex];
        if (!existing) return;
        const nextLonLat = this.map.unproject([item.layoutX, item.layoutY]);
        srcFeatures[item.featureIndex] = {
          ...existing,
          geometry: {
            ...existing.geometry,
            coordinates: [nextLonLat.lng, nextLonLat.lat],
          },
        };
      });
    });

    perSourceFeatures.forEach((features, hubSourceId) => {
      const source = this.map.getSource(hubSourceId);
      if (!source || typeof source.setData !== 'function') return;
      source.setData({ type: 'FeatureCollection', features });
    });

    this._bringHubLayersToFront();
  }

  updated(changedProps) {
    this._applyLayoutMode();
    if (this.map) {
      if (changedProps.has('config')) {
        const oldConfig = changedProps.get('config');
        if (oldConfig?.map_style !== this.config.map_style) this._updateMapStyle();
        if (oldConfig?.map_projection !== this.config.map_projection) this._applyMapProjection(true);
        if (oldConfig?.icon_size !== this.config.icon_size) {
          // Force full live badge refresh on size change, even for stationary vehicles.
          this._vehicleLastPositions.clear();
        }
        this._centerMap();
        this._runAsyncTask(this._renderRoutes(), "render routes (config update)");
      }
      if (changedProps.has('hass')) {
        const snapshot = this._computeGpsSnapshot();
        if (snapshot !== this._liveGpsSnapshot) {
          this._liveGpsSnapshot = snapshot;
          this._runAsyncTask(this._renderLiveVehicles(), "render live vehicles (state update)");
        }

        // If integration restarts while kiosk is open, re-arm forced overlay redraws.
        if (this._startupSettled && !this._overlayStartupStable()) {
          console.log('[MetlinkExplorer] startup stability lost; restarting forced overlay redraw loop');
          this._restartStartupOverlayRedrawLoop();
        }
      }
    }
    this._forceSectionBreakout();
  }

  async firstUpdated() {
    console.log('[MetlinkExplorer] firstUpdated start');
    this._applyLayoutMode();
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
      pitch: this._isIsometricProjection() ? 55 : 0,
      bearing: this._isIsometricProjection() ? -20 : 0,
      attributionControl: false
    });

    if (this.map.getLayer('simple-tiles')) {
      this.map.setPaintProperty('simple-tiles', 'raster-fade-duration', TILE_FADE_DURATION_MS);
    }

    this.map.on('load', () => {
      console.log('[MetlinkExplorer] map load event');
      this.map.resize();
      this._applyMapProjection(false);
      this._centerMap();
      this._runAsyncTask(this._renderRoutes(), "render routes (map load)");
      this._startStartupOverlayRedrawLoop();
    });

    this.map.on('click', this._boundMapClick);
    this.map.on('move', this._boundMapMove);
    this.map.on('zoom', this._boundMapMove);
    this.map.on('moveend', this._boundStopLayoutChange);
    this.map.on('zoomend', this._boundStopLayoutChange);
    this.map.on('rotateend', this._boundStopLayoutChange);

    this.map.on('error', (event) => {
      console.error('[MetlinkExplorer] map error event', event?.error || event);
    });

    this._resizeObserver = new ResizeObserver(() => {
      if (this.map) this.map.resize();
    });
    this._resizeObserver.observe(this);
  }

  _detectEditorPreviewMode() {
    // Home Assistant card editor wrappers.
    return Boolean(
      this.closest('hui-dialog-edit-card')
      || this.closest('hui-card-preview')
      || this.closest('hui-card-element-editor')
    );
  }

  _applyLayoutMode() {
    this._isEditorPreview = this._detectEditorPreviewMode();
    const hostHeight = this._isEditorPreview ? '420px' : 'calc(100vh - 64px)';
    if (this._appliedHostHeight === hostHeight) return;
    this._appliedHostHeight = hostHeight;
    this.style.setProperty('--metlink-card-height', hostHeight);
    if (this.map) {
      try { this.map.resize(); } catch (_) {}
    }
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

  _configuredRouteEntries() {
    const categories = ['train', 'bus', 'ferry', 'cable'];
    return categories.reduce((total, cat) => total + (this.config?.[`${cat}_entities`] || []).length, 0);
  }

  _routeEntitiesReadyCount() {
    const categories = ['train', 'bus', 'ferry', 'cable'];
    let ready = 0;
    categories.forEach((cat) => {
      const entries = this.config?.[`${cat}_entities`] || [];
      entries.forEach((entry) => {
        const features = this._parseRouteGeometry(entry?.entity);
        if (Array.isArray(features) && features.length > 0) ready += 1;
      });
    });
    return ready;
  }

  _hasConfiguredSelectedStops() {
    const categories = ['train', 'bus', 'ferry', 'cable'];
    return categories.some((cat) => {
      const entries = this.config?.[`${cat}_entities`] || [];
      return entries.some((entry) => Array.isArray(entry?.selected_stops) && entry.selected_stops.length > 0);
    });
  }

  _overlayStartupStable() {
    const expectedRoutes = this._configuredRouteEntries();
    const readyRoutes = this._routeEntitiesReadyCount();
    const routesDrawn = this._routeLayersByMode.size > 0;
    const stopsConfigured = this._hasConfiguredSelectedStops();
    const stopsDrawn = !stopsConfigured || this._hubLayerIds.size > 0;
    return expectedRoutes > 0 && readyRoutes >= expectedRoutes && routesDrawn && stopsDrawn;
  }

  _stopStartupOverlayRedrawLoop() {
    if (this._startupRedrawTimer) {
      clearInterval(this._startupRedrawTimer);
      this._startupRedrawTimer = null;
    }
  }

  _restartStartupOverlayRedrawLoop() {
    this._startupSettled = false;
    this._startupStableTicks = 0;
    this._startStartupOverlayRedrawLoop();
  }

  _startStartupOverlayRedrawLoop() {
    if (this._startupRedrawTimer) return;
    this._startupSettled = false;
    this._startupStableTicks = 0;
    this._startupRedrawTimer = setInterval(() => {
      this._runAsyncTask(this._forceStartupOverlayRedrawTick(), "startup overlay redraw tick");
    }, STARTUP_REDRAW_INTERVAL_MS);
    this._runAsyncTask(this._forceStartupOverlayRedrawTick(), "startup overlay redraw initial tick");
  }

  async _forceStartupOverlayRedrawTick() {
    if (!this.map || !this.map.isStyleLoaded()) return;

    // Force overlay refreshes only: routes/stops/live badges. Base raster map remains untouched.
    this._vehicleLastPositions.clear();
    await this._renderRoutes();
    await this._renderLiveVehicles();

    if (this._overlayStartupStable()) {
      this._startupStableTicks += 1;
      if (this._startupStableTicks >= STARTUP_STABLE_TICKS_REQUIRED) {
        this._startupSettled = true;
        this._stopStartupOverlayRedrawLoop();
        console.log('[MetlinkExplorer] startup overlay redraw loop settled; stopping forced redraws');
      }
      return;
    }

    this._startupStableTicks = 0;
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
    this.map.addLayer({
      id: 'simple-tiles',
      type: 'raster',
      source: 'raster-tiles',
      paint: {
        'raster-fade-duration': TILE_FADE_DURATION_MS,
      },
    });
    this.map.once('idle', () => this._runAsyncTask(this._renderRoutes(), "render routes (style update)"));
  }

  disconnectedCallback() {
    window.removeEventListener('pointerdown', this._boundDocumentPointerDown, true);
    this._stopStartupOverlayRedrawLoop();
    if (this._stopLayoutDebounceTimer) {
      clearTimeout(this._stopLayoutDebounceTimer);
      this._stopLayoutDebounceTimer = null;
    }
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }
    if (this._bubbleAutoCloseTimer) {
      clearTimeout(this._bubbleAutoCloseTimer);
      this._bubbleAutoCloseTimer = null;
    }
    if (this.map) {
      this.map.off('click', this._boundMapClick);
      this.map.off('move', this._boundMapMove);
      this.map.off('zoom', this._boundMapMove);
      this.map.off('moveend', this._boundStopLayoutChange);
      this.map.off('zoomend', this._boundStopLayoutChange);
      this.map.off('rotateend', this._boundStopLayoutChange);
    }
    super.disconnectedCallback();
  }

  render() {
    return html`
      <ha-card>
        <div id="map"></div>
        ${this._renderLayerPanel()}
        ${this._renderDepartureBubble()}
      </ha-card>
    `;
  }

  _renderLayerPanel() {
    // Determine which modes actually have configured entities so we only show
    // rows that are relevant to this card instance.
    const modeLabels = { train: 'Train', bus: 'Bus', ferry: 'Ferry', cable: 'Cable Car' };
    const activeModes = ['train', 'bus', 'ferry', 'cable'].filter(
      (m) => (this.config[`${m}_entities`] || []).length > 0
    );
    if (activeModes.length === 0) return html``;

    const open = this._layerPanelOpen;
    const vis = this._layerVisibility;

    const btn = (type, mode, label) => {
      const on = vis[type][mode] !== false;
      return html`<button
        class="lp-btn ${on ? 'on' : 'off'}"
        @click=${() => this._toggleLayerVisibility(type, mode)}
        title="${on ? 'Hide' : 'Show'} ${modeLabels[mode]} ${type}"
      >${label}</button>`;
    };

    return html`
      <div class="layer-panel-wrap">
        <button
          class="lp-hamburger"
          @click=${() => { this._layerPanelOpen = !this._layerPanelOpen; this.requestUpdate(); }}
          title="Layer controls"
          aria-label="Layer controls"
        >
          <span class="lp-ham-line"></span>
          <span class="lp-ham-line"></span>
          <span class="lp-ham-line"></span>
        </button>
        ${open ? html`
          <div class="layer-panel">
            <div class="lp-title">Display Layers</div>
            <div class="lp-section-label">Routes</div>
            <div class="lp-row">
              ${activeModes.map((m) => btn('routes', m, modeLabels[m]))}
            </div>
            <div class="lp-section-label">Stops</div>
            <div class="lp-row">
              ${activeModes.map((m) => btn('stops', m, modeLabels[m]))}
            </div>
            <div class="lp-section-label">Live Tracking</div>
            <div class="lp-row">
              ${activeModes.filter((m) => m !== 'cable').map((m) => btn('live', m, modeLabels[m]))}
            </div>
          </div>
        ` : html``}
      </div>
    `;
  }

  static get styles() {
    return css`
      :host { display: block; width: 100% !important; height: var(--metlink-card-height, calc(100vh - 64px)); grid-column: 1 / -1 !important; }
      ha-card { height: 100%; width: 100%; position: relative; overflow: hidden; background: #1c1c1c; border: none; }
      #map { position: absolute; inset: 0; height: 100%; width: 100%; }
      .departure-bubble {
        position: absolute;
        z-index: 1000;
        color: #fff;
        pointer-events: auto;
      }
      .departure-head-shell {
        background: #000;
        border-radius: 12px;
        padding: 12px;
        box-shadow: 0 14px 40px rgba(0, 0, 0, 0.5);
        opacity: 0;
      }
      .departure-bubble.right.open .departure-head-shell {
        animation: bubble-header-slide-right 220ms cubic-bezier(0.22, 0.61, 0.36, 1) forwards;
      }
      .departure-bubble.left.open .departure-head-shell {
        animation: bubble-header-slide-left 220ms cubic-bezier(0.22, 0.61, 0.36, 1) forwards;
      }
      .departure-body-shell {
        margin-top: 8px;
        background: #000;
        border-radius: 12px;
        box-shadow: 0 14px 40px rgba(0, 0, 0, 0.5);
        overflow: hidden;
        max-height: 0;
        opacity: 0;
        transform: translateY(-10px);
      }
      .departure-filters {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 6px;
        padding: 12px 12px 8px;
      }
      .departure-filter-btn {
        appearance: none;
        border: 1px solid rgba(255, 255, 255, 0.32);
        background: rgba(255, 255, 255, 0.08);
        color: rgba(255, 255, 255, 0.9);
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        line-height: 1;
        padding: 7px 10px;
        cursor: pointer;
      }
      .departure-filter-btn.active {
        background: #ffffff;
        color: #111;
        border-color: #ffffff;
      }
      .departure-filter-btn:disabled {
        opacity: 0.45;
        cursor: not-allowed;
      }
      .departure-bubble.open .departure-body-shell {
        animation: bubble-body-drop 240ms ease 220ms forwards;
      }
      .departure-list {
        display: block;
        max-height: min(58vh, 360px);
        overflow-y: auto;
        overflow-x: hidden;
        padding: 0 12px 12px;
      }
      .departure-list::-webkit-scrollbar {
        width: 8px;
      }
      .departure-list::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.3);
        border-radius: 999px;
      }
      .departure-list::-webkit-scrollbar-track {
        background: transparent;
      }
      @keyframes bubble-header-slide-right {
        from {
          opacity: 0;
          transform: translateX(-18px);
        }
        to {
          opacity: 1;
          transform: translateX(0);
        }
      }
      @keyframes bubble-header-slide-left {
        from {
          opacity: 0;
          transform: translateX(18px);
        }
        to {
          opacity: 1;
          transform: translateX(0);
        }
      }
      @keyframes bubble-body-drop {
        from {
          opacity: 0;
          max-height: 0;
          transform: translateY(-10px);
        }
        to {
          opacity: 1;
          max-height: 420px;
          transform: translateY(0);
        }
      }
      .departure-bubble.open {
        pointer-events: auto;
      }
      .departure-heading {
        font-size: 15px;
        line-height: 1.3;
        font-weight: 700;
        margin: 0;
      }
      .departure-subheading {
        margin-top: 4px;
        font-size: 12px;
        line-height: 1.25;
        color: rgba(255, 255, 255, 0.75);
      }
      .departure-item {
        padding: 10px 0;
        border-top: 1px solid rgba(255, 255, 255, 0.2);
      }
      .departure-item:first-child {
        border-top: 1px solid rgba(255, 255, 255, 0.2);
      }
      .departure-route-line {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
      }
      .departure-route {
        font-size: 22px;
        font-weight: 700;
        line-height: 1.1;
      }
      .departure-destination {
        margin-top: 3px;
        font-size: 15px;
        font-weight: 600;
        line-height: 1.2;
      }
      .departure-direction-chip {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.14);
        border: 1px solid rgba(255, 255, 255, 0.28);
        color: rgba(255, 255, 255, 0.95);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.02em;
      }
      .departure-time {
        margin-top: 4px;
        font-size: 13px;
        line-height: 1.35;
        color: rgba(255, 255, 255, 0.85);
      }
      .departure-empty {
        font-size: 14px;
        line-height: 1.35;
        color: rgba(255, 255, 255, 0.85);
        padding: 8px 0 4px;
      }
      @media (max-width: 640px) {
        .departure-bubble {
          width: min(90vw, 360px) !important;
        }
        .departure-list {
          max-height: 50vh;
        }
      }

      /* ── Layer panel ─────────────────────────────────────────────────── */
      .layer-panel-wrap {
        position: absolute;
        top: 12px;
        left: 12px;
        z-index: 900;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 6px;
        pointer-events: auto;
      }
      .lp-hamburger {
        width: 36px;
        height: 36px;
        background: rgba(0, 0, 0, 0.72);
        border: 1px solid rgba(255, 255, 255, 0.22);
        border-radius: 8px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 4px;
        cursor: pointer;
        padding: 0;
        backdrop-filter: blur(4px);
      }
      .lp-hamburger:hover {
        background: rgba(30, 30, 30, 0.88);
      }
      .lp-ham-line {
        display: block;
        width: 16px;
        height: 2px;
        background: #ffffff;
        border-radius: 2px;
      }
      .layer-panel {
        background: rgba(0, 0, 0, 0.82);
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 10px;
        padding: 10px 10px 12px;
        width: max-content;
        min-width: 0;
        backdrop-filter: blur(6px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
      }
      .lp-title {
        color: rgba(255, 255, 255, 0.98);
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        margin: 0 0 8px;
      }
      .lp-section-label {
        color: rgba(255, 255, 255, 0.9);
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 9px 0 5px;
      }
      .lp-section-label:first-child {
        margin-top: 0;
      }
      .lp-row {
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
      }
      .lp-btn {
        appearance: none;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 700;
        line-height: 1;
        padding: 5px 10px;
        cursor: pointer;
        transition: background 120ms, color 120ms, opacity 120ms;
        border: 1px solid rgba(255, 255, 255, 0.28);
      }
      .lp-btn.on {
        background: rgba(255, 255, 255, 0.92);
        color: #111111;
        border-color: #ffffff;
      }
      .lp-btn.off {
        background: rgba(255, 255, 255, 0.08);
        color: rgba(255, 255, 255, 0.55);
        border-color: rgba(255, 255, 255, 0.18);
      }
      .lp-btn:hover {
        opacity: 0.82;
      }
    `;
  }
}

if (!customElements.get("metlink-explorer-map-card")) {
  customElements.define("metlink-explorer-map-card", MetlinkExplorerCard);
  console.log("[MetlinkExplorer] custom element registered: metlink-explorer-map-card");
} else {
  console.log("[MetlinkExplorer] custom element already registered: metlink-explorer-map-card");
}
