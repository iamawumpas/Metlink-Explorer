"""Sensor platform for Metlink Explorer."""
from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ACTIVE_DIRECTION,
    CONF_API_KEY,
    CONF_ROUTE_DESC,
    CONF_ROUTE_ID,
    CONF_ROUTE_LONG_NAME,
    CONF_ROUTE_SHORT_NAME,
    CONF_ROUTES,
    CONF_TRANSPORTATION_TYPE,
    DEFAULT_ACTIVE_DIRECTION,
    DOMAIN,
    TRAIN_ROUTE_TYPE,
    TRANSPORTATION_TYPES,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up route-centric and compatibility sensors."""
    runtime = hass.data[DOMAIN][config_entry.entry_id]
    coordinators: dict[str, Any] = runtime.get("coordinators", {})

    routes = config_entry.data.get(CONF_ROUTES)
    if not isinstance(routes, list) or not routes:
        routes = [
            {
                CONF_ROUTE_ID: config_entry.data[CONF_ROUTE_ID],
                CONF_ROUTE_SHORT_NAME: config_entry.data[CONF_ROUTE_SHORT_NAME],
                CONF_ROUTE_LONG_NAME: config_entry.data[CONF_ROUTE_LONG_NAME],
                CONF_ROUTE_DESC: config_entry.data.get(CONF_ROUTE_DESC, ""),
            }
        ]

    api_key = config_entry.data[CONF_API_KEY]
    transportation_type = config_entry.data[CONF_TRANSPORTATION_TYPE]
    transportation_name = TRANSPORTATION_TYPES.get(transportation_type, "Unknown")

    entities: list[SensorEntity] = []
    for route in routes:
        route_id = str(route.get(CONF_ROUTE_ID))
        if not route_id:
            continue
        coordinator = coordinators.get(route_id) or runtime.get("coordinator")
        if not coordinator:
            continue

        route_short_name = route.get(CONF_ROUTE_SHORT_NAME, "Unknown")
        route_long_name = route.get(CONF_ROUTE_LONG_NAME, "Unknown Route")
        route_desc = route.get(CONF_ROUTE_DESC, "")

        entities.append(
            MetlinkRouteSensor(
                coordinator,
                config_entry,
                route_id,
                route_short_name,
                route_long_name,
                route_desc,
                transportation_name,
            )
        )

    if _is_mode_leader(hass, config_entry):
        entities.append(
            MetlinkModeBoardSensor(
                coordinator,
                hass,
                api_key,
                transportation_type,
                transportation_name,
            )
        )

    if int(transportation_type) == TRAIN_ROUTE_TYPE:
        geometry_coordinator = runtime.get("geometry_coordinator")
        if geometry_coordinator is not None:
            entities.append(
                MetlinkTrainRouteGeometrySensor(
                    geometry_coordinator,
                    transportation_name,
                )
            )
            line_routes: list[tuple[str, str]] = []
            seen_route_ids: set[str] = set()

            # Create one per-line entity for every configured train route.
            for route in routes:
                route_id = str(route.get(CONF_ROUTE_ID, "")).strip()
                if not route_id or route_id in seen_route_ids:
                    continue
                seen_route_ids.add(route_id)
                route_short_name = str(route.get(CONF_ROUTE_SHORT_NAME) or route_id)
                line_routes.append((route_id, route_short_name))

            geometry_data = geometry_coordinator.data if isinstance(geometry_coordinator.data, dict) else {}
            geometry_features = geometry_data.get("features", []) if isinstance(geometry_data, dict) else []
            if isinstance(geometry_features, list):
                for feature in geometry_features:
                    if not isinstance(feature, dict):
                        continue
                    props = feature.get("properties", {})
                    if not isinstance(props, dict):
                        continue
                    route_id = str(props.get("route_id", "")).strip()
                    if not route_id or route_id in seen_route_ids:
                        continue
                    seen_route_ids.add(route_id)
                    route_short_name = str(props.get("route_short_name") or route_id)
                    line_routes.append((route_id, route_short_name))

            for route_id, route_short_name in line_routes:
                entities.append(
                    MetlinkTrainLineGeometrySensor(
                        geometry_coordinator,
                        route_id=route_id,
                        route_short_name=route_short_name,
                    )
                )

    async_add_entities(entities)


def _is_mode_leader(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Ensure only one board sensor is created per API key and transportation type."""
    api_key = config_entry.data.get(CONF_API_KEY)
    transport_type = int(config_entry.data.get(CONF_TRANSPORTATION_TYPE, -1))
    same_group_entries = [
        entry.entry_id
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get(CONF_API_KEY) == api_key
        and int(entry.data.get(CONF_TRANSPORTATION_TYPE, -1)) == transport_type
    ]
    if not same_group_entries:
        return True
    return config_entry.entry_id == sorted(same_group_entries)[0]


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


