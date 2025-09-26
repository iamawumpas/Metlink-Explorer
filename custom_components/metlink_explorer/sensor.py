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
    coordinator: MetlinkDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    # Get config data
    transport_type = config_entry.data[CONF_TRANSPORT_TYPE]
    route_short_name = config_entry.data[CONF_ROUTE_SHORT_NAME]
    route_long_name = config_entry.data[CONF_ROUTE_LONG_NAME]
    
    # Create sensors for both directions
    entities = []
    
    # Direction 0 (normal direction)
    direction_0_entity = MetlinkRouteSensor(
        coordinator,
        config_entry,
        direction=0,
        transport_type=transport_type,
        route_short_name=route_short_name,
        route_long_name=route_long_name,
    )
    entities.append(direction_0_entity)
    _LOGGER.info(f"Created direction 0 entity: {direction_0_entity.name} (ID: {direction_0_entity.unique_id})")
    
    # Direction 1 (reverse direction)
    # Reverse the route name by splitting on ' - ' and reversing
    route_parts = route_long_name.split(" - ")
    reversed_route_name = " - ".join(reversed(route_parts))
    
    direction_1_entity = MetlinkRouteSensor(
        coordinator,
        config_entry,
        direction=1,
        transport_type=transport_type,
        route_short_name=route_short_name,
        route_long_name=reversed_route_name,
    )
    entities.append(direction_1_entity)
    _LOGGER.info(f"Created direction 1 entity: {direction_1_entity.name} (ID: {direction_1_entity.unique_id})")
    
    _LOGGER.info(f"Adding {len(entities)} entities to Home Assistant")
    async_add_entities(entities, True)


class MetlinkRouteSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Metlink route sensor."""

    def __init__(
        self,
        coordinator: MetlinkDataUpdateCoordinator,
        config_entry: ConfigEntry,
        direction: int,
        transport_type: int,
        route_short_name: str,
        route_long_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self._config_entry = config_entry
        self._direction = direction
        self._transport_type = transport_type
        self._route_short_name = route_short_name
        self._route_long_name = route_long_name
        
        # Create entity naming
        transport_type_name = TRANSPORT_TYPES.get(transport_type, "Unknown")
        direction_suffix = "outbound" if direction == 0 else "inbound"
        
        # Entity ID - make it more descriptive
        route_id = config_entry.data.get(CONF_ROUTE_ID, "unknown")
        self._attr_unique_id = f"{DOMAIN}_{route_id}_{direction}"
        
        # Entity name using the schema: transport_type :: route_number / route_description
        self._attr_name = f"{transport_type_name} :: {route_short_name} / {route_long_name}"
        
        # Device info - use route-specific identifier but both entities share same device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{config_entry.entry_id}_{route_id}")},
            "name": f"{transport_type_name} Route {route_short_name}",
            "manufacturer": "Metlink",
            "model": f"{transport_type_name} Route",
            "sw_version": "1.0",
        }

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
            
        # Get route data
        route_data = self.coordinator.data.get("route_data", {})
        trip_updates = self.coordinator.data.get("trip_updates", [])
        vehicle_positions = self.coordinator.data.get("vehicle_positions", [])
        
        # Filter for this direction
        direction_trips = []
        for update in trip_updates:
            trip_update = update.get("trip_update", {})
            trip = trip_update.get("trip", {})
            if trip.get("direction_id") == self._direction:
                direction_trips.append(update)
        
        direction_vehicles = []
        for position in vehicle_positions:
            trip = position.get("trip", {})
            if trip.get("direction_id") == self._direction:
                direction_vehicles.append(position)
        
        # Return status based on available data
        if direction_trips:
            return "Active"
        elif direction_vehicles:
            return "In Service"
        else:
            return "Scheduled"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}
            
        route_data = self.coordinator.data.get("route_data", {})
        trip_updates = self.coordinator.data.get("trip_updates", [])
        vehicle_positions = self.coordinator.data.get("vehicle_positions", [])
        service_alerts = self.coordinator.data.get("service_alerts", [])
        last_updated = self.coordinator.data.get("last_updated")
        
        # Filter for this direction
        direction_trips = []
        for update in trip_updates:
            trip_update = update.get("trip_update", {})
            trip = trip_update.get("trip", {})
            if trip.get("direction_id") == self._direction:
                direction_trips.append(update)
        
        direction_vehicles = []
        for position in vehicle_positions:
            trip = position.get("trip", {})
            if trip.get("direction_id") == self._direction:
                direction_vehicles.append(position)
        
        attributes = {
            "direction": self._direction,
            "direction_name": "Outbound" if self._direction == 0 else "Inbound",
            "transport_type": TRANSPORT_TYPES.get(self._transport_type, "Unknown"),
            "route_id": route_data.get("route_id"),
            "route_short_name": self._route_short_name,
            "route_long_name": self._route_long_name,
            "route_color": route_data.get("route_color"),
            "route_text_color": route_data.get("route_text_color"),
            "agency_id": route_data.get("agency_id"),
            "trip_count": len(direction_trips),
            "vehicle_count": len(direction_vehicles),
            "alert_count": len(service_alerts),
            "last_updated": last_updated.isoformat() if last_updated else None,
        }
        
        # Add trip information if available
        if direction_trips:
            next_trips = []
            for update in direction_trips[:3]:  # Show next 3 trips
                trip_update = update.get("trip_update", {})
                trip = trip_update.get("trip", {})
                
                trip_info = {
                    "trip_id": trip.get("trip_id"),
                    "delay": trip_update.get("delay", 0),
                    "schedule_relationship": trip.get("schedule_relationship", "SCHEDULED"),
                }
                
                # Add stop time updates if available
                stop_time_update = trip_update.get("stop_time_update")
                if stop_time_update:
                    if isinstance(stop_time_update, list):
                        trip_info["stops"] = len(stop_time_update)
                    else:
                        trip_info["stops"] = 1
                    
                next_trips.append(trip_info)
                
            attributes["next_trips"] = next_trips
        
        # Add vehicle information if available
        if direction_vehicles:
            vehicles = []
            for position in direction_vehicles:
                vehicle_data = position.get("vehicle", {})
                trip = position.get("trip", {})
                
                vehicle_info = {
                    "vehicle_id": vehicle_data.get("id"),
                    "trip_id": trip.get("trip_id"),
                    "timestamp": position.get("timestamp"),
                }
                
                # Add position if available
                position_data = position.get("position", {})
                if position_data:
                    vehicle_info["latitude"] = position_data.get("latitude")
                    vehicle_info["longitude"] = position_data.get("longitude")
                    vehicle_info["bearing"] = position_data.get("bearing")
                    vehicle_info["speed"] = position_data.get("speed")
                
                vehicles.append(vehicle_info)
                
            attributes["vehicles"] = vehicles
        
        # Add service alerts if available
        if service_alerts:
            alerts = []
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
                
                alerts.append(alert_info)
                
            attributes["alerts"] = alerts
        
        return attributes

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