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
    _LOGGER.info("=" * 60)
    _LOGGER.info(f"🚀 STARTING Metlink Explorer sensor setup for entry: {config_entry.entry_id}")
    _LOGGER.info("=" * 60)
    
    try:
        _LOGGER.info("📡 Step 1/6: Retrieving coordinator...")
        coordinator: MetlinkDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
        _LOGGER.info(f"✅ Found coordinator: {coordinator}")
        
        # Get config data
        _LOGGER.info("📋 Step 2/6: Reading configuration data...")
        transport_type = config_entry.data[CONF_TRANSPORT_TYPE]
        route_id = config_entry.data[CONF_ROUTE_ID]
        route_short_name = config_entry.data[CONF_ROUTE_SHORT_NAME]
        route_long_name = config_entry.data[CONF_ROUTE_LONG_NAME]
        
        transport_type_name = TRANSPORT_TYPES.get(transport_type, "Unknown")
        _LOGGER.info(f"✅ Config loaded - {transport_type_name}: {route_short_name} / {route_long_name}")
        
        # Check if coordinator has data, if not wait for it
        _LOGGER.info("🔄 Step 3/6: Ensuring coordinator data is available...")
        if not coordinator.data:
            _LOGGER.info("⏳ No data available yet, requesting initial refresh...")
            await coordinator.async_request_refresh()
            if not coordinator.data:
                _LOGGER.error("❌ Failed to get initial data from coordinator")
                return
        _LOGGER.info("✅ Coordinator data is ready")
        
        # Create sensors for both directions
        _LOGGER.info("🏗️ Step 4/6: Creating route entities...")
        entities = []
        
        # Get trip updates to extract headsign information for direction naming
        trip_updates = coordinator.data.get("trip_updates", [])
        _LOGGER.info(f"🔍 Found {len(trip_updates)} trip updates for headsign extraction")
        
        # Helper function to get headsign for a direction
        def get_direction_headsign(direction_id):
            _LOGGER.info(f"   🔎 Searching for direction {direction_id} headsign in route {route_id}")
            for update in trip_updates:
                trip_update = update.get("trip_update", {})
                trip = trip_update.get("trip", {})
                trip_route_id = trip.get("route_id")
                trip_direction_id = trip.get("direction_id")
                headsign = trip.get("trip_headsign", "")
                
                if trip_route_id == route_id and trip_direction_id == direction_id:
                    if headsign:
                        # Clean up headsign and format as "to [destination]"
                        headsign = headsign.replace("to ", "").replace("To ", "")
                        _LOGGER.info(f"   ✅ Found headsign: '{headsign}' for route {route_id}, direction {direction_id}")
                        return f"to {headsign}"
            _LOGGER.info(f"   ❌ No headsign found for route {route_id}, direction {direction_id}")
            return None
        
        # Direction 0 (outbound) - use headsign or fallback to original name
        direction_0_headsign = get_direction_headsign(0)
        if direction_0_headsign:
            direction_0_name = direction_0_headsign
            _LOGGER.info(f"🎯 Found headsign for Direction 0: {direction_0_name}")
        else:
            direction_0_name = route_long_name
            _LOGGER.info(f"📍 No headsign found for Direction 0, using original name: {direction_0_name}")
        
        _LOGGER.info(f"📍 Creating Direction 0 entity (Outbound): {direction_0_name}")
        direction_0_entity = MetlinkRouteSensor(
            coordinator,
            config_entry,
            direction=0,
            transport_type=transport_type,
            route_short_name=route_short_name,
            route_long_name=direction_0_name,
        )
        entities.append(direction_0_entity)
        _LOGGER.info(f"✅ Direction 0 entity created: {direction_0_entity.name}")
        _LOGGER.info(f"   📋 Entity ID: {direction_0_entity.unique_id}")
        
        # Direction 1 (inbound) - use headsign or fallback to original name
        direction_1_headsign = get_direction_headsign(1)
        if direction_1_headsign:
            direction_1_name = direction_1_headsign
            _LOGGER.info(f"🎯 Found headsign for Direction 1: {direction_1_name}")
        else:
            direction_1_name = route_long_name
            _LOGGER.info(f"📍 No headsign found for Direction 1, using original name: {direction_1_name}")
        
        _LOGGER.info("📍 Creating Direction 1 entity (Inbound)...")
        _LOGGER.info(f"   🚂 Direction 1 route name: {direction_1_name}")
        
        direction_1_entity = MetlinkRouteSensor(
            coordinator,
            config_entry,
            direction=1,
            transport_type=transport_type,
            route_short_name=route_short_name,
            route_long_name=direction_1_name,
        )
        entities.append(direction_1_entity)
        _LOGGER.info(f"✅ Direction 1 entity created: {direction_1_entity.name}")
        _LOGGER.info(f"   📋 Entity ID: {direction_1_entity.unique_id}")
        
        _LOGGER.info("🚀 Step 5/6: Adding entities to Home Assistant...")
        _LOGGER.info(f"📊 Total entities to add: {len(entities)}")
        async_add_entities(entities, True)
        
        _LOGGER.info("🎉 Step 6/6: Setup completed successfully!")
        _LOGGER.info("=" * 60)
        _LOGGER.info(f"✅ COMPLETED Metlink Explorer setup for {transport_type_name} Route {route_short_name}")
        _LOGGER.info("📍 Check Developer Tools > States to see your new entities")
        _LOGGER.info("=" * 60)
        
    except Exception as e:
        _LOGGER.error("❌ " + "=" * 50)
        _LOGGER.error(f"❌ ERROR during Metlink Explorer setup: {e}")
        _LOGGER.error("❌ " + "=" * 50)
        raise


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
        
        # Get direction-specific departures
        departure_key = f"direction_{self._direction}_departures"
        departures = self.coordinator.data.get(departure_key, [])
        
        # Show the next departure for this direction
        if departures:
            next_departure = departures[0]
            departure_time = next_departure.get("departure_time", "")
            stop_name = next_departure.get("stop_name", "Unknown Stop")
            stop_sequence = next_departure.get("route_stop_sequence", "")
            
            if departure_time and stop_name:
                sequence_info = f" (Stop {stop_sequence})" if stop_sequence else ""
                return f"Next: {departure_time} at {stop_name}{sequence_info}"
            else:
                return f"Next departure at {stop_name}"
        
        # Filter for this direction from real-time data
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
            return "No upcoming departures"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}
            
        route_data = self.coordinator.data.get("route_data", {})
        trip_updates = self.coordinator.data.get("trip_updates", [])
        vehicle_positions = self.coordinator.data.get("vehicle_positions", [])
        service_alerts = self.coordinator.data.get("service_alerts", [])
        route_stops = self.coordinator.data.get("route_stops", {})
        last_updated = self.coordinator.data.get("last_updated")
        
        # Get direction-specific departures
        departure_key = f"direction_{self._direction}_departures"
        departures = self.coordinator.data.get(departure_key, [])
        
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
            "last_updated": last_updated.isoformat() if hasattr(last_updated, 'isoformat') else None,
        }
        
        # Add stop sequence information for this direction
        direction_stops = route_stops.get(self._direction, [])
        if direction_stops:
            stop_sequence_list = []
            for stop in direction_stops:
                stop_info = {
                    "stop_id": stop.get("stop_id", ""),
                    "stop_name": stop.get("stop_name", ""),
                    "stop_sequence": stop.get("stop_sequence", 0),
                    "stop_code": stop.get("stop_code", ""),
                    "stop_lat": stop.get("stop_lat"),
                    "stop_lon": stop.get("stop_lon"),
                    "zone_id": stop.get("zone_id", ""),
                }
                stop_sequence_list.append(stop_info)
            
            attributes["stop_sequence"] = stop_sequence_list
            attributes["total_stops"] = len(direction_stops)
        
        # Add departure information if available
        if departures:
            departure_list = []
            for departure in departures:
                departure_info = {
                    "departure_time": departure.get("departure_time", ""),
                    "arrival_time": departure.get("arrival_time", ""),
                    "stop_name": departure.get("stop_name", ""),
                    "stop_id": departure.get("stop_id", ""),
                    "trip_id": departure.get("trip_id", ""),
                    "stop_sequence": departure.get("stop_sequence", 0),
                    "route_stop_sequence": departure.get("route_stop_sequence", 0),
                    "pickup_type": departure.get("pickup_type", 0),
                    "drop_off_type": departure.get("drop_off_type", 0),
                    "stop_lat": departure.get("stop_lat"),
                    "stop_lon": departure.get("stop_lon"),
                    "zone_id": departure.get("zone_id", ""),
                    "stop_code": departure.get("stop_code", ""),
                }
                departure_list.append(departure_info)
            
            attributes["next_departures"] = departure_list
            attributes["departure_count"] = len(departures)
        
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