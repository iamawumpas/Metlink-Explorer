"""Data update coordinator for Metlink Explorer."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MetlinkApiClient, MetlinkApiError
from .const import CONF_API_KEY, CONF_ROUTE_ID, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class MetlinkDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Metlink API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.api_client = MetlinkApiClient(hass, entry.data[CONF_API_KEY])
        self.route_id = entry.data[CONF_ROUTE_ID]
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # Get route information
            route_data = await self.api_client.get_route_by_id(self.route_id)
            if not route_data:
                raise UpdateFailed(f"Route {self.route_id} not found")
            
            # Get real-time data
            trip_updates = await self.api_client.get_trip_updates()
            vehicle_positions = await self.api_client.get_vehicle_positions()
            service_alerts = await self.api_client.get_service_alerts()
            
            # Filter data for this route
            route_trip_updates = [
                update for update in trip_updates 
                if update.get("trip", {}).get("route_id") == self.route_id
            ]
            
            route_vehicle_positions = [
                position for position in vehicle_positions 
                if position.get("trip", {}).get("route_id") == self.route_id
            ]
            
            route_service_alerts = [
                alert for alert in service_alerts 
                if any(
                    entity.get("route_id") == self.route_id 
                    for entity in alert.get("informed_entity", [])
                )
            ]
            
            return {
                "route_data": route_data,
                "trip_updates": route_trip_updates,
                "vehicle_positions": route_vehicle_positions,
                "service_alerts": route_service_alerts,
                "last_updated": self.last_update_success,
            }
            
        except MetlinkApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err