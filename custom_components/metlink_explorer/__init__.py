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
    _LOGGER.info("🔧 " + "=" * 50)
    _LOGGER.info("🔧 INITIALIZING Metlink Explorer Integration")
    _LOGGER.info(f"🔧 Entry ID: {entry.entry_id}")
    _LOGGER.info("🔧 " + "=" * 50)
    
    try:
        # Initialize the data update coordinator
        _LOGGER.info("⚙️ Step 1/4: Creating data update coordinator...")
        coordinator = MetlinkDataUpdateCoordinator(hass, entry)
        _LOGGER.info("✅ Coordinator created successfully")
        
        # Fetch initial data to ensure the API key works
        _LOGGER.info("📡 Step 2/4: Performing initial data refresh...")
        _LOGGER.info("   ⏳ This may take 10-30 seconds depending on API response time...")
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("✅ Initial data refresh completed successfully")
        
        # Store coordinator in hass.data
        _LOGGER.info("💾 Step 3/4: Storing coordinator in Home Assistant...")
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = coordinator
        _LOGGER.info("✅ Coordinator stored successfully")
        
        # Setup platforms
        _LOGGER.info(f"🏗️ Step 4/4: Setting up platforms: {PLATFORMS}")
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
        _LOGGER.info("🔧 " + "=" * 50)
        _LOGGER.info("🎉 INTEGRATION SETUP COMPLETED!")
        _LOGGER.info("🔧 " + "=" * 50)
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