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

class MetlinkExplorerEditor extends LitElement {
  static get properties() {
    return { hass: {}, _config: {} };
  }

  setConfig(config) {
    this._config = {
      train_entities: [],
      bus_entities: [],
      ferry_entities: [],
      train_live_entities: [],
      bus_live_entities: [],
      ferry_live_entities: [],
      ...config
    };
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
      style: 'solid' 
    }];
    this._updateConfig({ [key]: newEntities });
  }

  _handleEntryChange(type, index, field, value) {
    const key = `${type}_entities`;
    const newEntities = this._config[key].map((item, i) => 
      i === index ? { ...item, [field]: value } : item
    );
    this._updateConfig({ [key]: newEntities });
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

  _addLiveEntity(type) {
    const key = `${type}_live_entities`;
    const randomColor = RANDOM_COLORS[Math.floor(Math.random() * RANDOM_COLORS.length)];
    const newEntities = [...(this._config[key] || []), {
      entity: '',
      color: randomColor,
      size: 7,
      show_label: true
    }];
    this._updateConfig({ [key]: newEntities });
  }

  _handleLiveEntryChange(type, index, field, value) {
    const key = `${type}_live_entities`;
    const newEntities = (this._config[key] || []).map((item, i) =>
      i === index ? { ...item, [field]: value } : item
    );
    this._updateConfig({ [key]: newEntities });
  }

  _moveLiveEntity(type, index, direction) {
    const key = `${type}_live_entities`;
    const newEntities = [...(this._config[key] || [])];
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= newEntities.length) return;
    [newEntities[index], newEntities[newIndex]] = [newEntities[newIndex], newEntities[index]];
    this._updateConfig({ [key]: newEntities });
  }

  _removeLiveEntity(type, index) {
    const key = `${type}_live_entities`;
    const newEntities = (this._config[key] || []).filter((_, i) => i !== index);
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
        ${this._renderSection('train', 'Train Routes', ['train', 'geometry'])}
        ${this._renderSection('bus', 'Bus Routes', ['bus', 'geometry'])}
        ${this._renderSection('ferry', 'Ferry Routes', ['ferry', 'geometry'])}
        ${this._renderLiveSection('train', 'Live Trains', ['train'])}
        ${this._renderLiveSection('bus', 'Live Buses', ['bus'])}
        ${this._renderLiveSection('ferry', 'Live Ferries', ['ferry'])}
      </div>
    `;
  }

  _renderSection(type, title, filters) {
    const entities = this._config[`${type}_entities`] || [];
    const allSelected = [
        ...(this._config.train_entities || []),
        ...(this._config.bus_entities || []),
        ...(this._config.ferry_entities || [])
    ].map(e => e.entity).filter(e => e !== '');

    return html`
      <div class="section">
        <div class="section-header">${title}</div>
        <div class="entity-list">
          ${entities.map((entry, idx) => {
            const filteredEntities = Object.keys(this.hass.states).filter(eid => {
                const stateObj = this.hass.states[eid];
                const entityIdLower = eid.toLowerCase();
                const friendlyNameLower = (stateObj.attributes.friendly_name || "").toLowerCase();
                const matchesFilter = filters.every(f => entityIdLower.includes(f.toLowerCase()) || friendlyNameLower.includes(f.toLowerCase()));
                const isNotSelected = !allSelected.includes(eid) || eid === entry.entity;
                return eid.startsWith("sensor.") && matchesFilter && isNotSelected;
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

  _renderLiveSection(type, title, filters) {
    const entities = this._config[`${type}_live_entities`] || [];
    const allSelected = [
      ...(this._config.train_live_entities || []),
      ...(this._config.bus_live_entities || []),
      ...(this._config.ferry_live_entities || [])
    ].map(e => e.entity).filter(e => e !== '');

    return html`
      <div class="section">
        <div class="section-header">${title}</div>
        <div class="entity-list">
          ${entities.map((entry, idx) => {
            const filteredEntities = Object.keys(this.hass.states).filter(eid => {
              if (!eid.startsWith("device_tracker.")) return false;
              const stateObj = this.hass.states[eid];
              const entityIdLower = eid.toLowerCase();
              const friendlyNameLower = (stateObj.attributes.friendly_name || "").toLowerCase();
              const routeLower = String(stateObj.attributes.route_id || "").toLowerCase();
              const matchesFilter = filters.some(f =>
                entityIdLower.includes(f.toLowerCase())
                || friendlyNameLower.includes(f.toLowerCase())
                || routeLower.includes(f.toLowerCase())
              );
              const isNotSelected = !allSelected.includes(eid) || eid === entry.entity;
              return matchesFilter && isNotSelected;
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
                    @value-changed=${(e) => this._handleLiveEntryChange(type, idx, 'entity', e.detail.value)}
                  ></ha-selector>
                  <div class="controls">
                    <ha-icon icon="mdi:arrow-up" @click=${() => this._moveLiveEntity(type, idx, -1)}></ha-icon>
                    <ha-icon icon="mdi:arrow-down" @click=${() => this._moveLiveEntity(type, idx, 1)}></ha-icon>
                    <ha-icon icon="mdi:delete" @click=${() => this._removeLiveEntity(type, idx)}></ha-icon>
                  </div>
                </div>
                <div class="row-styling">
                  <div class="style-item">
                    <label>Marker Color</label>
                    <input type="color" .value=${entry.color || '#ffa500'} @input=${(e) => this._handleLiveEntryChange(type, idx, 'color', e.target.value)}>
                  </div>
                  <div class="style-item">
                    <label>Marker Size (${entry.size || 7}px)</label>
                    <input type="range" min="4" max="16" .value=${entry.size || 7} @input=${(e) => this._handleLiveEntryChange(type, idx, 'size', parseInt(e.target.value))}>
                  </div>
                  <div class="style-item">
                    <label>Show Label</label>
                    <input type="checkbox" .checked=${entry.show_label !== false} @change=${(e) => this._handleLiveEntryChange(type, idx, 'show_label', e.target.checked)}>
                  </div>
                </div>
              </div>
            `;
          })}
        </div>
        <mwc-button @click=${() => this._addLiveEntity(type)}>
          <ha-icon icon="mdi:plus"></ha-icon> Add ${type} Vehicle
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
    `;
  }
}
customElements.define("metlink-explorer-map-editor", MetlinkExplorerEditor);