def _normalize_departure_str(value: str | None) -> str:
    """Normalize departure string for sorting and parsing."""
    if not value:
        return ""
    text = str(value).replace("Scheduled:", "").strip()
    match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", text)
    if not match:
        return ""
    hour = int(match.group(1))
    minute = int(match.group(2))
    second = int(match.group(3) or "0")
    if hour >= 24:
        hour -= 24
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def _eta_seconds_from_departure(value: str | None, wrap_next_day: bool = True) -> int | None:
    """Compute ETA seconds from local time string.

    When wrap_next_day is False, times earlier than now return negative values.
    """
    normalized = _normalize_departure_str(value)
    if not normalized:
        return None
    try:
        now = datetime.now()
        target = datetime.strptime(f"{now.date()} {normalized}", "%Y-%m-%d %H:%M:%S")
        if target < now:
            if wrap_next_day:
                # If already passed today, treat as next-day service.
                target = target + timedelta(days=1)
        return int((target - now).total_seconds())
    except Exception:
        return None


def _direction_from_entry(entry: ConfigEntry, direction_id: int) -> str:
    """Get user-facing direction label from entry metadata."""
    route_long_name = entry.data.get(CONF_ROUTE_LONG_NAME, "")
    route_desc = entry.data.get(CONF_ROUTE_DESC, "")
    return _direction_label(route_long_name, route_desc, direction_id)


def _train_line_default_color(route_short_name: str | None) -> str:
    """Return a default color for known train line abbreviations."""
    key = (route_short_name or "").strip().upper()
    known = {
        "HVL": "#f57c00",
        "KPL": "#1e88e5",
        "JVL": "#43a047",
        "MEL": "#8e24aa",
        "WRL": "#e53935",
    }
    return known.get(key, "#00bcd4")


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
            "sw_version": "0.4.16",
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
            "sw_version": "0.4.16",
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


