import { LitElement, html, css } from "https://unpkg.com/lit-element/lit-element.js?module";

class MetlinkExplorerTileCard extends LitElement {
  static get properties() {
    return {
      hass: {},
      _config: {},
    };
  }

  static get styles() {
    return css`
      ha-card {
        padding: 16px;
      }
      .container {
        display: flex;
        align-items: center;
      }
      ha-icon {
        margin-right: 16px;
      }
      .attributes div {
        margin-bottom: 2px;
      }
    `;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Entity is required");
    }
    this._config = config;
  }

  set hass(hass) {
    this._hass = hass;
    this.requestUpdate();
  }

  render() {
    if (!this._hass || !this._config) return html``;
    const entity = this._hass.states[this._config.entity];
    if (!entity) return html`<ha-card>Entity not found: ${this._config.entity}</ha-card>`;

    const icon = this._config.icon || "mdi:bus";
    const attributes = this._config.attributes || [];

    return html`
      <ha-card>
        <div class="container">
          <ha-icon .icon="${icon}"></ha-icon>
          <div>
            <div style="font-weight: bold;">${entity.attributes.friendly_name || this._config.entity}</div>
            <div>State: ${entity.state}</div>
            <div class="attributes">
              ${attributes.map(attr => html`
                <div><b>${attr}:</b> ${entity.attributes[attr]}</div>
              `)}
            </div>
          </div>
        </div>
      </ha-card>
    `;
  }

  getCardSize() {
    return 1;
  }

  static getConfigElement() {
    return document.createElement("metlink-explorer-tile-card-editor");
  }
}

class MetlinkExplorerTileCardEditor extends LitElement {
  static get properties() {
    return {
      hass: {},
      _config: {},
    };
  }

  setConfig(config) {
    this._config = { ...config };
  }

  set hass(hass) {
    this._hass = hass;
    this.requestUpdate();
  }

  render() {
    if (!this._hass) return html``;
    const entities = Object.keys(this._hass.states).filter(e => e.startsWith("sensor."));
    const icon = this._config.icon || "mdi:bus";
    const attributes = this._config.attributes || [];
    const selectedEntity = this._config.entity || "";

    // Get attributes for the selected entity
    const entityAttrs = selectedEntity && this._hass.states[selectedEntity]
      ? Object.keys(this._hass.states[selectedEntity].attributes)
      : [];

    return html`
      <div>
        <label>Entity:</label>
        <select @change="${e => this._updateConfig('entity', e.target.value)}">
          <option value="">Select entity</option>
          ${entities.map(e => html`
            <option value="${e}" ?selected=${e === selectedEntity}>${e}</option>
          `)}
        </select>
      </div>
      <div>
        <label>Icon:</label>
        <input type="text" .value="${icon}" @input="${e => this._updateConfig('icon', e.target.value)}" placeholder="mdi:bus" />
      </div>
      <div>
        <label>Attributes to show:</label>
        <select multiple @change="${e => this._updateAttributes(e)}" style="min-width: 200px;">
          ${entityAttrs.map(attr => html`
            <option value="${attr}" ?selected=${attributes.includes(attr)}>${attr}</option>
          `)}
        </select>
      </div>
    `;
  }

  _updateConfig(key, value) {
    this._config = { ...this._config, [key]: value };
    this._fireConfigChanged();
  }

  _updateAttributes(e) {
    const selected = Array.from(e.target.selectedOptions).map(opt => opt.value);
    this._config = { ...this._config, attributes: selected };
    this._fireConfigChanged();
  }

  _fireConfigChanged() {
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config } }));
  }
}

customElements.define('metlink-explorer-tile-card', MetlinkExplorerTileCard);
customElements.define('metlink-explorer-tile-card-editor', MetlinkExplorerTileCardEditor);