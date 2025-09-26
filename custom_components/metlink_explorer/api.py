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

    async def get_route_stops(self, route_id: str) -> dict[int, list[dict[str, Any]]]:
        """Get stops for a route organized by direction."""
        # Get all trips for this route
        trips = await self._request(f"gtfs/trips?route_id={route_id}")
        
        # Get stop times for each trip to build stop sequences
        direction_stops = {0: [], 1: []}  # direction_id -> list of stops
        
        # Process a few trips from each direction to get representative stop sequences
        processed_directions = set()
        
        for trip in trips:
            direction_id = trip.get("direction_id")
            if direction_id is None or direction_id in processed_directions:
                continue
                
            trip_id = trip.get("trip_id")
            if not trip_id:
                continue
                
            # Get stop times for this trip
            stop_times = await self._request(f"gtfs/stop_times?trip_id={trip_id}")
            
            # Sort by stop_sequence to get correct order
            stop_times.sort(key=lambda x: x.get("stop_sequence", 0))
            
            # Get stop details for each stop in the sequence
            stops_in_sequence = []
            for stop_time in stop_times:
                stop_id = stop_time.get("stop_id")
                if stop_id:
                    # Get stop details
                    stops = await self.get_stops()
                    stop_info = next((s for s in stops if s.get("stop_id") == stop_id), None)
                    
                    if stop_info:
                        stops_in_sequence.append({
                            "stop_id": stop_id,
                            "stop_name": stop_info.get("stop_name", ""),
                            "stop_sequence": stop_time.get("stop_sequence", 0),
                            "stop_lat": stop_info.get("stop_lat"),
                            "stop_lon": stop_info.get("stop_lon"),
                            "zone_id": stop_info.get("zone_id"),
                            "stop_code": stop_info.get("stop_code"),
                        })
            
            direction_stops[direction_id] = stops_in_sequence
            processed_directions.add(direction_id)
            
            # Break if we've processed both directions
            if len(processed_directions) >= 2:
                break
        
        return direction_stops

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

    async def get_route_departures(self, route_id: str, direction_id: int = None, limit: int = 10) -> list[dict[str, Any]]:
        """Get next departures for a specific route and direction."""
        # Get stop sequences for this route
        route_stops = await self.get_route_stops(route_id)
        
        # If direction_id is specified, only get stops for that direction
        if direction_id is not None:
            target_stops = route_stops.get(direction_id, [])
        else:
            # Get stops from both directions
            target_stops = []
            for direction_stops in route_stops.values():
                target_stops.extend(direction_stops)
        
        # Get stop times for all stops in the route sequence
        all_departures = []
        for stop_info in target_stops:
            stop_id = stop_info["stop_id"]
            stop_times = await self.get_stop_times(stop_id)
            
            # Filter for this specific route and add stop/sequence info
            route_departures = [
                {
                    **st, 
                    "stop_name": stop_info["stop_name"],
                    "stop_id": stop_id,
                    "route_stop_sequence": stop_info["stop_sequence"],
                    "stop_lat": stop_info["stop_lat"],
                    "stop_lon": stop_info["stop_lon"],
                    "zone_id": stop_info["zone_id"],
                    "stop_code": stop_info["stop_code"],
                    "direction_id": direction_id if direction_id is not None else self._infer_direction_from_stops(stop_info, route_stops)
                }
                for st in stop_times 
                if st.get("route_id") == route_id
            ]
            all_departures.extend(route_departures)
        
        # Sort by departure time and return next departures
        now = datetime.now().time()
        
        # Filter for upcoming departures and sort
        upcoming = [
            dep for dep in all_departures 
            if self._parse_time(dep.get("departure_time", "")) > now
        ]
        upcoming.sort(key=lambda x: self._parse_time(x.get("departure_time", "")))
        
        return upcoming[:limit]
    
    def _infer_direction_from_stops(self, stop_info: dict, route_stops: dict) -> int:
        """Infer direction_id based on which direction's stop sequence contains this stop."""
        stop_id = stop_info["stop_id"]
        
        for direction_id, stops in route_stops.items():
            if any(stop["stop_id"] == stop_id for stop in stops):
                return direction_id
        
        return 0  # Default to direction 0
    
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