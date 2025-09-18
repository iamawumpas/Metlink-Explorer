from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .api import MetlinkApiClient

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    api_key = entry.data["api_key"]
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = MetlinkApiClient(api_key)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    client = hass.data[DOMAIN].pop(entry.entry_id)
    await client.close()
    return True