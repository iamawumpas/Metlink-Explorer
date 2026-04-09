"""API client for Metlink Open Data."""
from __future__ import annotations

import asyncio
import math
import logging
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

import aiohttp
import async_timeout

from .const import (
    API_ENDPOINTS,
    BASE_URL,
    DEFAULT_GTFS_CACHE_TTL_SECONDS,
    REQUEST_TIMEOUT,
    TRAIN_GTFS_CACHE_TTL_SECONDS,
    TRAIN_ROUTE_TYPE,
)

_LOGGER = logging.getLogger(__name__)
NEGATIVE_ROUTE_GEOMETRY_CACHE_TTL_SECONDS = 300
TRAIN_OVERLAP_OFFSET_METERS = 10.0


class MetlinkApiError(Exception):
    """Exception to indicate a general API error."""


class MetlinkApiClient:
    """Client for interacting with Metlink Open Data API."""

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession,
        transportation_type: int | None = None,
    ) -> None:
        """Initialize the API client."""
        self._api_key = api_key
        self._session = session
        self._base_url = BASE_URL
        self._transportation_type = int(transportation_type) if transportation_type is not None else None
        # Simple caches to reduce repeated static lookups
        self._route_short_name_cache = {}
        # TTL caches for static endpoints
        self._routes_cache = None
        self._routes_cache_ts = None
        self._trips_cache = None
        self._trips_cache_ts = None
        self._trips_by_route_cache: dict[str, list[dict[str, Any]]] = {}
        self._stops_cache = None
        self._stops_cache_ts = None
        self._calendar_dates_cache = None
        self._calendar_dates_cache_ts = None
        self._stop_times_cache_by_trip: dict[str, tuple[datetime, list[dict[str, Any]]]] = {}
        self._shapes_cache_by_id: dict[str, tuple[datetime, list[dict[str, Any]]]] = {}
        self._stop_pattern_cache = {}
        self._route_timetable_cache = {}
        self._route_geometry_cache: dict[str, tuple[datetime, dict[str, Any]]] = {}
        self._route_geometry_miss_cache: dict[str, datetime] = {}
        self._cache_ttl_seconds = DEFAULT_GTFS_CACHE_TTL_SECONDS

    @property
    def _static_cache_ttl_seconds(self) -> int:
        """Return cache TTL for static GTFS datasets.

        Train static GTFS data changes infrequently, so use a weekly TTL to
        reduce repeated API load.
        """
        if self._transportation_type == TRAIN_ROUTE_TYPE:
            return TRAIN_GTFS_CACHE_TTL_SECONDS
        return self._cache_ttl_seconds

    async def _request(self, endpoint: str) -> dict[str, Any]:
        """Make a request to the API."""
        url = f"{self._base_url}{endpoint}"
        headers = {
            "accept": "application/json",
            "x-api-key": self._api_key,
        }

        try:
            async with async_timeout.timeout(REQUEST_TIMEOUT):
                async with self._session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    return await response.json()
        except asyncio.TimeoutError as exc:
            raise MetlinkApiError(f"Timeout occurred while connecting to API: {url}") from exc
        except aiohttp.ClientError as exc:
            raise MetlinkApiError(f"Error occurred while communicating with API: {exc}") from exc

    async def validate_api_key(self) -> bool:
        """Validate the API key by making a test request."""
        try:
            await self._request(API_ENDPOINTS["agency"])
            return True
        except MetlinkApiError:
            return False

    async def get_routes(self) -> list[dict[str, Any]]:
        """Get all routes."""
        try:
            now = datetime.now()
            if self._routes_cache is not None and self._routes_cache_ts and (now - self._routes_cache_ts).total_seconds() < self._static_cache_ttl_seconds:
                return self._routes_cache
            data = await self._request(API_ENDPOINTS["routes"])
            if isinstance(data, list):
                self._routes_cache = data
                self._routes_cache_ts = now
            return data
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to fetch routes: %s", exc)
            raise

    async def get_routes_by_type(self, route_type: int) -> list[dict[str, Any]]:
        """Get routes filtered by transportation type."""
        routes = await self.get_routes()
        return [route for route in routes if route.get("route_type") == route_type]

    async def get_trips_for_route(self, route_id: str) -> list[dict[str, Any]]:
        """Get trips for a specific route."""
        try:
            route_id = str(route_id)
            _LOGGER.debug("Getting trips for route %s", route_id)
            now = datetime.now()
            cache_valid = (
                self._trips_cache is not None
                and self._trips_cache_ts is not None
                and (now - self._trips_cache_ts).total_seconds() < self._static_cache_ttl_seconds
            )

            if not cache_valid:
                trips = await self._request(API_ENDPOINTS["trips"])
                if not isinstance(trips, list):
                    trips = []
                self._trips_cache = trips
                self._trips_cache_ts = now
                self._trips_by_route_cache = {}
                for trip in trips:
                    if not isinstance(trip, dict):
                        continue
                    rid = str(trip.get("route_id", "")).strip()
                    if not rid:
                        continue
                    self._trips_by_route_cache.setdefault(rid, []).append(trip)

            route_trips = self._trips_by_route_cache.get(route_id, [])
            _LOGGER.debug(
                "Found %d trips for route %s out of %d total trips",
                len(route_trips),
                route_id,
                len(self._trips_cache) if isinstance(self._trips_cache, list) else 0,
            )
            return route_trips
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to fetch trips for route %s: %s", route_id, exc)
            raise

    async def get_stop_times_for_trip(self, trip_id: str) -> list[dict[str, Any]]:
        """Get stop times for a specific trip to understand stop sequence."""
        try:
            trip_id = str(trip_id)
            _LOGGER.debug("Getting stop times for trip %s", trip_id)
            now = datetime.now()
            cached = self._stop_times_cache_by_trip.get(trip_id)
            if cached and (now - cached[0]).total_seconds() < self._static_cache_ttl_seconds:
                return cached[1]

            # The stop_times endpoint requires trip_id as a parameter
            endpoint = f"{API_ENDPOINTS['stop_times']}?trip_id={trip_id}"
            stop_times = await self._request(endpoint)
            
            # The API returns the stop times directly, no need to filter
            if not isinstance(stop_times, list):
                _LOGGER.warning("Expected list from stop_times API, got %s", type(stop_times))
                return []
            
            # Sort by stop_sequence to get the correct order
            sorted_stop_times = sorted(stop_times, key=lambda x: x.get("stop_sequence", 0))
            self._stop_times_cache_by_trip[trip_id] = (now, sorted_stop_times)
            
            _LOGGER.debug("Found %d stop times for trip %s", len(sorted_stop_times), trip_id)
            
            return sorted_stop_times
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to fetch stop times for trip %s: %s", trip_id, exc)
            raise

    async def get_route_stop_pattern(self, route_id: str, direction_id: int) -> list[dict[str, Any]]:
        """Get the stop pattern for a route in a specific direction."""
        try:
            _LOGGER.debug("Getting stop pattern for route %s direction %s", route_id, direction_id)
            cache_key = (str(route_id), int(direction_id))
            now = datetime.now()
            cached = self._stop_pattern_cache.get(cache_key)
            if cached and (now - cached[0]).total_seconds() < self._static_cache_ttl_seconds:
                return cached[1]
            
            # Get trips for this route and direction
            trips = await self.get_trips_for_route(route_id)
            _LOGGER.debug("Found %d total trips for route %s", len(trips), route_id)
            
            direction_trips = [t for t in trips if t.get("direction_id") == direction_id]
            _LOGGER.debug("Found %d trips for route %s direction %s", len(direction_trips), route_id, direction_id)
            
            if not direction_trips:
                _LOGGER.error("No trips found for route %s direction %s - this will prevent stop pattern creation", route_id, direction_id)
                _LOGGER.debug("Available trips for route %s: %s", route_id, [f"trip_id={t.get('trip_id')}, direction_id={t.get('direction_id')}" for t in trips[:5]])
                return []
            
            # Use the first trip to get the stop pattern
            sample_trip = direction_trips[0]
            trip_id = sample_trip["trip_id"]
            _LOGGER.debug("Using sample trip %s for stop pattern", trip_id)
            
            # Get stop times for this trip
            stop_times = await self.get_stop_times_for_trip(trip_id)
            _LOGGER.debug("Found %d stop times for trip %s", len(stop_times), trip_id)
            
            if not stop_times:
                _LOGGER.warning("No stop times found for trip %s", trip_id)
                return []
            
            # Get stop details
            all_stops = await self.get_stops()
            stops_dict = {str(stop["stop_id"]): stop for stop in all_stops}
            _LOGGER.debug("Loaded %d total stops for lookup", len(stops_dict))
            
            # Build stop pattern with details
            stop_pattern = []
            for stop_time in stop_times:
                stop_id = str(stop_time["stop_id"])
                if stop_id in stops_dict:
                    stop_info = stops_dict[stop_id].copy()
                    stop_info.update({
                        "stop_sequence": stop_time["stop_sequence"],
                        "arrival_time": stop_time.get("arrival_time"),
                        "departure_time": stop_time.get("departure_time"),
                    })
                    stop_pattern.append(stop_info)
                else:
                    _LOGGER.warning("Stop %s not found in stops dictionary", stop_id)
            
            _LOGGER.debug("Built stop pattern with %d stops", len(stop_pattern))
            # Cache
            self._stop_pattern_cache[cache_key] = (now, stop_pattern)
            return stop_pattern
            
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to get stop pattern for route %s direction %s: %s", route_id, direction_id, exc)
            raise

    async def get_stops(self) -> list[dict[str, Any]]:
        """Get all stops."""
        try:
            now = datetime.now()
            if self._stops_cache is not None and self._stops_cache_ts and (now - self._stops_cache_ts).total_seconds() < self._static_cache_ttl_seconds:
                return self._stops_cache
            data = await self._request(API_ENDPOINTS["stops"])
            if isinstance(data, list):
                self._stops_cache = data
                self._stops_cache_ts = now
            return data
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to fetch stops: %s", exc)
            raise

    async def get_calendar_dates(self) -> list[dict[str, Any]]:
        """Get calendar date overrides used for service validity."""
        try:
            now = datetime.now()
            if (
                self._calendar_dates_cache is not None
                and self._calendar_dates_cache_ts
                and (now - self._calendar_dates_cache_ts).total_seconds() < self._static_cache_ttl_seconds
            ):
                return self._calendar_dates_cache

            data = await self._request(API_ENDPOINTS["calendar_dates"])
            if isinstance(data, list):
                self._calendar_dates_cache = data
                self._calendar_dates_cache_ts = now
            return data if isinstance(data, list) else []
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to fetch calendar_dates: %s", exc)
            raise

    async def get_shapes(self, shape_id: str) -> list[dict[str, Any]]:
        """Get GTFS shape points for a specific shape_id."""
        try:
            shape_id = str(shape_id).strip()
            if not shape_id:
                return []

            now = datetime.now()
            cached = self._shapes_cache_by_id.get(shape_id)
            if cached and (now - cached[0]).total_seconds() < self._static_cache_ttl_seconds:
                return cached[1]

            endpoint = f"{API_ENDPOINTS['shapes']}?shape_id={quote(shape_id, safe='')}"
            data = await self._request(endpoint)
            rows = data if isinstance(data, list) else []
            self._shapes_cache_by_id[shape_id] = (now, rows)
            return rows
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to fetch shapes for shape_id %s: %s", shape_id, exc)
            raise

    async def get_route_geojson_feature(self, route_id: str) -> dict[str, Any] | None:
        """Build a GeoJSON feature for a single route.

        Prefer GTFS shapes when available; fall back to stop-pattern geometry.
        """
        route_id = str(route_id)
        now = datetime.now()
        cached = self._route_geometry_cache.get(route_id)
        if cached and (now - cached[0]).total_seconds() < self._static_cache_ttl_seconds:
            return cached[1]

        miss_ts = self._route_geometry_miss_cache.get(route_id)
        if miss_ts and (now - miss_ts).total_seconds() < NEGATIVE_ROUTE_GEOMETRY_CACHE_TTL_SECONDS:
            return None

        trips = await self.get_trips_for_route(route_id)
        if not trips:
            self._route_geometry_miss_cache[route_id] = now
            self._route_geometry_cache.pop(route_id, None)
            return None

        shape_ids: list[str] = []
        shape_id_set: set[str] = set()
        for trip in trips:
            shape_id = str(trip.get("shape_id", "")).strip()
            if not shape_id or shape_id in shape_id_set:
                continue
            shape_id_set.add(shape_id)
            shape_ids.append(shape_id)

        lines: list[list[list[float]]] = []
        if shape_ids:
            for shape_id in shape_ids:
                shape_rows = await self.get_shapes(shape_id)
                points: list[tuple[int, float, float]] = []
                for row in shape_rows:
                    if not isinstance(row, dict):
                        continue
                    try:
                        lat = float(row.get("shape_pt_lat"))
                        lon = float(row.get("shape_pt_lon"))
                        seq = int(row.get("shape_pt_sequence", 0) or 0)
                    except (TypeError, ValueError):
                        continue
                    points.append((seq, lat, lon))

                rows = sorted(points, key=lambda item: item[0])
                coords: list[list[float]] = []
                for _, lat, lon in rows:
                    point = [lon, lat]
                    if not coords or coords[-1] != point:
                        coords.append(point)
                if len(coords) >= 2:
                    lines.append(coords)

        if not lines:
            lines = await self._fallback_route_lines_from_stop_patterns(route_id)
        if not lines:
            self._route_geometry_miss_cache[route_id] = now
            self._route_geometry_cache.pop(route_id, None)
            return None

        route_short_name = await self._get_route_short_name(route_id)
        feature = {
            "type": "Feature",
            "properties": {
                "route_id": route_id,
                "route_short_name": route_short_name,
                "shape_count": len(lines),
            },
            "geometry": {
                "type": "MultiLineString" if len(lines) > 1 else "LineString",
                "coordinates": lines if len(lines) > 1 else lines[0],
            },
        }

        self._route_geometry_cache[route_id] = (now, feature)
        self._route_geometry_miss_cache.pop(route_id, None)
        return feature

    async def _fallback_route_lines_from_stop_patterns(self, route_id: str) -> list[list[list[float]]]:
        """Build route geometry lines from direction stop patterns as fallback."""
        lines: list[list[list[float]]] = []
        for direction_id in (0, 1):
            try:
                stops = await self.get_route_stop_pattern(route_id, direction_id)
            except MetlinkApiError:
                continue

            coords: list[list[float]] = []
            for stop in stops or []:
                if not isinstance(stop, dict):
                    continue
                lat = stop.get("stop_lat")
                lon = stop.get("stop_lon")
                try:
                    point = [float(lon), float(lat)]
                except (TypeError, ValueError):
                    continue
                if not coords or coords[-1] != point:
                    coords.append(point)

            if len(coords) >= 2:
                lines.append(coords)

        return lines

    async def get_mode_routes_geojson(self, route_ids: list[str]) -> dict[str, Any]:
        """Build a GeoJSON feature collection for the provided mode routes."""
        features: list[dict[str, Any]] = []
        for route_id in route_ids:
            try:
                feature = await self.get_route_geojson_feature(str(route_id))
            except MetlinkApiError:
                feature = None
            if feature:
                features.append(feature)

        if self._transportation_type == TRAIN_ROUTE_TYPE and features:
            features = self._apply_train_overlap_offsets(features)

        return {
            "type": "FeatureCollection",
            "features": features,
            "route_count": len(route_ids),
            "feature_count": len(features),
        }

    def _apply_train_overlap_offsets(self, features: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply point-level east/west offsets to overlapping train routes.

        Offsets are applied only to coordinates shared by more than one route,
        keeping single-line track sections on native coordinates.
        """
        point_routes: dict[tuple[float, float], set[str]] = {}

        for feature in features:
            props = feature.get("properties", {}) if isinstance(feature, dict) else {}
            route_short_name = str((props or {}).get("route_short_name", "")).strip().upper()
            if not route_short_name:
                continue
            for lon, lat in self._iter_feature_points(feature):
                key = self._point_key(lon, lat)
                point_routes.setdefault(key, set()).add(route_short_name)

        adjusted_features: list[dict[str, Any]] = []
        for feature in features:
            if not isinstance(feature, dict):
                adjusted_features.append(feature)
                continue

            props = feature.get("properties", {}) if isinstance(feature, dict) else {}
            route_short_name = str((props or {}).get("route_short_name", "")).strip().upper()
            if not route_short_name:
                adjusted_features.append(feature)
                continue

            geometry = feature.get("geometry", {})
            if not isinstance(geometry, dict):
                adjusted_features.append(feature)
                continue

            geometry_type = geometry.get("type")
            coordinates = geometry.get("coordinates")
            if geometry_type == "LineString":
                new_coords = self._offset_line_coords(coordinates, route_short_name, point_routes)
            elif geometry_type == "MultiLineString":
                new_coords = [
                    self._offset_line_coords(line, route_short_name, point_routes)
                    for line in (coordinates or [])
                    if isinstance(line, list)
                ]
            else:
                adjusted_features.append(feature)
                continue

            new_feature = {
                **feature,
                "geometry": {
                    **geometry,
                    "coordinates": new_coords,
                },
            }
            adjusted_features.append(new_feature)

        return adjusted_features

    def _iter_feature_points(self, feature: dict[str, Any]) -> list[tuple[float, float]]:
        """Return all (lon, lat) points from a GeoJSON feature geometry."""
        geometry = feature.get("geometry", {})
        if not isinstance(geometry, dict):
            return []

        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")
        points: list[tuple[float, float]] = []

        if geometry_type == "LineString" and isinstance(coordinates, list):
            for point in coordinates:
                if not isinstance(point, list) or len(point) < 2:
                    continue
                try:
                    points.append((float(point[0]), float(point[1])))
                except (TypeError, ValueError):
                    continue
        elif geometry_type == "MultiLineString" and isinstance(coordinates, list):
            for line in coordinates:
                if not isinstance(line, list):
                    continue
                for point in line:
                    if not isinstance(point, list) or len(point) < 2:
                        continue
                    try:
                        points.append((float(point[0]), float(point[1])))
                    except (TypeError, ValueError):
                        continue

        return points

    def _offset_line_coords(
        self,
        coords: Any,
        route_short_name: str,
        point_routes: dict[tuple[float, float], set[str]],
    ) -> list[list[float]]:
        """Offset coordinates in a line based on overlap lane placement rules."""
        if not isinstance(coords, list):
            return []

        shifted: list[list[float]] = []
        for point in coords:
            if not isinstance(point, list) or len(point) < 2:
                continue

            try:
                lon = float(point[0])
                lat = float(point[1])
            except (TypeError, ValueError):
                continue

            key = self._point_key(lon, lat)
            overlapping_routes = point_routes.get(key, set())
            if len(overlapping_routes) <= 1:
                shifted.append([lon, lat])
                continue

            lane_step = self._lane_step_for_route(route_short_name, overlapping_routes)
            if lane_step == 0:
                shifted.append([lon, lat])
                continue

            meters_per_lon_degree = 111320.0 * max(0.2, math.cos(math.radians(lat)))
            lon_offset = (TRAIN_OVERLAP_OFFSET_METERS * lane_step) / meters_per_lon_degree
            shifted.append([lon + lon_offset, lat])

        return shifted

    def _lane_step_for_route(self, route_short_name: str, overlapping_routes: set[str]) -> int:
        """Return lane step where negative is west and positive is east."""
        name = route_short_name.upper()
        routes = {r.upper() for r in overlapping_routes}

        steps: dict[str, int] = {}
        mel_present = "MEL" in routes
        hvl_present = "HVL" in routes
        kpl_present = "KPL" in routes
        jvl_present = "JVL" in routes
        wrl_present = "WRL" in routes

        if mel_present:
            steps["MEL"] = 0
            if kpl_present:
                steps["KPL"] = -1
                if jvl_present:
                    steps["JVL"] = -2
                if hvl_present:
                    steps["HVL"] = 1
                    if wrl_present:
                        steps["WRL"] = 2
                elif wrl_present:
                    steps["WRL"] = 1
            else:
                # Special case: if KPL is missing, WRL moves west of MEL.
                if wrl_present:
                    steps["WRL"] = -1
                if jvl_present:
                    steps["JVL"] = -2 if wrl_present else -1
                if hvl_present:
                    steps["HVL"] = 1
        else:
            # Special case: if MEL is missing, HVL is centered when present.
            if hvl_present:
                steps["HVL"] = 0
            if wrl_present:
                steps["WRL"] = 1 if hvl_present else 0
            if kpl_present:
                steps["KPL"] = -1 if hvl_present else 0
            if jvl_present:
                if kpl_present:
                    steps["JVL"] = steps["KPL"] - 1
                elif hvl_present:
                    steps["JVL"] = -1
                else:
                    steps["JVL"] = 0

        return steps.get(name, 0)

    def _point_key(self, lon: float, lat: float) -> tuple[float, float]:
        """Normalize a coordinate to stable key precision for overlap matching."""
        return (round(lon, 6), round(lat, 6))

    async def get_route_timetable_rows(
        self,
        route_id: str,
        service_date: str | None = None,
        trip_updates_payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Build timetable rows for a route from trips+stop_times for a service date.

        Rows are sorted chronologically and realtime updates are overlaid when available.
        """
        date_str = service_date or datetime.now().strftime("%Y%m%d")
        cache_key = (str(route_id), date_str)
        now = datetime.now()

        if cache_key in self._route_timetable_cache:
            ts, cached_rows = self._route_timetable_cache[cache_key]
            if (now - ts).total_seconds() < self._static_cache_ttl_seconds:
                base_rows = [row.copy() for row in cached_rows]
            else:
                base_rows = await self._build_route_timetable_base_rows(str(route_id), date_str)
                self._route_timetable_cache[cache_key] = (now, [row.copy() for row in base_rows])
        else:
            base_rows = await self._build_route_timetable_base_rows(str(route_id), date_str)
            self._route_timetable_cache[cache_key] = (now, [row.copy() for row in base_rows])

        return self._overlay_realtime_on_rows(base_rows, trip_updates_payload)

    async def _build_route_timetable_base_rows(self, route_id: str, date_str: str) -> list[dict[str, Any]]:
        """Build scheduled route timetable rows for the given service date."""
        trips = await self.get_trips_for_route(route_id)
        if not trips:
            return []

        try:
            calendar_dates = await self.get_calendar_dates()
        except MetlinkApiError:
            calendar_dates = []

        trips_for_date = self._filter_trips_for_service_date(trips, calendar_dates, date_str)
        if not trips_for_date:
            # Fallback: if service-date filtering removes everything, keep all route trips.
            trips_for_date = trips

        stops = await self.get_stops()
        stop_name_by_id = {str(s.get("stop_id")): s.get("stop_name", "Unknown Stop") for s in stops}

        sem = asyncio.Semaphore(8)

        async def fetch_trip_stop_times(trip: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
            async with sem:
                trip_id = str(trip.get("trip_id"))
                stop_times = await self.get_stop_times_for_trip(trip_id)
                return trip, stop_times

        trip_and_stop_times = await asyncio.gather(
            *(fetch_trip_stop_times(trip) for trip in trips_for_date),
            return_exceptions=False,
        )

        rows: list[dict[str, Any]] = []
        for trip, stop_times in trip_and_stop_times:
            if not stop_times:
                continue

            last = stop_times[-1]
            destination_stop_id = str(last.get("stop_id"))
            destination_name = stop_name_by_id.get(destination_stop_id, "Unknown Stop")

            trip_id = str(trip.get("trip_id"))
            service_id = str(trip.get("service_id", ""))
            direction_id = trip.get("direction_id")

            for st in stop_times:
                stop_id = str(st.get("stop_id"))
                # Departure boards should only include true departure events.
                dep_time = st.get("departure_time")
                # Some non-train feeds only populate arrival_time at stops.
                if not dep_time and self._transportation_type != TRAIN_ROUTE_TYPE:
                    dep_time = st.get("arrival_time")
                if not dep_time:
                    continue
                # Exclude terminal-stop rows where service ends at this stop.
                if self._transportation_type == TRAIN_ROUTE_TYPE and stop_id == destination_stop_id:
                    continue
                rows.append(
                    {
                        "route_id": str(route_id),
                        "trip_id": trip_id,
                        "service_id": service_id,
                        "service_date": date_str,
                        "direction_id": direction_id,
                        "stop_id": stop_id,
                        "stop_name": stop_name_by_id.get(stop_id, "Unknown Stop"),
                        "stop_sequence": st.get("stop_sequence"),
                        "destination": destination_name,
                        "scheduled_departure_time": dep_time,
                        "departure_time": dep_time,
                        "eta_display": f"Scheduled: {dep_time}",
                        "is_realtime": False,
                        "time_source": "scheduled",
                        "debug_source": "gtfs_stop_times",
                    }
                )

        rows.sort(key=lambda r: self._seconds_for_service_time(r.get("scheduled_departure_time")))
        return rows

    def _filter_trips_for_service_date(
        self,
        trips: list[dict[str, Any]],
        calendar_dates: list[dict[str, Any]],
        date_str: str,
    ) -> list[dict[str, Any]]:
        """Filter trips by service_date using calendar_dates exceptions."""
        if not calendar_dates:
            return trips

        active_service_ids: set[str] = set()
        removed_service_ids: set[str] = set()
        for row in calendar_dates:
            if str(row.get("date")) != str(date_str):
                continue
            service_id = str(row.get("service_id", ""))
            exception_type = int(row.get("exception_type", 0) or 0)
            if exception_type == 1:
                active_service_ids.add(service_id)
            elif exception_type == 2:
                removed_service_ids.add(service_id)

        filtered = []
        for trip in trips:
            sid = str(trip.get("service_id", ""))
            if sid in removed_service_ids:
                continue
            # Non-train feeds may provide sparse active exceptions; keep trips
            # unless they are explicitly removed.
            if (
                self._transportation_type == TRAIN_ROUTE_TYPE
                and active_service_ids
                and sid not in active_service_ids
            ):
                continue
            filtered.append(trip)
        return filtered

    def _overlay_realtime_on_rows(
        self,
        rows: list[dict[str, Any]],
        trip_updates_payload: dict[str, Any] | list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        """Overlay GTFS-RT trip update times onto scheduled rows."""
        result = [row.copy() for row in rows]
        if not trip_updates_payload:
            return result

        if isinstance(trip_updates_payload, dict):
            entities = trip_updates_payload.get("entity", [])
        elif isinstance(trip_updates_payload, list):
            entities = trip_updates_payload
        else:
            return result

        rt_map: dict[tuple[str, str], dict[str, Any]] = {}
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            trip_update = entity.get("trip_update", {})
            if not isinstance(trip_update, dict):
                continue
            trip_id = str((trip_update.get("trip") or {}).get("trip_id", ""))
            for stu in trip_update.get("stop_time_update", []) or []:
                if not isinstance(stu, dict):
                    continue
                stop_id = str(stu.get("stop_id", ""))
                dep = stu.get("departure", {})
                if not isinstance(dep, dict) or not dep.get("time"):
                    continue
                timestamp = int(dep.get("time"))
                delay = int(dep.get("delay", 0) or 0)
                formatted = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
                rt_map[(trip_id, stop_id)] = {
                    "departure_time": formatted,
                    "timestamp": timestamp,
                    "delay_seconds": delay,
                }

        for row in result:
            key = (str(row.get("trip_id", "")), str(row.get("stop_id", "")))
            rt = rt_map.get(key)
            if not rt:
                continue
            row["departure_time"] = rt["departure_time"]
            row["eta_display"] = rt["departure_time"]
            row["is_realtime"] = True
            row["time_source"] = "trip_update"
            row["realtime_timestamp"] = rt["timestamp"]
            row["delay_seconds"] = rt["delay_seconds"]
            row["debug_source"] = "gtfs_rt_trip_updates"

        result.sort(key=lambda r: self._seconds_for_service_time(r.get("departure_time")))
        return result

    def _seconds_for_service_time(self, value: str | None) -> int:
        """Convert HH:MM(:SS) service time to sortable seconds (supports 24+ hours)."""
        if not value:
            return 10**9
        text = str(value).strip()
        if text.startswith("Scheduled:"):
            text = text.replace("Scheduled:", "").strip()
        parts = text.split(":")
        if len(parts) < 2:
            return 10**9
        try:
            hh = int(parts[0])
            mm = int(parts[1])
            ss = int(parts[2]) if len(parts) > 2 else 0
            return hh * 3600 + mm * 60 + ss
        except ValueError:
            return 10**9

    async def get_vehicle_positions(self) -> list[dict[str, Any]]:
        """Get real-time vehicle positions."""
        try:
            return await self._request(API_ENDPOINTS["vehicle_positions"])
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to fetch vehicle positions: %s", exc)
            raise

    async def get_trip_updates(self) -> list[dict[str, Any]]:
        """Get real-time trip updates."""
        try:
            return await self._request(API_ENDPOINTS["trip_updates"])
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to fetch trip updates: %s", exc)
            raise

    async def get_stop_predictions(self, stop_id: str | None = None) -> list[dict[str, Any]]:
        """Get stop departure predictions for a specific stop."""
        try:
            url = f"{self._base_url}/stop-predictions"
            params = {"stop_id": stop_id} if stop_id else {}
            headers = {"X-API-KEY": self._api_key}
        
            _LOGGER.debug("Fetching stop predictions from %s with params %s", url, params)
        
            async with self._session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    _LOGGER.debug("Got %d predictions for stop %s", len(data) if isinstance(data, list) else 0, stop_id)
                    return data if isinstance(data, list) else []
                else:
                    _LOGGER.warning("Stop predictions request failed with status %d for stop %s", response.status, stop_id)
                    return []
                
        except Exception as exc:
            _LOGGER.error("Failed to get stop predictions for stop %s: %s", stop_id, exc)
            return []

    async def _batch_get_stop_predictions(self, stop_ids: list[str], concurrency: int = 6) -> dict[str, list[dict[str, Any]]]:
        """Fetch predictions for many stops concurrently with a concurrency limit.

        Returns a mapping of stop_id -> predictions list.
        """
        results: dict[str, list[dict[str, Any]]] = {}
        sem = asyncio.Semaphore(max(1, concurrency))

        async def fetch_one(sid: str) -> None:
            async with sem:
                preds = await self.get_stop_predictions(sid)
                results[sid] = preds if isinstance(preds, list) else []

        await asyncio.gather(*(fetch_one(s) for s in stop_ids))
        return results

    async def get_route_stop_predictions(self, route_id: str, direction_id: int) -> dict[str, Any]:
        """Get real-time predictions for all stops on a route using trip updates."""
        try:
            _LOGGER.debug("Getting route stop predictions for route %s direction %s", route_id, direction_id)
            
            # Get the stop pattern for this route/direction
            stop_pattern = await self.get_route_stop_pattern(route_id, direction_id)
            
            if not stop_pattern:
                _LOGGER.warning("No stop pattern found for route %s direction %s", route_id, direction_id)
                return {
                    "stops": {},
                    "destination": None,
                    "stop_count": 0
                }
            
            _LOGGER.info("Processing %d stops in pattern for route %s direction %s", 
                        len(stop_pattern), route_id, direction_id)
            
            # Get destination (last stop in the pattern)
            destination_stop = stop_pattern[-1] if stop_pattern else None
            
            # Get real-time trip updates
            trip_updates = await self.get_trip_updates()
            _LOGGER.debug("Found %d trip updates", len(trip_updates))
            
            # Get trips for our route to match trip IDs
            trips = await self.get_trips_for_route(route_id)
            direction_trips = [t for t in trips if t.get("direction_id") == direction_id]
            trip_ids = {trip["trip_id"] for trip in direction_trips}
            _LOGGER.debug("Looking for trip updates matching %d trip IDs", len(trip_ids))
            
            # Process trip updates to get real-time predictions
            stop_predictions = {}
            
            # Initialize all stops with empty predictions
            for stop in stop_pattern:
                stop_id = str(stop["stop_id"])
                stop_predictions[stop_id] = {
                    "stop_info": stop,
                    "predictions": []
                }
            
            # Process trip updates
            if isinstance(trip_updates, dict) and "entity" in trip_updates:
                entities = trip_updates["entity"]
            elif isinstance(trip_updates, list):
                entities = trip_updates
            else:
                _LOGGER.warning("Unexpected trip_updates format: %s", type(trip_updates))
                entities = []
            
            real_time_found = 0
            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                    
                trip_update = entity.get("trip_update", {})
                if not trip_update:
                    continue
                
                trip_info = trip_update.get("trip", {})
                trip_id = trip_info.get("trip_id")
                
                # Check if this trip belongs to our route/direction
                if trip_id not in trip_ids:
                    continue
                
                stop_time_updates = trip_update.get("stop_time_update", [])
                _LOGGER.debug("Processing trip %s with %d stop updates", trip_id, len(stop_time_updates))
                
                for stop_update in stop_time_updates:
                    stop_id = str(stop_update.get("stop_id", ""))
                    if stop_id in stop_predictions:
                        # Extract departure info
                        departure_info = stop_update.get("departure", {})
                        if departure_info:
                            # Convert Unix timestamp to readable time
                            time_stamp = departure_info.get("time")
                            delay = departure_info.get("delay", 0)
                            
                            if time_stamp:
                                try:
                                    # Convert Unix timestamp to local time
                                    dt = datetime.fromtimestamp(int(time_stamp))
                                    formatted_time = dt.strftime("%H:%M:%S")
                                    
                                    prediction = {
                                        "departure_time": formatted_time,
                                        "expected_departure_time": formatted_time,
                                        "delay_seconds": delay,
                                        "trip_id": trip_id,
                                        "timestamp": time_stamp,
                                        "is_real_time": True
                                    }
                                    
                                    stop_predictions[stop_id]["predictions"].append(prediction)
                                    real_time_found += 1
                                    
                                except (ValueError, TypeError) as e:
                                    _LOGGER.debug("Could not parse timestamp %s: %s", time_stamp, e)
            
            _LOGGER.debug("Found %d real-time predictions across all stops", real_time_found)
            
            return {
                "stops": stop_predictions,
                "destination": destination_stop,
                "stop_count": len(stop_pattern)
            }
            
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to get route stop predictions for route %s direction %s: %s", 
                         route_id, direction_id, exc)
            raise

    async def get_route_timeline_for_card(self, route_id: str, direction_id: int) -> dict[str, Any]:
        """Get route timeline data optimized for Home Assistant card display using stop predictions."""
        try:
            _LOGGER.info("Getting route timeline for card display: route %s direction %s", route_id, direction_id)
            
            # Step 1: Get the static stop pattern from GTFS data
            stop_pattern = await self.get_route_stop_pattern(route_id, direction_id)
            if not stop_pattern:
                _LOGGER.error("No stop pattern found for route %s direction %s", route_id, direction_id)
                return {"stops": [], "error": "No stop pattern found"}
            
            _LOGGER.info("Found stop pattern with %d stops", len(stop_pattern))
            
            # Step 2: Get real-time predictions using the stop-predictions endpoint (batched)
            timeline_stops = []
            current_time = datetime.now()
            current_time_str = current_time.strftime("%H:%M:%S")
            # Resolve route short name once and cache
            route_short_name = await self._get_route_short_name(route_id)
            stop_ids = [str(s.get("stop_id")) for s in stop_pattern if s.get("stop_id") is not None]
            predictions_by_stop = await self._batch_get_stop_predictions(stop_ids, concurrency=6)
            # Prepare GTFS-RT trip updates as a fallback source
            fallback_rt = {}
            try:
                rt = await self.get_route_stop_predictions(route_id, direction_id)
                if isinstance(rt, dict):
                    fallback_rt = rt.get("stops", {}) or {}
            except Exception as ex:
                _LOGGER.debug("Trip updates fallback not available: %s", ex)
            
            for stop_info in stop_pattern:
                stop_id = str(stop_info["stop_id"])
                
                # Get real-time predictions for this stop
                raw_preds = predictions_by_stop.get(stop_id, [])
                # Filter for our specific route and direction; accept missing direction_id
                relevant_predictions = [
                    p for p in raw_preds
                    if self._prediction_matches_route(p, route_id, route_short_name)
                    and (p.get("direction_id") == direction_id or p.get("direction_id") in (None, "", "nn"))
                ]
                # Sort predictions by normalized departure time and take the next few
                predictions = sorted(
                    relevant_predictions,
                    key=lambda x: self._normalize_time_str(
                        x.get("departure_time") or x.get("expected_departure_time") or "99:99:99"
                    )
                )[:3]
                time_source = None
                if predictions:
                    time_source = "realtime"
                else:
                    fb_entry = fallback_rt.get(stop_id, {}) if isinstance(fallback_rt, dict) else {}
                    fb_preds = fb_entry.get("predictions", []) if isinstance(fb_entry, dict) else []
                    if fb_preds:
                        predictions = sorted(
                            fb_preds,
                            key=lambda x: self._normalize_time_str(
                                x.get("departure_time") or x.get("expected_departure_time") or "99:99:99"
                            )
                        )[:3]
                        if predictions:
                            time_source = "trip_update"
                
                # Calculate ETA for the next departure
                eta_display = "No predictions"
                eta_seconds = 0
                next_departure = None
                
                if predictions:
                    next_pred = predictions[0]
                    departure_time = next_pred.get("departure_time") or next_pred.get("expected_departure_time")
                    
                    if departure_time:
                        eta_display, eta_seconds = self._eta_from_time_str(departure_time, current_time)
                        next_departure = self._normalize_time_str(departure_time)
                
                # Use scheduled time as fallback
                if not next_departure:
                    scheduled_time = stop_info.get("departure_time", stop_info.get("arrival_time"))
                    if scheduled_time:
                        eta_display = f"Scheduled: {scheduled_time}"
                        next_departure = scheduled_time
                        if not time_source:
                            time_source = "scheduled"
                
                timeline_stop = {
                    "stop_id": stop_id,
                    "stop_name": stop_info.get("stop_name", "Unknown Stop"),
                    "stop_sequence": stop_info.get("stop_sequence", 0),
                    "scheduled_time": stop_info.get("departure_time", stop_info.get("arrival_time")),
                    "next_departure": next_departure,
                    "eta_display": eta_display,
                    "eta_seconds": eta_seconds,
                    "time_source": time_source,
                    "prediction_count": len(predictions),
                    "has_real_time": len(predictions) > 0,
                    "stop_lat": stop_info.get("stop_lat"),
                    "stop_lon": stop_info.get("stop_lon"),
                    "is_departure": stop_info.get("stop_sequence", 0) == 0,
                    "is_destination": stop_info.get("stop_sequence", 0) == len(stop_pattern) - 1,
                    "is_hub": self._is_hub_stop(stop_info.get("stop_name", "")),
                    "all_predictions": predictions,  # Include all predictions for debugging
                }
                timeline_stops.append(timeline_stop)
            
            # Sort by stop sequence
            timeline_stops.sort(key=lambda x: x["stop_sequence"])
            
            _LOGGER.info("Built timeline with %d stops, %d with real-time data", 
                        len(timeline_stops), 
                        sum(1 for s in timeline_stops if s["has_real_time"]))
            
            return {
                "stops": timeline_stops,
                "route_id": route_id,
                "direction_id": direction_id,
                "current_time": current_time_str,
                "total_stops": len(timeline_stops),
                "departure_stop": timeline_stops[0] if timeline_stops else None,
                "destination_stop": timeline_stops[-1] if timeline_stops else None,
                "hub_stops": [s for s in timeline_stops if s["is_hub"]],
                "real_time_stops": sum(1 for s in timeline_stops if s["has_real_time"]),
                "error": None
            }
            
        except Exception as exc:
            _LOGGER.error("Failed to get route timeline for route %s direction %s: %s", 
                         route_id, direction_id, exc, exc_info=True)
            return {"stops": [], "error": str(exc)}
    
    async def _get_route_short_name(self, route_id: str) -> str:
        """Get route short name for a given route ID with simple caching."""
        rid = str(route_id)
        if rid in self._route_short_name_cache:
            return self._route_short_name_cache[rid]
        try:
            routes = await self.get_routes()
            for r in routes or []:
                rid_str = str(r.get("route_id"))
                self._route_short_name_cache[rid_str] = r.get("route_short_name", "") or ""
            return self._route_short_name_cache.get(rid, "")
        except Exception:
            return ""
    
    def _is_hub_stop(self, stop_name: str) -> bool:
        """Identify if a stop is a major hub/interchange."""
        hub_keywords = [
            "station", "interchange", "terminal", "centre", "plaza", 
            "wellington", "petone", "lower hutt", "upper hutt", "masterton",
            "johnsonville", "porirua", "paraparaumu", "waikanae"
        ]
        stop_name_lower = stop_name.lower()
        return any(keyword in stop_name_lower for keyword in hub_keywords)

    def _normalize_time_str(self, time_str: str | None) -> str:
        """Normalize a time string to HH:MM:SS for consistent sorting/formatting."""
        if not time_str:
            return ""
        s = str(time_str).strip()
        # Handle HH:MM
        if len(s) == 5 and s.count(":") == 1:
            return f"{s}:00"
        # Handle values >= 24 hours (e.g., 25:30:00) by wrapping to next day for display
        try:
            hours, minutes, seconds = [int(x) for x in s.split(":")]
            if hours >= 24:
                hours = hours - 24
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except Exception:
            pass
        return s

    def _eta_from_time_str(self, time_str: str, now: datetime) -> tuple[str, int]:
        """Compute human-friendly ETA text and seconds from a local time string."""
        ts = self._normalize_time_str(time_str)
        try:
            departure_dt = datetime.strptime(f"{now.date()} {ts}", "%Y-%m-%d %H:%M:%S")
            if departure_dt < now:
                departure_dt += timedelta(days=1)
            eta_seconds = int((departure_dt - now).total_seconds())
        except Exception:
            return ts or "", 0

        if eta_seconds <= 0:
            return "Due now", eta_seconds
        minutes = eta_seconds // 60
        seconds = eta_seconds % 60
        if eta_seconds < 60:
            return f"{eta_seconds}s", eta_seconds
        if minutes < 60:
            return f"{minutes}m {seconds}s", eta_seconds
        hours = minutes // 60
        rem_min = minutes % 60
        return f"{hours}h {rem_min}m", eta_seconds

    def _prediction_matches_route(self, pred: dict[str, Any], route_id: str, route_short_name: str) -> bool:
        """Match prediction to route by id or short name (case/format tolerant)."""
        try:
            rid_match = str(pred.get("route_id")) == str(route_id)
            rsn_pred = str(pred.get("route_short_name", "")).strip().lower()
            rsn_ref = (route_short_name or "").strip().lower()
            rsn_match = rsn_pred == rsn_ref and rsn_ref != ""
            return rid_match or rsn_match
        except Exception:
            return False