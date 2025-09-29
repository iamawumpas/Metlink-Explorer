"""Sensor platform for Metlink Explorer."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MetlinkApiClient, MetlinkApiError
from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_TRANSPORTATION_TYPE,
    CONF_ROUTE_ID,
    CONF_ROUTE_SHORT_NAME,
    CONF_ROUTE_LONG_NAME,
    CONF_ROUTE_DESC,
    TRANSPORTATION_TYPES,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class MetlinkDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: MetlinkApiClient,
        route_id: str,
    ) -> None:
        """Initialize."""
        self.api_client = api_client
        self.route_id = route_id
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # Fetch real-time data for this route
            trips = await self.api_client.get_trips_for_route(self.route_id)
            vehicle_positions = await self.api_client.get_vehicle_positions()
            trip_updates = await self.api_client.get_trip_updates()
            
            return {
                "trips": trips,
                "vehicle_positions": vehicle_positions,
                "trip_updates": trip_updates,
            }
        except MetlinkApiError as exc:
            raise UpdateFailed(f"Error communicating with API: {exc}") from exc


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    api_key = config_entry.data[CONF_API_KEY]
    transportation_type = config_entry.data[CONF_TRANSPORTATION_TYPE]
    route_id = config_entry.data[CONF_ROUTE_ID]
    route_short_name = config_entry.data[CONF_ROUTE_SHORT_NAME]
    route_long_name = config_entry.data[CONF_ROUTE_LONG_NAME]
    route_desc = config_entry.data.get(CONF_ROUTE_DESC, "")  # Direction 1 description

    session = async_get_clientsession(hass)
    api_client = MetlinkApiClient(api_key, session)

    coordinator = MetlinkDataUpdateCoordinator(hass, api_client, route_id)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    # Create sensor entities for both directions using the new naming schema
    entities = []
    transportation_name = TRANSPORTATION_TYPES.get(transportation_type, "Unknown")
    
    # Direction 0: route_short_name :: route_long_name  
    entities.append(
        MetlinkSensor(
            coordinator,
            config_entry,
            route_id,
            route_short_name,
            route_long_name,  # Direction 0 description
            transportation_name,
            0,  # Direction 0
        )
    )
    
    # Direction 1: route_short_name :: route_desc (if available)
    if route_desc:  # Only create Direction 1 if we have route_desc
        entities.append(
            MetlinkSensor(
                coordinator,
                config_entry,
                route_id,
                route_short_name,
                route_desc,  # Direction 1 description
                transportation_name,
                1,  # Direction 1
            )
        )

    async_add_entities(entities)


class MetlinkSensor(CoordinatorEntity, SensorEntity):
    """Metlink sensor entity."""

    def __init__(
        self,
        coordinator: MetlinkDataUpdateCoordinator,
        config_entry: ConfigEntry,
        route_id: str,
        route_short_name: str,
        route_description: str,  # Will be route_long_name for dir 0, route_desc for dir 1
        transportation_name: str,
        direction: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self._route_id = route_id
        self._route_short_name = route_short_name
        self._route_description = route_description
        self._transportation_name = transportation_name
        self._direction = direction
        self._config_entry = config_entry

        # Use the new naming schema: route_short_name :: route_description
        self._attr_name = f"{route_short_name} :: {route_description}"
        self._attr_unique_id = f"{DOMAIN}_{route_id}_{direction}"
        
        # Add proper sensor properties for Home Assistant recognition
        self._attr_native_unit_of_measurement = "trips"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = True
        
        # Set device info to group sensors properly
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{route_id}")},
            "name": f"{transportation_name} Route {route_short_name}",
            "manufacturer": "Metlink",
            "model": transportation_name,
            "sw_version": "1.0",
        }

    @property
    def native_value(self) -> int | None:
        """Return the native value of the sensor."""
        if not self.coordinator.data:
            return None
        
        # Count active trips for this direction
        trips = self.coordinator.data.get("trips", [])
        active_trips = [
            trip for trip in trips 
            if trip.get("direction_id") == self._direction
        ]
        
        return len(active_trips)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}

        trips = self.coordinator.data.get("trips", [])
        vehicle_positions = self.coordinator.data.get("vehicle_positions", [])
        trip_updates = self.coordinator.data.get("trip_updates", [])

        # Filter data for this direction
        direction_trips = [
            trip for trip in trips 
            if trip.get("direction_id") == self._direction
        ]

        return {
            "route_id": self._route_id,
            "route_short_name": self._route_short_name,
            "route_description": self._route_description,
            "transportation_type": self._transportation_name,
            "direction": self._direction,
            "trip_count": len(direction_trips),
            "last_updated": self.coordinator.last_update_success_time,
        }

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        transportation_icons = {
            "Train": "mdi:train",
            "Bus": "mdi:bus",
            "Ferry": "mdi:ferry",
            "Cable Car": "mdi:cable-car",
            "School Bus": "mdi:bus-school",
        }
        return transportation_icons.get(self._transportation_name, "mdi:transit-connection-variant")