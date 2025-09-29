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
        direction_id: int,
    ) -> None:
        """Initialize."""
        self.api_client = api_client
        self.route_id = route_id
        self.direction_id = direction_id
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{route_id}_{direction_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # Fetch basic real-time data
            trips = await self.api_client.get_trips_for_route(self.route_id)
            vehicle_positions = await self.api_client.get_vehicle_positions()
            trip_updates = await self.api_client.get_trip_updates()
            
            # NEW: Fetch route stop predictions
            route_stop_data = await self.api_client.get_route_stop_predictions(
                self.route_id, self.direction_id
            )
            
            return {
                "trips": trips,
                "vehicle_positions": vehicle_positions,
                "trip_updates": trip_updates,
                "route_stops": route_stop_data,  # NEW: Stop pattern and predictions
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
    route_desc = config_entry.data.get(CONF_ROUTE_DESC, "")

    session = async_get_clientsession(hass)
    api_client = MetlinkApiClient(api_key, session)

    # Create separate coordinators for each direction
    entities = []
    transportation_name = TRANSPORTATION_TYPES.get(transportation_type, "Unknown")
    
    # Direction 0: route_short_name :: route_long_name
    coordinator_0 = MetlinkDataUpdateCoordinator(hass, api_client, route_id, 0)
    await coordinator_0.async_config_entry_first_refresh()
    
    entities.append(
        MetlinkSensor(
            coordinator_0,
            config_entry,
            route_id,
            route_short_name,
            route_long_name,
            transportation_name,
            0,
        )
    )
    
    # Direction 1: route_short_name :: route_desc (if available)
    if route_desc:
        coordinator_1 = MetlinkDataUpdateCoordinator(hass, api_client, route_id, 1)
        await coordinator_1.async_config_entry_first_refresh()
        
        entities.append(
            MetlinkSensor(
                coordinator_1,
                config_entry,
                route_id,
                route_short_name,
                route_desc,
                transportation_name,
                1,
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
        route_description: str,
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
        route_stops = self.coordinator.data.get("route_stops", {})

        # Filter data for this direction
        direction_trips = [
            trip for trip in trips 
            if trip.get("direction_id") == self._direction
        ]

        # NEW: Process stop predictions
        next_departures = []
        all_stops = []
        destination_stop = route_stops.get("destination")
        
        if route_stops and route_stops.get("stops"):
            stops_data = route_stops["stops"]
            
            # Build stop list with next departures
            for stop_id, stop_data in stops_data.items():
                stop_info = stop_data["stop_info"]
                predictions = stop_data["predictions"]
                
                stop_entry = {
                    "stop_id": stop_id,
                    "stop_name": stop_info.get("stop_name", "Unknown Stop"),
                    "stop_sequence": stop_info.get("stop_sequence", 0),
                    "next_departure": predictions[0].get("departure_time") if predictions else None,
                    "prediction_count": len(predictions)
                }
                all_stops.append(stop_entry)
                
                # Collect next departures for quick access
                if predictions:
                    next_departures.extend([
                        {
                            "stop_name": stop_info.get("stop_name"),
                            "departure_time": pred.get("departure_time"),
                            "delay_seconds": pred.get("delay_seconds", 0)
                        }
                        for pred in predictions[:2]  # Next 2 departures per stop
                    ])
            
            # Sort stops by sequence
            all_stops.sort(key=lambda x: x["stop_sequence"])
            
            # Sort next departures by time
            next_departures = sorted(
                [d for d in next_departures if d["departure_time"]], 
                key=lambda x: x["departure_time"]
            )[:10]  # Next 10 departures across all stops

        return {
            "route_id": self._route_id,
            "route_short_name": self._route_short_name,
            "route_description": self._route_description,
            "transportation_type": self._transportation_name,
            "direction": self._direction,
            "trip_count": len(direction_trips),
            "last_updated": self.coordinator.last_update_success,
            
            # NEW: Stop and prediction data
            "destination_stop": destination_stop.get("stop_name") if destination_stop else None,
            "destination_stop_id": destination_stop.get("stop_id") if destination_stop else None,
            "total_stops": len(all_stops),
            "stops_with_predictions": len([s for s in all_stops if s["next_departure"]]),
            "next_departures": next_departures,  # Next 10 departures across route
            "all_stops": all_stops,  # Complete stop list with predictions
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