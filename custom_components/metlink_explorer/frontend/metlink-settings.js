/* Shared per-user settings storage for Metlink cards. */
(() => {
  "use strict";
  const settingsCaches = new WeakMap();
  const settingsRequests = new WeakMap();

  const loadAll = (hass) => {
    const connection = hass.connection;
    const cached = settingsCaches.get(connection);
    if (cached) return Promise.resolve(cached);
    const pending = settingsRequests.get(connection);
    if (pending) return pending;
    const request = hass.callWS({ type: "metlink_explorer/get_settings" })
      .then((settings) => {
        if (!settings || typeof settings !== "object" || Array.isArray(settings)) {
          throw new Error("Metlink Explorer returned invalid user settings");
        }
        settingsCaches.set(connection, settings);
        return settings;
      })
      .catch((err) => {
        settingsRequests.delete(connection);
        throw err;
      });
    settingsRequests.set(connection, request);
    return request;
  };

  const save = async (hass, key, value) => {
    await hass.callWS({ type: "metlink_explorer/save_settings", key, value });
    const connection = hass.connection;
    const cached = settingsCaches.get(connection);
    if (cached) cached[key] = value;
    else settingsRequests.get(connection)?.then((settings) => { settings[key] = value; });
  };

  window.MetlinkExplorerSettings = {
    async load(hass, key) {
      const settings = await loadAll(hass);
      if (Object.prototype.hasOwnProperty.call(settings, key)) {
        const saved = settings[key];
        return saved && typeof saved === "object" && !Array.isArray(saved) ? saved : {};
      }

      let raw;
      try {
        raw = localStorage.getItem(key);
      } catch (err) {
        console.error("Metlink Explorer could not read legacy browser settings", err);
        return {};
      }
      if (!raw) return {};

      let saved;
      try {
        saved = JSON.parse(raw);
      } catch (err) {
        console.warn("Metlink Explorer ignored invalid legacy browser settings", err);
        return {};
      }
      if (!saved || typeof saved !== "object" || Array.isArray(saved)) return {};

      await save(hass, key, saved);
      try {
        localStorage.removeItem(key);
      } catch (err) {
        console.error("Metlink Explorer could not remove migrated browser settings", err);
      }
      return saved;
    },
    peek(hass, key) {
      return settingsCaches.get(hass.connection)?.[key];
    },
    save,
  };
})();
