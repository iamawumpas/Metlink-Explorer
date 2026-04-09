"""Device tracker platform for live Metlink vehicle positions."""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_API_KEY,
    CONF_ROUTE_ID,
    CONF_TRANSPORTATION_TYPE,
    TRANSPORTATION_TYPES,
)
from .mode_registry import entry_routes, is_mode_leader, normalize_transportation_type

SUPPORTED_TRACKER_TYPES: set[int] = {2, 4}
MODE_ICONS = {
    "Train": "mdi:train",
    "Ferry": "mdi:ferry",
}


def _entry_route_ids(config_entry: ConfigEntry) -> set[str]:
    """Return configured route ids for an entry."""
    route_ids: set[str] = set()
    for route in entry_routes(config_entry):
        route_ids.add(str(route.get(CONF_ROUTE_ID)))

    if not route_ids and config_entry.data.get(CONF_ROUTE_ID):
        route_ids.add(str(config_entry.data.get(CONF_ROUTE_ID)))
    return route_ids


def _extract_positions(vehicle_positions: Any, route_ids: set[str]) -> dict[str, dict[str, Any]]:
    """Extract normalized vehicle positions, filtered to configured routes."""
    if isinstance(vehicle_positions, dict):
        entities = vehicle_positions.get("entity", [])
    elif isinstance(vehicle_positions, list):
        entities = vehicle_positions
    else:
        return {}

    results: dict[str, dict[str, Any]] = {}
    for entity in entities:
        if not isinstance(entity, dict):
            continue

        wrapper_id = entity.get("id")
        vehicle_msg = entity.get("vehicle") if isinstance(entity.get("vehicle"), dict) else entity
        if not isinstance(vehicle_msg, dict):
            continue

        trip = vehicle_msg.get("trip") or {}
        route_id = str(trip.get("route_id", "")).strip()
        if route_ids and (not route_id or route_id not in route_ids):
            continue

        position = vehicle_msg.get("position") or {}
        latitude = position.get("latitude", position.get("lat"))
        longitude = position.get("longitude", position.get("lon"))
        if latitude is None or longitude is None:
            continue

        descriptor = vehicle_msg.get("vehicle") or {}
        vehicle_id = str(descriptor.get("id") or vehicle_msg.get("vehicle_id") or wrapper_id or "").strip()
        if not vehicle_id:
            continue

        label = str(descriptor.get("label") or descriptor.get("license_plate") or vehicle_id)
        trip_id = str(trip.get("trip_id", "")).strip() or None

        try:
            lat = float(latitude)
            lon = float(longitude)
        except (TypeError, ValueError):
            continue

        bearing = position.get("bearing")
        speed = position.get("speed")
        timestamp = vehicle_msg.get("timestamp")

        results[vehicle_id] = {
            "vehicle_id": vehicle_id,
            "label": label,
            "route_id": route_id or None,
            "trip_id": trip_id,
            "latitude": lat,
            "longitude": lon,
            "bearing": bearing,
            "speed": speed,
            "timestamp": timestamp,
        }

    return results


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up live train/ferry vehicle trackers from GTFS-RT vehicle positions."""
    transport_type = normalize_transportation_type(config_entry.data.get(CONF_TRANSPORTATION_TYPE))
    if transport_type not in SUPPORTED_TRACKER_TYPES:
        return
    if not is_mode_leader(hass, config_entry):
        return

    transportation_name = TRANSPORTATION_TYPES.get(transport_type, "Vehicle")

    runtime = hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {})
    coordinator = runtime.get("coordinator")
    if coordinator is None:
        return

    route_ids = _entry_route_ids(config_entry)
    known_vehicle_ids: set[str] = set()

    @callback
    def async_discover_new_trackers() -> None:
        vehicle_positions = coordinator.data.get("vehicle_positions") if coordinator.data else None
        current = _extract_positions(vehicle_positions, route_ids)

        new_entities: list[MetlinkVehicleTrackerEntity] = []
        for vehicle_id, data in current.items():
            if vehicle_id in known_vehicle_ids:
                continue
            known_vehicle_ids.add(vehicle_id)
            new_entities.append(
                MetlinkVehicleTrackerEntity(
                    coordinator=coordinator,
                    transportation_name=transportation_name,
                    route_ids=route_ids,
                    vehicle_id=vehicle_id,
                    initial_data=data,
                )
            )

        if new_entities:
            async_add_entities(new_entities)

    async_discover_new_trackers()
    unsub = coordinator.async_add_listener(async_discover_new_trackers)
    config_entry.async_on_unload(unsub)


class MetlinkVehicleTrackerEntity(CoordinatorEntity, TrackerEntity):
    """Tracker entity representing a single live Metlink vehicle."""

    _attr_source_type = SourceType.GPS

    def __init__(
        self,
        coordinator,
        transportation_name: str,
        route_ids: set[str],
        vehicle_id: str,
        initial_data: dict[str, Any],
    ) -> None:
        """Initialize live vehicle tracker."""
        super().__init__(coordinator)
        self._transportation_name = transportation_name
        self._route_ids = route_ids
        self._vehicle_id = vehicle_id
        self._initial_data = initial_data

        self._attr_unique_id = f"{DOMAIN}_{transportation_name.lower()}_vehicle_{vehicle_id}"
        self._attr_name = f"{transportation_name} {initial_data.get('label', vehicle_id)}"
        self._attr_icon = MODE_ICONS.get(transportation_name, "mdi:crosshairs-gps")
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{transportation_name.lower()}_vehicle_{vehicle_id}")},
            "name": self._attr_name,
            "manufacturer": "Metlink",
            "model": f"{transportation_name} Vehicle",
            "sw_version": "0.5.1",
        }

    def _current(self) -> dict[str, Any] | None:
        """Return latest normalized data for this vehicle."""
        vehicle_positions = self.coordinator.data.get("vehicle_positions") if self.coordinator.data else None
        positions = _extract_positions(vehicle_positions, self._route_ids)
        return positions.get(self._vehicle_id) or self._initial_data

    @property
    def available(self) -> bool:
        """Return if tracker has a current GPS fix from coordinator data."""
        return self.coordinator.last_update_success and self._current() is not None

    @property
    def latitude(self) -> float | None:
        """Return current latitude."""
        current = self._current()
        return current.get("latitude") if current else None

    @property
    def longitude(self) -> float | None:
        """Return current longitude."""
        current = self._current()
        return current.get("longitude") if current else None

    @property
    def location_accuracy(self) -> int:
        """Return estimated GPS accuracy in meters."""
        return 100

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return live metadata for map popups/debugging."""
        current = self._current()
        if not current:
            return {}
        return {
            "vehicle_id": current.get("vehicle_id"),
            "label": current.get("label"),
            "route_id": current.get("route_id"),
            "trip_id": current.get("trip_id"),
            "bearing": current.get("bearing"),
            "speed": current.get("speed"),
            "timestamp": current.get("timestamp"),
        }
