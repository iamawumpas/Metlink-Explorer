"""API client for Metlink Explorer."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_BASE_URL, API_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class MetlinkApiError(Exception):
    """Exception to indicate a general API error."""


class MetlinkApiClient:
    """API client for Metlink."""

    def __init__(self, hass: HomeAssistant, api_key: str) -> None:
        """Initialize the API client."""
        self._hass = hass
        self._api_key = api_key
        self._session = async_get_clientsession(hass)

    async def _request(self, endpoint: str) -> dict[str, Any]:
        """Make a request to the Metlink API."""
        url = f"{API_BASE_URL}/{endpoint}"
        headers = {
            "accept": "application/json",
            "x-api-key": self._api_key,
        }
        
        try:
            async with asyncio.timeout(API_TIMEOUT):
                async with self._session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    return await response.json()
        except aiohttp.ClientError as err:
            _LOGGER.error("Error communicating with Metlink API: %s", err)
            raise MetlinkApiError(f"Error communicating with API: {err}") from err
        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout communicating with Metlink API")
            raise MetlinkApiError("Timeout communicating with API") from err

    async def validate_api_key(self) -> bool:
        """Validate the API key by making a simple request."""
        try:
            await self._request("gtfs/agency")
            return True
        except MetlinkApiError:
            return False

    async def get_agencies(self) -> list[dict[str, Any]]:
        """Get all agencies."""
        return await self._request("gtfs/agency")

    async def get_routes(self, route_type: int | None = None) -> list[dict[str, Any]]:
        """Get all routes, optionally filtered by route type."""
        routes = await self._request("gtfs/routes")
        
        if route_type is not None:
            routes = [route for route in routes if route.get("route_type") == route_type]
            
        return routes

    async def get_route_by_id(self, route_id: str) -> dict[str, Any] | None:
        """Get a specific route by ID."""
        routes = await self.get_routes()
        for route in routes:
            if route.get("route_id") == route_id:
                return route
        return None

    async def get_stops(self) -> list[dict[str, Any]]:
        """Get all stops."""
        return await self._request("gtfs/stops")

    async def get_stop_times(self, stop_id: str) -> list[dict[str, Any]]:
        """Get stop times for a specific stop."""
        return await self._request(f"gtfs/stop_times?stop_id={stop_id}")

    async def get_trip_updates(self) -> list[dict[str, Any]]:
        """Get real-time trip updates."""
        response = await self._request("gtfs-rt/tripupdates")
        return response.get("entity", [])

    async def get_vehicle_positions(self) -> list[dict[str, Any]]:
        """Get real-time vehicle positions."""
        response = await self._request("gtfs-rt/vehiclepositions")
        return response.get("entity", [])

    async def get_service_alerts(self) -> list[dict[str, Any]]:
        """Get service alerts."""
        response = await self._request("gtfs-rt/servicealerts")
        return response.get("entity", [])

    async def get_route_departures(self, route_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get next departures for a specific route."""
        # Get all stops for this route first
        stops = await self.get_stops()
        route_stops = [stop for stop in stops if any(
            route.get("route_id") == route_id 
            for route in stop.get("routes", [])
        )]
        
        # Get stop times for all stops on this route
        all_departures = []
        for stop in route_stops:
            stop_times = await self.get_stop_times(stop["stop_id"])
            # Filter for this specific route and add stop info
            route_departures = [
                {**st, "stop_name": stop.get("stop_name", ""), "stop_id": stop["stop_id"]}
                for st in stop_times 
                if st.get("route_id") == route_id
            ]
            all_departures.extend(route_departures)
        
        # Sort by departure time and return next 10
        now = datetime.now().time()
        
        # Filter for upcoming departures and sort
        upcoming = [
            dep for dep in all_departures 
            if self._parse_time(dep.get("departure_time", "")) > now
        ]
        upcoming.sort(key=lambda x: self._parse_time(x.get("departure_time", "")))
        
        return upcoming[:limit]
    
    def _parse_time(self, time_str: str) -> time:
        """Parse time string in HH:MM:SS format."""
        try:
            if not time_str:
                return time.max
            parts = time_str.split(":")
            hour = int(parts[0]) % 24  # Handle 24+ hour format
            minute = int(parts[1])
            second = int(parts[2]) if len(parts) > 2 else 0
            return time(hour, minute, second)
        except (ValueError, IndexError):
            return time.max