class MetlinkModeBoardSensor(CoordinatorEntity, SensorEntity):
    """Aggregate departures board for a transportation mode across configured routes."""

    def __init__(
        self,
        coordinator,
        hass: HomeAssistant,
        api_key: str,
        transportation_type: int,
        transportation_name: str,
    ) -> None:
        """Initialize mode board sensor."""
        super().__init__(coordinator)
        self._hass = hass
        self._api_key = api_key
        self._transportation_type = transportation_type
        self._transportation_name = transportation_name

        self._attr_name = f"{transportation_name} :: Departures Board"
        self._attr_unique_id = f"{DOMAIN}_{transportation_type}_board"
        self._attr_native_unit_of_measurement = "departures"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = True

    def _build_departures(self) -> tuple[list[dict[str, Any]], int]:
        """Collect and normalize timetable departures across all routes in this mode."""
        rows: list[dict[str, Any]] = []
        route_count = 0

        entries = [
            entry
            for entry in self._hass.config_entries.async_entries(DOMAIN)
            if entry.data.get(CONF_API_KEY) == self._api_key
            and entry.data.get(CONF_TRANSPORTATION_TYPE) == self._transportation_type
        ]

        for entry in entries:
            runtime = self._hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
            routes = entry.data.get(CONF_ROUTES)
            if not isinstance(routes, list) or not routes:
                routes = [
                    {
                        CONF_ROUTE_ID: entry.data.get(CONF_ROUTE_ID),
                        CONF_ROUTE_SHORT_NAME: entry.data.get(CONF_ROUTE_SHORT_NAME),
                    }
                ]

            coordinators: dict[str, Any] = runtime.get("coordinators", {})
            route_short_name_by_id = {
                str(r.get(CONF_ROUTE_ID)): r.get(CONF_ROUTE_SHORT_NAME)
                for r in routes
                if r.get(CONF_ROUTE_ID) is not None
            }

            for route_id, coordinator in coordinators.items():
                if not coordinator or not coordinator.data:
                    continue
                route_count += 1

                route_short_name = route_short_name_by_id.get(str(route_id))

                timetable_rows = coordinator.data.get("timetable_rows", [])
                if not isinstance(timetable_rows, list):
                    continue

                for row in timetable_rows:
                    if not isinstance(row, dict):
                        continue

                    departure = row.get("departure_time") or row.get("scheduled_departure_time")
                    if not departure:
                        continue

                    eta_seconds = _eta_seconds_from_departure(departure, wrap_next_day=False)
                    if eta_seconds is None or eta_seconds < 0:
                        # Board rows are for upcoming departures only.
                        continue
                    direction_id_raw = row.get("direction_id")
                    try:
                        direction_id = int(direction_id_raw) if direction_id_raw is not None else None
                    except (TypeError, ValueError):
                        direction_id = None
                    direction_label = _direction_from_entry(entry, direction_id) if direction_id is not None else None

                    rows.append(
                        {
                            "route_id": route_id,
                            "route_short_name": route_short_name,
                            "route_type": self._transportation_name.lower(),
                            "direction_id": direction_id,
                            "direction_label": direction_label,
                            "stop_id": row.get("stop_id"),
                            "stop_name": row.get("stop_name"),
                            "destination": row.get("destination"),
                            "departure_time": departure,
                            "scheduled_departure_time": row.get("scheduled_departure_time"),
                            "eta_seconds": eta_seconds,
                            "eta_display": row.get("eta_display"),
                            "is_realtime": bool(row.get("is_realtime", False)),
                            "time_source": row.get("time_source"),
                            # Debug fields
                            "trip_id": row.get("trip_id"),
                            "service_id": row.get("service_id"),
                            "service_date": row.get("service_date"),
                            "stop_sequence": row.get("stop_sequence"),
                            "debug_source": row.get("debug_source"),
                        }
                    )

            # Legacy fallback if no coordinators dict is present.
            if not coordinators:
                coordinator = runtime.get("coordinator")
                if coordinator and coordinator.data:
                    route_count += 1
                    route_id = entry.data.get(CONF_ROUTE_ID)
                    route_short_name = entry.data.get(CONF_ROUTE_SHORT_NAME)
                    for row in coordinator.data.get("timetable_rows", []) or []:
                        if not isinstance(row, dict):
                            continue
                        departure = row.get("departure_time") or row.get("scheduled_departure_time")
                        if not departure:
                            continue
                        eta_seconds = _eta_seconds_from_departure(departure, wrap_next_day=False)
                        if eta_seconds is None or eta_seconds < 0:
                            continue
                        rows.append(
                            {
                                "route_id": route_id,
                                "route_short_name": route_short_name,
                                "route_type": self._transportation_name.lower(),
                                "direction_id": row.get("direction_id"),
                                "direction_label": None,
                                "stop_id": row.get("stop_id"),
                                "stop_name": row.get("stop_name"),
                                "destination": row.get("destination"),
                                "departure_time": departure,
                                "scheduled_departure_time": row.get("scheduled_departure_time"),
                                "eta_seconds": eta_seconds,
                                "eta_display": row.get("eta_display"),
                                "is_realtime": bool(row.get("is_realtime", False)),
                                "time_source": row.get("time_source"),
                                "trip_id": row.get("trip_id"),
                                "service_id": row.get("service_id"),
                                "service_date": row.get("service_date"),
                                "stop_sequence": row.get("stop_sequence"),
                                "debug_source": row.get("debug_source"),
                            }
                        )

        def sort_key(item: dict[str, Any]) -> tuple[int, str]:
            eta = item.get("eta_seconds")
            if isinstance(eta, int):
                return (0, f"{eta:08d}")
            return (1, _normalize_departure_str(item.get("departure_time")) or "99:99:99")

        rows.sort(key=sort_key)
        return rows, route_count

    @property
    def native_value(self) -> int | None:
        """Return number of upcoming departures in board payload."""
        departures, _ = self._build_departures()
        return len(departures)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return aggregated departures and metadata."""
        departures, route_count = self._build_departures()
        return {
            "transportation_type": self._transportation_name,
            "transportation_type_id": self._transportation_type,
            "configured_route_count": route_count,
            "departure_count": len(departures),
            "departures": departures,
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
        return transportation_icons.get(self._transportation_name, "mdi:format-list-bulleted-square")


class MetlinkTrainRouteGeometrySensor(CoordinatorEntity, SensorEntity):
    """Expose train route geometries as GeoJSON for map overlays."""

    def __init__(self, coordinator, transportation_name: str) -> None:
        """Initialize train route geometry sensor."""
        super().__init__(coordinator)
        self._transportation_name = transportation_name
        self._attr_name = f"{transportation_name} :: Route Geometry"
        self._attr_unique_id = f"{DOMAIN}_{transportation_name.lower()}_route_geometry"
        self._attr_native_unit_of_measurement = "routes"
        self._attr_entity_registry_enabled_default = True
        self._attr_icon = "mdi:map-marker-path"

    @property
    def native_value(self) -> int | None:
        """Return number of route features in GeoJSON payload."""
        data = self.coordinator.data if isinstance(self.coordinator.data, dict) else {}
        return int(data.get("feature_count", 0))

    @property
    def available(self) -> bool:
        """Return if geometry payload is available."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return GeoJSON data and summary attributes."""
        data = self.coordinator.data if isinstance(self.coordinator.data, dict) else {}
        return {
            "transportation_type": self._transportation_name,
            "geojson": {
                "type": data.get("type", "FeatureCollection"),
                "features": data.get("features", []),
            },
            "route_count": data.get("route_count", 0),
            "feature_count": data.get("feature_count", 0),
        }


