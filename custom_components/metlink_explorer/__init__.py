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
    _LOGGER.info("Setting up Metlink Explorer entry: %s", entry.entry_id)
    
    try:
        # Initialize the data update coordinator
        coordinator = MetlinkDataUpdateCoordinator(hass, entry)
        
        # Fetch initial data to ensure the API key works
        _LOGGER.debug("Starting initial data refresh for coordinator...")
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Initial data refresh completed successfully")
        
        # Store coordinator in hass.data
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = coordinator
        
        # Setup platforms
        _LOGGER.debug("Setting up platforms: %s", PLATFORMS)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _LOGGER.info("Metlink Explorer setup completed successfully")
        
        return True
        
    except Exception as err:
        _LOGGER.error("Error setting up Metlink Explorer: %s", err, exc_info=True)
        return False


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