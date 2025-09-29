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

    async def get_stop_times_for_trip(self, trip_id: str) -> list[dict[str, Any]]:
        """Get stop times for a specific trip to understand stop sequence."""
        try:
            stop_times = await self._request(API_ENDPOINTS["stop_times"])
            trip_stop_times = [st for st in stop_times if st.get("trip_id") == trip_id]
            # Sort by stop_sequence to get the correct order
            return sorted(trip_stop_times, key=lambda x: x.get("stop_sequence", 0))
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to fetch stop times for trip %s: %s", trip_id, exc)
            raise

    async def get_route_stop_pattern(self, route_id: str, direction_id: int) -> list[dict[str, Any]]:
        """Get the stop pattern for a route in a specific direction."""
        try:
            # Get trips for this route and direction
            trips = await self.get_trips_for_route(route_id)
            direction_trips = [t for t in trips if t.get("direction_id") == direction_id]
            
            if not direction_trips:
                _LOGGER.warning("No trips found for route %s direction %s", route_id, direction_id)
                return []
            
            # Use the first trip to get the stop pattern
            # In a real implementation, you might want to check multiple trips to ensure consistency
            sample_trip = direction_trips[0]
            trip_id = sample_trip["trip_id"]
            
            # Get stop times for this trip
            stop_times = await self.get_stop_times_for_trip(trip_id)
            
            # Get stop details
            all_stops = await self.get_stops()
            stops_dict = {stop["stop_id"]: stop for stop in all_stops}
            
            # Build stop pattern with details
            stop_pattern = []
            for stop_time in stop_times:
                stop_id = stop_time["stop_id"]
                if stop_id in stops_dict:
                    stop_info = stops_dict[stop_id].copy()
                    stop_info.update({
                        "stop_sequence": stop_time["stop_sequence"],
                        "arrival_time": stop_time.get("arrival_time"),
                        "departure_time": stop_time.get("departure_time"),
                    })
                    stop_pattern.append(stop_info)
            
            return stop_pattern
            
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to get stop pattern for route %s direction %s: %s", route_id, direction_id, exc)
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

    async def get_route_stop_predictions(self, route_id: str, direction_id: int) -> dict[str, Any]:
        """Get real-time predictions for all stops on a route in a specific direction."""
        try:
            # Get the stop pattern for this route/direction
            stop_pattern = await self.get_route_stop_pattern(route_id, direction_id)
            
            if not stop_pattern:
                return {"stops": [], "destination": None}
            
            # Get destination (last stop in the pattern)
            destination_stop = stop_pattern[-1] if stop_pattern else None
            
            # Get predictions for each stop on the route
            stop_predictions = {}
            for stop in stop_pattern:
                stop_id = stop["stop_id"]
                try:
                    predictions = await self.get_stop_predictions(stop_id)
                    # Filter predictions for our specific route
                    route_predictions = [
                        pred for pred in predictions 
                        if pred.get("route_id") == route_id and pred.get("direction_id") == direction_id
                    ]
                    stop_predictions[stop_id] = {
                        "stop_info": stop,
                        "predictions": route_predictions[:3]  # Limit to next 3 departures
                    }
                except MetlinkApiError:
                    # If we can't get predictions for this stop, continue with others
                    stop_predictions[stop_id] = {
                        "stop_info": stop,
                        "predictions": []
                    }
            
            return {
                "stops": stop_predictions,
                "destination": destination_stop,
                "stop_count": len(stop_pattern)
            }
            
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to get route stop predictions for route %s direction %s: %s", route_id, direction_id, exc)
            raise