class MetlinkTrainLineGeometrySensor(CoordinatorEntity, SensorEntity):
    """Expose a single train line geometry as GeoJSON for per-route styling."""

    def __init__(self, coordinator, route_id: str, route_short_name: str) -> None:
        """Initialize train line geometry sensor."""
        super().__init__(coordinator)
        self._route_id = str(route_id)
        self._route_short_name = route_short_name
        self._attr_name = f"Train :: {self._route_short_name} Geometry"
        self._attr_unique_id = f"{DOMAIN}_train_route_geometry_{self._route_id}"
        self._attr_native_unit_of_measurement = "features"
        self._attr_entity_registry_enabled_default = True
        self._attr_icon = "mdi:transit-connection-horizontal"

    def _feature(self) -> dict[str, Any] | None:
        """Return this route's feature from the mode geometry payload."""
        data = self.coordinator.data if isinstance(self.coordinator.data, dict) else {}
        features = data.get("features", [])
        if not isinstance(features, list):
            return None
        for feature in features:
            if not isinstance(feature, dict):
                continue
            props = feature.get("properties", {})
            if not isinstance(props, dict):
                continue
            if str(props.get("route_id", "")) == self._route_id:
                return feature
        return None

    @property
    def native_value(self) -> int | None:
        """Return 1 when this route has geometry data available."""
        return 1 if self._feature() else 0

    @property
    def available(self) -> bool:
        """Return if geometry payload is available."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return route-specific GeoJSON and default style hint."""
        feature = self._feature()
        features = [feature] if feature else []
        return {
            "route_id": self._route_id,
            "route_short_name": self._route_short_name,
            "default_color": _train_line_default_color(self._route_short_name),
            "geojson": {
                "type": "FeatureCollection",
                "features": features,
            },
            "feature_count": len(features),
        }
