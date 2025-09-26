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
    entities.append(
        MetlinkRouteSensor(
            coordinator,
            config_entry,
            direction=0,
            transport_type=transport_type,
            route_short_name=route_short_name,
            route_long_name=route_long_name,
        )
    )
    
    # Direction 1 (reverse direction)
    # Reverse the route name by splitting on ' - ' and reversing
    route_parts = route_long_name.split(" - ")
    reversed_route_name = " - ".join(reversed(route_parts))
    
    entities.append(
        MetlinkRouteSensor(
            coordinator,
            config_entry,
            direction=1,
            transport_type=transport_type,
            route_short_name=route_short_name,
            route_long_name=reversed_route_name,
        )
    )
    
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
        
        # Entity ID
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_{direction}"
        
        # Entity name using the schema: transport_type :: route_number / route_description
        self._attr_name = f"{transport_type_name} :: {route_short_name} / {route_long_name}"
        
        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"{transport_type_name} :: {route_short_name} / {route_long_name}",
            "manufacturer": "Metlink",
            "model": transport_type_name,
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
        direction_trips = [
            trip for trip in trip_updates 
            if trip.get("trip", {}).get("direction_id") == self._direction
        ]
        
        direction_vehicles = [
            vehicle for vehicle in vehicle_positions 
            if vehicle.get("trip", {}).get("direction_id") == self._direction
        ]
        
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
        direction_trips = [
            trip for trip in trip_updates 
            if trip.get("trip", {}).get("direction_id") == self._direction
        ]
        
        direction_vehicles = [
            vehicle for vehicle in vehicle_positions 
            if vehicle.get("trip", {}).get("direction_id") == self._direction
        ]
        
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
            for trip in direction_trips[:3]:  # Show next 3 trips
                trip_info = {
                    "trip_id": trip.get("trip", {}).get("trip_id"),
                    "delay": trip.get("delay", 0),
                    "schedule_relationship": trip.get("schedule_relationship", "SCHEDULED"),
                }
                
                # Add stop time updates if available
                if "stop_time_update" in trip:
                    trip_info["stops"] = len(trip["stop_time_update"])
                    
                next_trips.append(trip_info)
                
            attributes["next_trips"] = next_trips
        
        # Add vehicle information if available
        if direction_vehicles:
            vehicles = []
            for vehicle in direction_vehicles:
                vehicle_info = {
                    "vehicle_id": vehicle.get("vehicle", {}).get("id"),
                    "trip_id": vehicle.get("trip", {}).get("trip_id"),
                    "timestamp": vehicle.get("timestamp"),
                }
                
                # Add position if available
                if "position" in vehicle:
                    vehicle_info["latitude"] = vehicle["position"].get("latitude")
                    vehicle_info["longitude"] = vehicle["position"].get("longitude")
                    vehicle_info["bearing"] = vehicle["position"].get("bearing")
                    vehicle_info["speed"] = vehicle["position"].get("speed")
                
                vehicles.append(vehicle_info)
                
            attributes["vehicles"] = vehicles
        
        # Add service alerts if available
        if service_alerts:
            alerts = []
            for alert in service_alerts:
                alert_info = {
                    "alert_id": alert.get("id"),
                    "cause": alert.get("cause"),
                    "effect": alert.get("effect"),
                    "severity_level": alert.get("severity_level"),
                }
                
                # Add header and description texts
                if "header_text" in alert:
                    alert_info["header"] = alert["header_text"].get("translation", [{}])[0].get("text", "")
                
                if "description_text" in alert:
                    alert_info["description"] = alert["description_text"].get("translation", [{}])[0].get("text", "")
                
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