"""The Metlink Explorer integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import MetlinkDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Metlink Explorer from a config entry."""
    _LOGGER.debug("Setting up Metlink Explorer entry: %s", entry.entry_id)
    
    # Initialize the data update coordinator
    coordinator = MetlinkDataUpdateCoordinator(hass, entry)
    
    # Fetch initial data to ensure the API key works
    await coordinator.async_config_entry_first_refresh()
    
    # Store coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Metlink Explorer entry: %s", entry.entry_id)
    
    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Remove coordinator from hass.data
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Clean up domain data if no entries left
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    
    return unload_ok