from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN

async def async_setup_entry(hass, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True

async def async_unload_entry(hass, entry: ConfigEntry):
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")