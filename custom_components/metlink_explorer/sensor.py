"""Sensor platform for Metlink Explorer."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ROUTE_ID,
    CONF_ROUTE_LONG_NAME,
    CONF_ROUTE_SHORT_NAME,
    CONF_TRANSPORT_TYPE,
    DOMAIN,
    TRANSPORT_TYPES,
)
from .coordinator import MetlinkDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Metlink Explorer sensor platform."""
    _LOGGER.info(f"Setting up Metlink Explorer sensor platform for entry: {config_entry.entry_id}")
    
    try:
        coordinator: MetlinkDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
        _LOGGER.info(f"Found coordinator: {coordinator}")
        
        # Get config data
        transport_type = config_entry.data[CONF_TRANSPORT_TYPE]
        route_short_name = config_entry.data[CONF_ROUTE_SHORT_NAME]
        route_long_name = config_entry.data[CONF_ROUTE_LONG_NAME]
        
        _LOGGER.info(f"Config data - Type: {transport_type}, Route: {route_short_name}, Name: {route_long_name}")
        
        # Wait for initial data to be available
        if not coordinator.data:
            _LOGGER.warning("No data available from coordinator, waiting for first refresh")
            await coordinator.async_request_refresh()
        
        # Get stop sequences from coordinator data
        route_stops = coordinator.data.get("route_stops", {})
        if not route_stops:
            _LOGGER.error("No route stops data available")
            return
        
        # Create entities for each stop in both directions
        entities = []
        
        for direction_id, stops in route_stops.items():
            direction_name = "Outbound" if direction_id == 0 else "Inbound"
            
            for stop_info in stops:
                stop_id = stop_info.get("stop_id")
                stop_name = stop_info.get("stop_name", "Unknown Stop")
                stop_sequence = stop_info.get("stop_sequence", 0)
                
                if not stop_id:
                    _LOGGER.warning(f"Skipping stop without ID in direction {direction_id}")
                    continue
                
                # Create stop-based entity
                stop_entity = MetlinkStopSensor(
                    coordinator=coordinator,
                    config_entry=config_entry,
                    direction_id=direction_id,
                    direction_name=direction_name,
                    transport_type=transport_type,
                    route_short_name=route_short_name,
                    route_long_name=route_long_name,
                    stop_info=stop_info,
                )
                
                entities.append(stop_entity)
                _LOGGER.debug(f"Created stop entity: {stop_entity.name} (Stop {stop_sequence})")
        
        _LOGGER.info(f"Adding {len(entities)} stop-based entities to Home Assistant")
        async_add_entities(entities, True)
        
    except Exception as e:
        _LOGGER.error(f"Error setting up sensor platform: {e}", exc_info=True)
        raise


class MetlinkStopSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Metlink stop sensor."""

    def __init__(
        self,
        coordinator: MetlinkDataUpdateCoordinator,
        config_entry: ConfigEntry,
        direction_id: int,
        direction_name: str,
        transport_type: int,
        route_short_name: str,
        route_long_name: str,
        stop_info: dict[str, Any],
    ) -> None:
        """Initialize the stop sensor."""
        super().__init__(coordinator)
        
        self._config_entry = config_entry
        self._direction_id = direction_id
        self._direction_name = direction_name
        self._transport_type = transport_type
        self._route_short_name = route_short_name
        self._route_long_name = route_long_name
        self._stop_info = stop_info
        
        # Extract stop details
        self._stop_id = stop_info.get("stop_id")
        self._stop_name = stop_info.get("stop_name", "Unknown Stop")
        self._stop_sequence = stop_info.get("stop_sequence", 0)
        self._stop_code = stop_info.get("stop_code", "")
        
        # Create entity naming following the pattern: 
        # transport_type :: route_number / route_name :: stop_id / stop_description
        transport_type_name = TRANSPORT_TYPES.get(transport_type, "Unknown").lower()
        
        # Entity name for display
        self._attr_name = f"{transport_type_name.title()} :: {route_short_name} / {route_long_name} :: {self._stop_id} / {self._stop_name}"
        
        # Unique ID for internal use
        route_id = config_entry.data.get(CONF_ROUTE_ID, "unknown")
        self._attr_unique_id = f"{DOMAIN}_{route_id}_{direction_id}_{self._stop_id}"
        
        # Device info - group stops by route for better organization
        transport_type_name = TRANSPORT_TYPES.get(transport_type, "Unknown")
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{config_entry.entry_id}_{route_id}")},
            "name": f"{transport_type_name} Route {route_short_name} - {route_long_name}",
            "manufacturer": "Metlink",
            "model": f"{transport_type_name} Route",
            "sw_version": "1.0",
        }

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor (next departure time for this stop)."""
        if not self.coordinator.data:
            return "No data"
            
        # Get departures for this direction
        departure_key = f"direction_{self._direction_id}_departures"
        all_departures = self.coordinator.data.get(departure_key, [])
        
        # Filter departures for this specific stop
        stop_departures = [
            dep for dep in all_departures 
            if dep.get("stop_id") == self._stop_id
        ]
        
        if stop_departures:
            next_departure = stop_departures[0]
            departure_time = next_departure.get("departure_time", "")
            if departure_time:
                return f"Next: {departure_time}"
            else:
                return "Departure scheduled"
        
        return "No upcoming departures"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes for this stop."""
        if not self.coordinator.data:
            return {}
            
        route_data = self.coordinator.data.get("route_data", {})
        trip_updates = self.coordinator.data.get("trip_updates", [])
        vehicle_positions = self.coordinator.data.get("vehicle_positions", [])
        service_alerts = self.coordinator.data.get("service_alerts", [])
        last_updated = self.coordinator.data.get("last_updated")
        
        # Get departures for this specific stop
        departure_key = f"direction_{self._direction_id}_departures"
        all_departures = self.coordinator.data.get(departure_key, [])
        stop_departures = [
            dep for dep in all_departures 
            if dep.get("stop_id") == self._stop_id
        ]
        
        attributes = {
            "stop_id": self._stop_id,
            "stop_name": self._stop_name,
            "stop_code": self._stop_code,
            "stop_sequence": self._stop_sequence,
            "direction_id": self._direction_id,
            "direction_name": self._direction_name,
            "transport_type": TRANSPORT_TYPES.get(self._transport_type, "Unknown"),
            "route_id": route_data.get("route_id"),
            "route_short_name": self._route_short_name,
            "route_long_name": self._route_long_name,
            "route_color": route_data.get("route_color"),
            "route_text_color": route_data.get("route_text_color"),
            "agency_id": route_data.get("agency_id"),
            "last_updated": last_updated.isoformat() if hasattr(last_updated, 'isoformat') else None,
        }
        
        # Add stop location if available
        if self._stop_info.get("stop_lat") is not None:
            attributes["stop_latitude"] = self._stop_info.get("stop_lat")
            attributes["stop_longitude"] = self._stop_info.get("stop_lon")
            attributes["zone_id"] = self._stop_info.get("zone_id", "")
        
        # Add next departures for this stop (up to 10)
        if stop_departures:
            departure_list = []
            for departure in stop_departures[:10]:  # Limit to 10 departures
                departure_info = {
                    "departure_time": departure.get("departure_time", ""),
                    "arrival_time": departure.get("arrival_time", ""),
                    "trip_id": departure.get("trip_id", ""),
                    "pickup_type": departure.get("pickup_type", 0),
                    "drop_off_type": departure.get("drop_off_type", 0),
                }
                departure_list.append(departure_info)
            
            attributes["next_departures"] = departure_list
            attributes["departure_count"] = len(departure_list)
        else:
            attributes["next_departures"] = []
            attributes["departure_count"] = 0
        
        # Add trip and vehicle information for this stop
        stop_trips = []
        stop_vehicles = []
        
        for update in trip_updates:
            trip_update = update.get("trip_update", {})
            trip = trip_update.get("trip", {})
            if trip.get("direction_id") == self._direction_id:
                # Check if this trip stops at our stop
                stop_time_updates = trip_update.get("stop_time_update", [])
                if isinstance(stop_time_updates, list):
                    for stu in stop_time_updates:
                        if stu.get("stop_id") == self._stop_id:
                            stop_trips.append({
                                "trip_id": trip.get("trip_id"),
                                "delay": trip_update.get("delay", 0),
                                "arrival_delay": stu.get("arrival", {}).get("delay", 0),
                                "departure_delay": stu.get("departure", {}).get("delay", 0),
                            })
                            break
        
        for position in vehicle_positions:
            trip = position.get("trip", {})
            if trip.get("direction_id") == self._direction_id and trip.get("trip_id"):
                # If we have trip info for this vehicle and it matches our trips, include it
                vehicle_trip_id = trip.get("trip_id")
                if any(t.get("trip_id") == vehicle_trip_id for t in stop_trips):
                    vehicle_data = position.get("vehicle", {})
                    position_data = position.get("position", {})
                    stop_vehicles.append({
                        "vehicle_id": vehicle_data.get("id"),
                        "trip_id": vehicle_trip_id,
                        "latitude": position_data.get("latitude"),
                        "longitude": position_data.get("longitude"),
                        "bearing": position_data.get("bearing"),
                        "speed": position_data.get("speed"),
                    })
        
        attributes["trips"] = stop_trips
        attributes["vehicles"] = stop_vehicles
        attributes["trip_count"] = len(stop_trips)
        attributes["vehicle_count"] = len(stop_vehicles)
        
        # Add service alerts
        attributes["alerts"] = []
        attributes["alert_count"] = len(service_alerts)
        for alert_entity in service_alerts:
            alert = alert_entity.get("alert", {})
            alert_info = {
                "alert_id": alert_entity.get("id"),
                "cause": alert.get("cause"),
                "effect": alert.get("effect"),
                "severity_level": alert.get("severity_level"),
            }
            
            # Add header and description texts
            header_text = alert.get("header_text", {})
            if header_text and "translation" in header_text:
                translations = header_text["translation"]
                if translations and len(translations) > 0:
                    alert_info["header"] = translations[0].get("text", "")
            
            description_text = alert.get("description_text", {})
            if description_text and "translation" in description_text:
                translations = description_text["translation"]
                if translations and len(translations) > 0:
                    alert_info["description"] = translations[0].get("text", "")
            
            attributes["alerts"].append(alert_info)
        
        return attributes

    @property
    def device_class(self) -> str | None:
        """Return device class for the sensor."""
        return None  # This is a text-based sensor

    @property 
    def icon(self) -> str:
        """Return the icon for the sensor."""
        transport_icons = {
            2: "mdi:train",      # Rail
            3: "mdi:bus",        # Bus
            4: "mdi:ferry",      # Ferry
            5: "mdi:gondola",    # Cable Car
            712: "mdi:school",   # School Services
        }
        return transport_icons.get(self._transport_type, "mdi:transit-connection-variant")
        return transport_icons.get(self._transport_type, "mdi:transit-connection-variant")