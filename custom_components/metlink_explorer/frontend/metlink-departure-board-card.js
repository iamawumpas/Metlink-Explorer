class MetlinkDepartureBoardCard extends HTMLElement {
  static getStubConfig() {
    return {
      type: "custom:metlink-departure-board-card",
      title: "Departures",
      entities: ["sensor.bus_departures_board"],
      route_entities: [],
      stop_filter: "",
      limit: 20,
    };
  }

  setConfig(config) {
    if (!config || (!config.entity && !config.entities)) {
      throw new Error("Provide entity or entities in card configuration");
    }

    const entities = Array.isArray(config.entities)
      ? config.entities
      : config.entity
        ? [config.entity]
        : [];

    this._config = {
      title: config.title || "Departures",
      entities,
      route_entities: Array.isArray(config.route_entities) ? config.route_entities : [],
      stop_filter: (config.stop_filter || "").toLowerCase(),
      limit: Number.isInteger(config.limit) ? config.limit : 20,
      sort_by: config.sort_by || "scheduled",
      show_countdown: config.show_countdown !== false,
      show_dividers: config.show_dividers !== false,
      divider_color: config.divider_color || "#ffffff66",
      fields: {
        route: config.fields?.route !== false,
        description: config.fields?.description !== false,
        stop: config.fields?.stop === true,
        departs: config.fields?.departs !== false,
      },
      route_color: config.route_color || "#ff9800",
      route_size: config.route_size || "1.4em",
      description_color: config.description_color || "#ffffff",
      meta_color: config.meta_color || "#ffd54f",
      card_max_height: config.card_max_height || "300px",
    };

    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }

    if (!this._timer) {
      this._timer = window.setInterval(() => this._render(), 30000);
    }

    this._render();
  }

  disconnectedCallback() {
    if (this._timer) {
      window.clearInterval(this._timer);
      this._timer = null;
    }
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  _render() {
    if (!this._hass || !this._config || !this.shadowRoot) {
      return;
    }

    const routeLabelMap = this._buildRouteLabelMap();
    const rows = this._buildRows(routeLabelMap);
    const sorted = this._sortRows(rows);
    const limited = sorted.slice(0, this._config.limit);

    const itemsHtml =
      limited.length === 0
        ? `<div class="empty">No departures found.</div>`
        : limited
            .map((row, index) => {
              const route = this._config.fields.route
                ? `<div class="route">${this._escape(row.route)}</div>`
                : "";
              const description = this._config.fields.description
                ? `<div class="description">${this._escape(row.description)}</div>`
                : "";
              const stop = this._config.fields.stop
                ? `<div class="stop">${this._escape(row.stop_name)}</div>`
                : "";
              const departs = this._config.fields.departs
                ? `<div class="meta">Departs <span class="meta-strong">${this._escape(row.scheduled_hhmm)}</span>${this._config.show_countdown ? ` in ${this._escape(row.countdown)}` : ""}</div>`
                : "";
              const divider =
                this._config.show_dividers && index < limited.length - 1
                  ? `<hr />`
                  : "";
              return `<div class="item">${route}${description}${stop}${departs}</div>${divider}`;
            })
            .join("");

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }
        .card {
          background: var(--ha-card-background, var(--card-background-color, #1c1c1c));
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, none);
          padding: 12px;
          max-height: ${this._config.card_max_height};
          overflow-y: auto;
          overflow-x: hidden;
          scrollbar-width: thin;
        }
        .title {
          margin: 0 0 10px 0;
          font-size: 1.1em;
          font-weight: 600;
          color: var(--primary-text-color);
        }
        .route {
          color: ${this._config.route_color};
          font-weight: 800;
          font-size: ${this._config.route_size};
          line-height: 1.15;
        }
        .description {
          color: ${this._config.description_color};
          font-weight: 600;
          font-size: 1em;
          line-height: 1.25;
          margin-top: 2px;
        }
        .stop {
          color: var(--secondary-text-color);
          font-size: 0.9em;
          margin-top: 2px;
        }
        .meta {
          color: ${this._config.meta_color};
          font-size: 1em;
          margin-top: 3px;
        }
        .meta-strong {
          color: var(--primary-text-color);
          font-weight: 700;
        }
        hr {
          border: none;
          border-top: 2px solid ${this._config.divider_color};
          margin: 10px 20px;
        }
        .empty {
          color: var(--secondary-text-color);
          font-size: 0.95em;
        }
      </style>
      <div class="card">
        ${this._config.title ? `<div class="title">${this._escape(this._config.title)}</div>` : ""}
        ${itemsHtml}
      </div>
    `;
  }

  _buildRouteLabelMap() {
    const map = new Map();
    const states = this._hass.states;

    for (const entityId of this._config.route_entities) {
      const state = states[entityId];
      if (!state || state.state === "unavailable" || state.state === "unknown") {
        continue;
      }

      const rsn = String(state.attributes.route_short_name || "").trim();
      if (!rsn) {
        continue;
      }

      const d0 = state.attributes.direction_0_label || null;
      const d1 = state.attributes.direction_1_label || null;
      const d0Dest = state.attributes.direction_0_destination || null;
      const d1Dest = state.attributes.direction_1_destination || null;

      map.set(`${rsn}|0`, { label: d0, destination: d0Dest });
      map.set(`${rsn}|1`, { label: d1, destination: d1Dest });
    }

    return map;
  }

  _buildRows(routeLabelMap) {
    const rows = [];
    const stopFilter = this._config.stop_filter;
    const states = this._hass.states;

    for (const boardEntity of this._config.entities) {
      const state = states[boardEntity];
      if (!state || state.state === "unavailable" || state.state === "unknown") {
        continue;
      }

      const departures = Array.isArray(state.attributes.departures)
        ? state.attributes.departures
        : [];

      for (const dep of departures) {
        const stopName = String(dep.stop_name || "");
        if (stopFilter && !stopName.toLowerCase().includes(stopFilter)) {
          continue;
        }

        const scheduledRaw =
          String(dep.scheduled_departure_time || dep.departure_time || "")
            .replace("Scheduled:", "")
            .trim();
        const parsed = this._parseTime(scheduledRaw);
        if (!parsed) {
          continue;
        }

        const now = new Date();
        const nowSec = now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds();
        let etaSec = parsed.seconds - nowSec;
        if (etaSec < 0) {
          etaSec += 86400;
        }

        const route = String(dep.route_short_name || "?");
        const directionId = Number.isInteger(dep.direction_id)
          ? dep.direction_id
          : parseInt(dep.direction_id || "0", 10) || 0;

        const mapped = routeLabelMap.get(`${route}|${directionId}`);
        let description = mapped?.label || dep.direction_label || dep.destination || "Unknown destination";

        if (mapped?.destination && dep.destination) {
          const rowDest = String(dep.destination).toLowerCase();
          const mappedDest = String(mapped.destination).toLowerCase();
          if (rowDest && mappedDest && !mappedDest.includes(rowDest) && !rowDest.includes(mappedDest)) {
            // Keep mapped label; destination mismatch is tolerated.
            description = mapped.label || description;
          }
        }

        rows.push({
          route,
          direction_id: directionId,
          description: String(description),
          stop_name: stopName,
          scheduled_hhmm: `${String(parsed.hour % 24).padStart(2, "0")}:${String(parsed.minute).padStart(2, "0")}`,
          scheduled_sort_seconds: parsed.seconds,
          eta_seconds: etaSec,
          countdown: this._formatCountdown(etaSec),
        });
      }
    }

    return rows;
  }

  _sortRows(rows) {
    if (this._config.sort_by === "eta") {
      return rows.sort((a, b) => a.eta_seconds - b.eta_seconds);
    }
    return rows.sort((a, b) => a.scheduled_sort_seconds - b.scheduled_sort_seconds);
  }

  _parseTime(value) {
    if (!value || typeof value !== "string") {
      return null;
    }
    const parts = value.split(":");
    if (parts.length < 2) {
      return null;
    }
    const hour = parseInt(parts[0], 10);
    const minute = parseInt(parts[1], 10);
    const second = parts.length > 2 ? parseInt(parts[2], 10) : 0;
    if (Number.isNaN(hour) || Number.isNaN(minute) || Number.isNaN(second)) {
      return null;
    }
    return {
      hour,
      minute,
      second,
      seconds: hour * 3600 + minute * 60 + second,
    };
  }

  _formatCountdown(totalSeconds) {
    if (totalSeconds < 3600) {
      const m = Math.floor((totalSeconds % 3600) / 60);
      return `${String(m).padStart(2, "0")}m`;
    }
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    return `${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m`;
  }

  _escape(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
}

customElements.define("metlink-departure-board-card", MetlinkDepartureBoardCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "metlink-departure-board-card",
  name: "Metlink Departure Board Card",
  description: "Configurable departures board for Metlink sensors",
});
