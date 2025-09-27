"""API client for Metlink Open Data."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import async_timeout

from .const import BASE_URL, API_ENDPOINTS, REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class MetlinkApiError(Exception):
    """Exception to indicate a general API error."""


class MetlinkApiClient:
    """Client for interacting with Metlink Open Data API."""

    def __init__(self, api_key: str, session: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self._api_key = api_key
        self._session = session
        self._base_url = BASE_URL

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
            return await self._request(API_ENDPOINTS["routes"])
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
            trips = await self._request(API_ENDPOINTS["trips"])
            return [trip for trip in trips if trip.get("route_id") == route_id]
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to fetch trips for route %s: %s", route_id, exc)
            raise

    async def get_stops(self) -> list[dict[str, Any]]:
        """Get all stops."""
        try:
            return await self._request(API_ENDPOINTS["stops"])
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to fetch stops: %s", exc)
            raise

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
        """Get stop departure predictions."""
        endpoint = API_ENDPOINTS["stop_predictions"]
        if stop_id:
            endpoint += f"?stop_id={stop_id}"
        
        try:
            return await self._request(endpoint)
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to fetch stop predictions: %s", exc)
            raise