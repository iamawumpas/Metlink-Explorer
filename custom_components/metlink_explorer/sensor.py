"""Sensor platform for Metlink Explorer."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ACTIVE_DIRECTION,
    CONF_LEGACY_DIRECTION_ENTITIES,
    CONF_ROUTE_DESC,
    CONF_ROUTE_ID,
    CONF_ROUTE_LONG_NAME,
    CONF_ROUTE_SHORT_NAME,
    CONF_TRANSPORTATION_TYPE,
    DEFAULT_ACTIVE_DIRECTION,
    DOMAIN,
    TRANSPORTATION_TYPES,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up route-centric and compatibility sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    route_id = config_entry.data[CONF_ROUTE_ID]
    route_short_name = config_entry.data[CONF_ROUTE_SHORT_NAME]
    route_long_name = config_entry.data[CONF_ROUTE_LONG_NAME]
    route_desc = config_entry.data.get(CONF_ROUTE_DESC, "")
    transportation_type = config_entry.data[CONF_TRANSPORTATION_TYPE]
    transportation_name = TRANSPORTATION_TYPES.get(transportation_type, "Unknown")

    entities: list[SensorEntity] = [
        MetlinkRouteSensor(
            coordinator,
            config_entry,
            route_id,
            route_short_name,
            route_long_name,
            route_desc,
            transportation_name,
        )
    ]

    if config_entry.options.get(CONF_LEGACY_DIRECTION_ENTITIES, True):
        entities.append(
            MetlinkDirectionSensor(
                coordinator,
                config_entry,
                route_id,
                route_short_name,
                _direction_label(route_long_name, route_desc, 0),
                transportation_name,
                0,
            )
        )
        entities.append(
            MetlinkDirectionSensor(
                coordinator,
                config_entry,
                route_id,
                route_short_name,
                _direction_label(route_long_name, route_desc, 1),
                transportation_name,
                1,
            )
        )

    async_add_entities(entities)


def _direction_label(route_long_name: str, route_desc: str, direction: int) -> str:
    """Build a friendly direction label using existing route metadata."""
    if direction == 0:
        return route_desc or route_long_name
    return route_long_name


def _timeline_for_direction(data: dict[str, Any] | None, direction: int) -> dict[str, Any]:
    """Get timeline for a direction from coordinator payload."""
    if not data:
        return {}
    timeline_by_direction = data.get("timeline_by_direction", {})
    if not isinstance(timeline_by_direction, dict):
        return {}
    return timeline_by_direction.get(direction, {}) if isinstance(timeline_by_direction.get(direction), dict) else {}


def _trip_count_for_direction(data: dict[str, Any] | None, direction: int) -> int:
    """Count active trips for the given direction."""
    trips = data.get("trips", []) if data else []
    if not isinstance(trips, list):
        return 0
    return len([trip for trip in trips if isinstance(trip, dict) and trip.get("direction_id") == direction])


class MetlinkRouteSensor(CoordinatorEntity, SensorEntity):
    """Primary route sensor representing both directions."""

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        route_id: str,
        route_short_name: str,
        route_long_name: str,
        route_desc: str,
        transportation_name: str,
    ) -> None:
        """Initialize the route sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._route_id = route_id
        self._route_short_name = route_short_name
        self._route_long_name = route_long_name
        self._route_desc = route_desc
        self._transportation_name = transportation_name

        self._attr_name = f"{route_short_name} :: Route"
        self._attr_unique_id = f"{DOMAIN}_{route_id}_route"
        self._attr_native_unit_of_measurement = "trips"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{route_id}")},
            "name": f"{transportation_name} Route {route_short_name}",
            "manufacturer": "Metlink",
            "model": transportation_name,
            "sw_version": "0.4.0",
        }

    @property
    def native_value(self) -> int | None:
        """Return active trip count for selected direction."""
        if not self.coordinator.data:
            return None
        active_direction = int(self._config_entry.options.get(CONF_ACTIVE_DIRECTION, DEFAULT_ACTIVE_DIRECTION))
        return _trip_count_for_direction(self.coordinator.data, active_direction)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return route-centric attributes for both directions."""
        if not self.coordinator.data:
            return {}

        active_direction = int(self._config_entry.options.get(CONF_ACTIVE_DIRECTION, DEFAULT_ACTIVE_DIRECTION))
        dir0 = _timeline_for_direction(self.coordinator.data, 0)
        dir1 = _timeline_for_direction(self.coordinator.data, 1)
        active = dir0 if active_direction == 0 else dir1

        return {
            "route_id": self._route_id,
            "route_short_name": self._route_short_name,
            "transportation_type": self._transportation_name,
            "active_direction": active_direction,
            "direction_0_label": _direction_label(self._route_long_name, self._route_desc, 0),
            "direction_1_label": _direction_label(self._route_long_name, self._route_desc, 1),
            "direction_0_trip_count": _trip_count_for_direction(self.coordinator.data, 0),
            "direction_1_trip_count": _trip_count_for_direction(self.coordinator.data, 1),
            "direction_0_destination": (dir0.get("destination_stop") or {}).get("stop_name") if isinstance(dir0, dict) else None,
            "direction_1_destination": (dir1.get("destination_stop") or {}).get("stop_name") if isinstance(dir1, dict) else None,
            "timeline_error": active.get("error") if isinstance(active, dict) else None,
            "timeline_stops": active.get("stops", []) if isinstance(active, dict) else [],
            "departure_stop": active.get("departure_stop") if isinstance(active, dict) else None,
            "destination_stop_timeline": active.get("destination_stop") if isinstance(active, dict) else None,
            "hub_stops": active.get("hub_stops", []) if isinstance(active, dict) else [],
            "current_time": active.get("current_time") if isinstance(active, dict) else None,
            "total_stops": active.get("total_stops", 0) if isinstance(active, dict) else 0,
            "real_time_stops": active.get("real_time_stops", 0) if isinstance(active, dict) else 0,
        }

    @property
    def icon(self) -> str:
        """Return icon based on transportation type."""
        transportation_icons = {
            "Train": "mdi:train",
            "Bus": "mdi:bus",
            "Ferry": "mdi:ferry",
            "Cable Car": "mdi:cable-car",
            "School Bus": "mdi:bus-school",
        }
        return transportation_icons.get(self._transportation_name, "mdi:transit-connection-variant")


class MetlinkDirectionSensor(CoordinatorEntity, SensorEntity):
    """Legacy compatibility sensor per direction to preserve IDs."""

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        route_id: str,
        route_short_name: str,
        route_description: str,
        transportation_name: str,
        direction: int,
    ) -> None:
        """Initialize legacy direction sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._route_id = route_id
        self._route_short_name = route_short_name
        self._route_description = route_description
        self._transportation_name = transportation_name
        self._direction = direction

        self._attr_name = f"{route_short_name} :: {route_description}"
        # Preserve existing unique_id format for migration compatibility.
        self._attr_unique_id = f"{DOMAIN}_{route_id}_{direction}"
        self._attr_native_unit_of_measurement = "trips"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{route_id}")},
            "name": f"{transportation_name} Route {route_short_name}",
            "manufacturer": "Metlink",
            "model": transportation_name,
            "sw_version": "0.4.0",
        }

    @property
    def native_value(self) -> int | None:
        """Return active trip count for this direction."""
        if not self.coordinator.data:
            return None
        return _trip_count_for_direction(self.coordinator.data, self._direction)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return compatibility attributes for this direction."""
        timeline = _timeline_for_direction(self.coordinator.data, self._direction)
        timeline = timeline if isinstance(timeline, dict) else {}

        dep_stop = timeline.get("departure_stop") or {}
        dest_stop = timeline.get("destination_stop") or {}
        timeline_stops = timeline.get("stops", [])

        preview_items: list[str] = []
        for stop in timeline_stops[:3] if isinstance(timeline_stops, list) else []:
            if isinstance(stop, dict) and stop.get("stop_name") and (stop.get("next_departure") or stop.get("scheduled_time")):
                preview_items.append(f"{stop.get('stop_name')} {stop.get('next_departure') or stop.get('scheduled_time')}")

        return {
            "route_id": self._route_id,
            "route_short_name": self._route_short_name,
            "route_description": self._route_description,
            "transportation_type": self._transportation_name,
            "direction": self._direction,
            "trip_count": _trip_count_for_direction(self.coordinator.data, self._direction),
            "last_updated": self.coordinator.last_update_success,
            "timeline_stops": timeline_stops,
            "timeline_error": timeline.get("error"),
            "departure_stop": dep_stop,
            "destination_stop_timeline": dest_stop,
            "hub_stops": timeline.get("hub_stops", []),
            "current_time": timeline.get("current_time"),
            "timeline_departure_stop_name": dep_stop.get("stop_name") if isinstance(dep_stop, dict) else None,
            "timeline_destination_stop_name": dest_stop.get("stop_name") if isinstance(dest_stop, dict) else None,
            "timeline_next_eta": dep_stop.get("eta_display") if isinstance(dep_stop, dict) else None,
            "timeline_next_departure": dep_stop.get("next_departure") if isinstance(dep_stop, dict) else None,
            "timeline_next_time_source": dep_stop.get("time_source") if isinstance(dep_stop, dict) else None,
            "timeline_preview": " • ".join(preview_items) if preview_items else None,
        }

    @property
    def icon(self) -> str:
        """Return icon based on transportation type."""
        transportation_icons = {
            "Train": "mdi:train",
            "Bus": "mdi:bus",
            "Ferry": "mdi:ferry",
            "Cable Car": "mdi:cable-car",
            "School Bus": "mdi:bus-school",
        }
        return transportation_icons.get(self._transportation_name, "mdi:transit-connection-variant")
