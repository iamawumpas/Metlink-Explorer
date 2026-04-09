"""Coordinator for route-centric Metlink updates."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MetlinkApiClient, MetlinkApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, TRAIN_GTFS_CACHE_TTL_SECONDS

_LOGGER = logging.getLogger(__name__)


class MetlinkDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and hold route-level data for both directions in one cycle."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: MetlinkApiClient,
        route_id: str,
    ) -> None:
        """Initialize route coordinator."""
        self.api_client = api_client
        self.route_id = str(route_id)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.route_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data for the route in both directions."""
        try:
            trips = await self.api_client.get_trips_for_route(self.route_id)
            vehicle_positions = await self.api_client.get_vehicle_positions()
            trip_updates = await self.api_client.get_trip_updates()
            timetable_rows = await self.api_client.get_route_timetable_rows(
                self.route_id,
                trip_updates_payload=trip_updates,
            )

            timeline_by_direction: dict[int, dict[str, Any]] = {}
            for direction_id in (0, 1):
                try:
                    timeline_by_direction[direction_id] = await self.api_client.get_route_timeline_for_card(
                        self.route_id,
                        direction_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.error(
                        "Failed to fetch timeline for route %s direction %s: %s",
                        self.route_id,
                        direction_id,
                        exc,
                    )
                    timeline_by_direction[direction_id] = {"stops": [], "error": str(exc)}

            return {
                "route_id": self.route_id,
                "trips": trips,
                "vehicle_positions": vehicle_positions,
                "trip_updates": trip_updates,
                "timetable_rows": timetable_rows,
                "timeline_by_direction": timeline_by_direction,
            }
        except MetlinkApiError as exc:
            raise UpdateFailed(f"Error communicating with API: {exc}") from exc


class MetlinkRouteGeometryCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and hold mode route geometry as GeoJSON."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: MetlinkApiClient,
        mode_key: str,
        route_ids: list[str],
    ) -> None:
        """Initialize mode route geometry coordinator."""
        self.api_client = api_client
        self.mode_key = mode_key
        self.route_ids = [str(route_id) for route_id in route_ids if route_id]

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{mode_key}_geometry",
            update_interval=timedelta(seconds=TRAIN_GTFS_CACHE_TTL_SECONDS),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update mode geometry from static GTFS shapes."""
        try:
            return await self.api_client.get_mode_routes_geojson(self.route_ids)
        except MetlinkApiError as exc:
            raise UpdateFailed(f"Error communicating with API: {exc}") from exc
