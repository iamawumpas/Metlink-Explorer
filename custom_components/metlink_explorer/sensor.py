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
            _LOGGER.debug("Starting data update for route %s direction %s", self.route_id, self.direction_id)
            
            # Fetch basic real-time data first (these are essential)
            trips = await self.api_client.get_trips_for_route(self.route_id)
            _LOGGER.debug("Fetched %d trips for route %s", len(trips), self.route_id)
            
            vehicle_positions = await self.api_client.get_vehicle_positions()
            _LOGGER.debug("Fetched %d vehicle positions", len(vehicle_positions))
            
            trip_updates = await self.api_client.get_trip_updates()
            _LOGGER.debug("Fetched %d trip updates", len(trip_updates))
            
            # Try to fetch route timeline for card display
            route_timeline_data = {"stops": [], "error": None}
            try:
                _LOGGER.info("Fetching route timeline for card display: route %s direction %s", 
                            self.route_id, self.direction_id)
                route_timeline_data = await self.api_client.get_route_timeline_for_card(
                    self.route_id, self.direction_id
                )
                _LOGGER.info("Route timeline data: %d stops, error: %s", 
                           len(route_timeline_data.get("stops", [])),
                           route_timeline_data.get("error", "None"))
                
            except Exception as exc:
                _LOGGER.error("Failed to fetch route timeline (non-critical): %s", exc, exc_info=True)
                route_timeline_data = {"stops": [], "error": str(exc)}
            
            # Try to fetch route stop predictions (this is the original feature, now secondary)
            route_stop_data = {"stops": {}, "destination": None, "stop_count": 0}
            try:
                _LOGGER.debug("Fetching route stop predictions for route %s direction %s", 
                             self.route_id, self.direction_id)
                route_stop_data = await self.api_client.get_route_stop_predictions(
                    self.route_id, self.direction_id
                )
                _LOGGER.info("Route stop data: %d stops, destination: %s", 
                             route_stop_data.get("stop_count", 0),
                             route_stop_data.get("destination", {}).get("stop_name", "None") 
                             if route_stop_data.get("destination") else "None")
                
                # Additional debugging for empty results
                if route_stop_data.get("stop_count", 0) == 0:
                    _LOGGER.warning("No stops found in route stop data - investigating...")
                    _LOGGER.debug("Full route_stop_data structure: %s", route_stop_data)
                    
            except Exception as exc:
                _LOGGER.error("Failed to fetch route stop predictions (non-critical): %s", exc, exc_info=True)
                # Continue with basic functionality even if stop patterns fail
            
            return {
                "trips": trips,
                "vehicle_positions": vehicle_positions,
                "trip_updates": trip_updates,
                "route_stops": route_stop_data,  # Will be empty dict if failed
                "route_timeline": route_timeline_data,  # NEW: Card-friendly timeline data
            }
        except MetlinkApiError as exc:
            _LOGGER.error("Error communicating with API: %s", exc)
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
    
    # Direction 0: route_short_name :: route_desc (reversed per user request)
    coordinator_0 = MetlinkDataUpdateCoordinator(hass, api_client, route_id, 0)
    await coordinator_0.async_config_entry_first_refresh()
    
    entities.append(
        MetlinkSensor(
            coordinator_0,
            config_entry,
            route_id,
            route_short_name,
            # Prefer route_desc for direction 0; fall back to long name if missing
            route_desc if route_desc else route_long_name,
            transportation_name,
            0,
        )
    )
    
    # Direction 1: route_short_name :: route_long_name (always create)
    coordinator_1 = MetlinkDataUpdateCoordinator(hass, api_client, route_id, 1)
    await coordinator_1.async_config_entry_first_refresh()
    
    entities.append(
        MetlinkSensor(
            coordinator_1,
            config_entry,
            route_id,
            route_short_name,
            route_long_name,
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
        route_timeline = self.coordinator.data.get("route_timeline", {})

        # Filter data for this direction
        direction_trips = [
            trip for trip in trips 
            if trip.get("direction_id") == self._direction
        ]

        # NEW: Process stop predictions with improved error handling
        next_departures = []
        all_stops = []
        destination_stop = route_stops.get("destination")
        
        _LOGGER.debug("Processing route stops data for route %s direction %s: %s stops available", 
                     self._route_id, self._direction,
                     len(route_stops.get("stops", {})) if route_stops else 0)
        
        # NEW: Process timeline data for card display
        timeline_stops = route_timeline.get("stops", [])
        timeline_error = route_timeline.get("error")
        
        _LOGGER.debug("Processing route timeline for route %s direction %s: %d stops, error: %s", 
                     self._route_id, self._direction, len(timeline_stops), timeline_error or "None")
        
        if route_stops and route_stops.get("stops"):
            stops_data = route_stops["stops"]
            
            # Build stop list with next departures
            for stop_id, stop_data in stops_data.items():
                if not isinstance(stop_data, dict) or "stop_info" not in stop_data:
                    _LOGGER.warning("Invalid stop data structure for stop %s", stop_id)
                    continue
                    
                stop_info = stop_data["stop_info"]
                predictions = stop_data.get("predictions", [])
                
                # Ensure predictions is a list
                if not isinstance(predictions, list):
                    predictions = []
                
                # Get scheduled departure time from GTFS data as fallback
                scheduled_departure = stop_info.get("departure_time")
                next_departure_time = None
                is_real_time = False
                
                if predictions:
                    # Use real-time prediction if available
                    latest_pred = predictions[0]  # Should be sorted by time
                    next_departure_time = latest_pred.get("departure_time") or latest_pred.get("expected_departure_time")
                    is_real_time = latest_pred.get("is_real_time", False)
                    delay = latest_pred.get("delay_seconds", 0)
                    
                    if delay != 0:
                        delay_min = delay // 60
                        delay_text = f" ({'+' if delay > 0 else ''}{delay_min}min)" if delay_min != 0 else ""
                        next_departure_time = f"{next_departure_time}{delay_text}"
                    
                    _LOGGER.debug("Using real-time prediction for stop %s: %s (delay: %ds)", 
                                 stop_id, next_departure_time, delay)
                elif scheduled_departure:
                    # Fall back to scheduled time - clearly marked as not current
                    next_departure_time = f"Scheduled: {scheduled_departure}"
                    is_real_time = False
                    _LOGGER.debug("Using scheduled time for stop %s: %s", stop_id, scheduled_departure)
                
                stop_entry = {
                    "stop_id": stop_id,
                    "stop_name": stop_info.get("stop_name", "Unknown Stop"),
                    "stop_sequence": stop_info.get("stop_sequence", 0),
                    "next_departure": next_departure_time,
                    "scheduled_departure": scheduled_departure,
                    "prediction_count": len(predictions),
                    "has_real_time": is_real_time,
                    "delay_seconds": predictions[0].get("delay_seconds", 0) if predictions else 0,
                    # Include more stop details
                    "stop_lat": stop_info.get("stop_lat"),
                    "stop_lon": stop_info.get("stop_lon"),
                }
                all_stops.append(stop_entry)
                
                # Collect next departures for quick access
                if predictions:
                    for pred in predictions[:2]:  # Next 2 departures per stop
                        departure_time = pred.get("departure_time") or pred.get("expected_departure_time")
                        if isinstance(pred, dict) and departure_time:
                            delay = pred.get("delay_seconds", 0)
                            display_time = departure_time
                            
                            # Add delay information if significant
                            if delay != 0:
                                delay_min = delay // 60
                                if delay_min != 0:
                                    display_time = f"{departure_time} ({'+' if delay > 0 else ''}{delay_min}min)"
                            
                            next_departures.append({
                                "stop_name": stop_info.get("stop_name", "Unknown Stop"),
                                "stop_id": stop_id,
                                "departure_time": display_time,
                                "raw_departure_time": departure_time,
                                "delay_seconds": delay,
                                "arrival_time": pred.get("arrival_time") or pred.get("expected_arrival_time"),
                                "is_real_time": pred.get("is_real_time", False),
                                "vehicle_id": pred.get("vehicle_id"),
                                "trip_id": pred.get("trip_id"),
                                "timestamp": pred.get("timestamp"),
                            })
                elif scheduled_departure:
                    # Include scheduled departure as fallback with clear indication
                    next_departures.append({
                        "stop_name": stop_info.get("stop_name", "Unknown Stop"),
                        "stop_id": stop_id,
                        "departure_time": f"Scheduled: {scheduled_departure}",
                        "raw_departure_time": scheduled_departure,
                        "delay_seconds": 0,
                        "arrival_time": stop_info.get("arrival_time"),
                        "is_real_time": False,
                        "note": "GTFS scheduled time - not current real-time data"
                    })
            
            # Sort stops by sequence
            all_stops.sort(key=lambda x: x.get("stop_sequence", 999))
            
            # Sort next departures by time (handle various time formats)
            valid_departures = []
            for d in next_departures:
                if d.get("departure_time"):
                    try:
                        # Use raw_departure_time for sorting if available, otherwise departure_time
                        sort_time = d.get("raw_departure_time") or d.get("departure_time", "")
                        # Remove "Scheduled: " prefix for sorting
                        if sort_time.startswith("Scheduled: "):
                            sort_time = sort_time[11:]
                        d["_sort_time"] = sort_time
                        valid_departures.append(d)
                    except (ValueError, TypeError):
                        _LOGGER.debug("Could not parse departure time: %s", d.get("departure_time"))
            
            # Sort by time - real-time predictions first, then by time
            def sort_key(x):
                is_rt = x.get("is_real_time", False)
                time_str = x.get("_sort_time", "")
                return (not is_rt, time_str)  # Real-time first (False sorts before True)
            
            # Sort and limit to next 10 departures
            next_departures = sorted(valid_departures, key=sort_key)[:10]
            
            # Clean up sort key
            for d in next_departures:
                d.pop("_sort_time", None)
            
        _LOGGER.debug("Processed %d stops and %d next departures for route %s direction %s", 
                     len(all_stops), len(next_departures), self._route_id, self._direction)

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
            "stops_with_predictions": len([s for s in all_stops if s.get("has_real_time", False)]),
            "stops_with_scheduled": len([s for s in all_stops if s.get("scheduled_departure")]),
            "next_departures": next_departures,  # Next departures across route
            "all_stops": all_stops,  # Complete stop list with predictions
            
            # NEW: Card-friendly timeline data
            "timeline_stops": timeline_stops,  # Ordered stops with ETA calculations
            "timeline_error": timeline_error,  # Any error in timeline generation
            "departure_stop": route_timeline.get("departure_stop"),  # First stop
            "destination_stop_timeline": route_timeline.get("destination_stop"),  # Last stop
            "hub_stops": route_timeline.get("hub_stops", []),  # Major interchange stops
            "current_time": route_timeline.get("current_time"),  # Reference time for ETAs
            "timeline_trip_id": route_timeline.get("trip_id"),  # Trip used for timeline
            
            # Enhanced debugging information
            "debug_info": {
                "coordinator_data_keys": list(self.coordinator.data.keys()) if self.coordinator.data else [],
                "route_stops_keys": list(route_stops.keys()) if route_stops else [],
                "stops_data_count": len(route_stops.get("stops", {})) if route_stops else 0,
                "last_update_time": str(self.coordinator.last_update_success_time) if hasattr(self.coordinator, 'last_update_success_time') else "unknown",
                "real_time_stops": len([s for s in all_stops if s.get("has_real_time", False)]),
                "scheduled_only_stops": len([s for s in all_stops if not s.get("has_real_time", False)]),
                "total_predictions": sum(s.get("prediction_count", 0) for s in all_stops),
                "route_info": {
                    "route_id": self._route_id,
                    "route_short_name": self._route_short_name,
                    "direction": self._direction
                }
            }
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