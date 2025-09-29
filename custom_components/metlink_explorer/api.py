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
            _LOGGER.debug("Getting trips for route %s", route_id)
            trips = await self._request(API_ENDPOINTS["trips"])
            
            # Ensure route_id comparison handles both string and integer types
            route_trips = [
                trip for trip in trips 
                if str(trip.get("route_id")) == str(route_id)
            ]
            
            _LOGGER.debug("Found %d trips for route %s out of %d total trips", 
                         len(route_trips), route_id, len(trips))
            
            return route_trips
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to fetch trips for route %s: %s", route_id, exc)
            raise

    async def get_stop_times_for_trip(self, trip_id: str) -> list[dict[str, Any]]:
        """Get stop times for a specific trip to understand stop sequence."""
        try:
            _LOGGER.debug("Getting stop times for trip %s", trip_id)
            stop_times = await self._request(API_ENDPOINTS["stop_times"])
            
            trip_stop_times = [
                st for st in stop_times 
                if str(st.get("trip_id")) == str(trip_id)
            ]
            
            # Sort by stop_sequence to get the correct order
            sorted_stop_times = sorted(trip_stop_times, key=lambda x: x.get("stop_sequence", 0))
            
            _LOGGER.debug("Found %d stop times for trip %s", len(sorted_stop_times), trip_id)
            
            return sorted_stop_times
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to fetch stop times for trip %s: %s", trip_id, exc)
            raise

    async def get_route_stop_pattern(self, route_id: str, direction_id: int) -> list[dict[str, Any]]:
        """Get the stop pattern for a route in a specific direction."""
        try:
            _LOGGER.debug("Getting stop pattern for route %s direction %s", route_id, direction_id)
            
            # Get trips for this route and direction
            trips = await self.get_trips_for_route(route_id)
            _LOGGER.debug("Found %d total trips for route %s", len(trips), route_id)
            
            direction_trips = [t for t in trips if t.get("direction_id") == direction_id]
            _LOGGER.debug("Found %d trips for route %s direction %s", len(direction_trips), route_id, direction_id)
            
            if not direction_trips:
                _LOGGER.warning("No trips found for route %s direction %s", route_id, direction_id)
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
            
            _LOGGER.debug("Processing %d stops in pattern", len(stop_pattern))
            
            # Get destination (last stop in the pattern)
            destination_stop = stop_pattern[-1] if stop_pattern else None
            
            # Get predictions for each stop on the route
            stop_predictions = {}
            prediction_errors = 0
            
            for i, stop in enumerate(stop_pattern):
                stop_id = str(stop["stop_id"])
                _LOGGER.debug("Getting predictions for stop %s (%d/%d): %s", 
                             stop_id, i+1, len(stop_pattern), stop.get("stop_name", "Unknown"))
                
                try:
                    predictions = await self.get_stop_predictions(stop_id)
                    
                    if predictions and isinstance(predictions, list):
                        # Filter predictions for our specific route
                        route_predictions = [
                            pred for pred in predictions 
                            if str(pred.get("route_id")) == str(route_id) and 
                               pred.get("direction_id") == direction_id
                        ]
                        
                        # If no route-specific predictions, log for debugging
                        if not route_predictions and predictions:
                            _LOGGER.debug("No route-specific predictions for stop %s, found %d general predictions", 
                                        stop_id, len(predictions))
                            # For debugging, let's see what route IDs we're getting
                            unique_routes = set(str(p.get("route_id", "unknown")) for p in predictions[:5])
                            _LOGGER.debug("Sample route IDs in predictions: %s (looking for %s)", 
                                        list(unique_routes), route_id)
                    else:
                        route_predictions = []
                        _LOGGER.debug("No predictions returned for stop %s (got %s)", stop_id, type(predictions))
                    
                    stop_predictions[stop_id] = {
                        "stop_info": stop,
                        "predictions": route_predictions[:3]  # Limit to next 3 departures
                    }
                    
                except MetlinkApiError as e:
                    # If we can't get predictions for this stop, continue with others
                    prediction_errors += 1
                    _LOGGER.debug("Failed to get predictions for stop %s: %s", stop_id, str(e))
                    stop_predictions[stop_id] = {
                        "stop_info": stop,
                        "predictions": []
                    }
            
            _LOGGER.debug("Completed predictions for %d stops with %d errors", 
                         len(stop_predictions), prediction_errors)
            
            return {
                "stops": stop_predictions,
                "destination": destination_stop,
                "stop_count": len(stop_pattern)
            }
            
        except MetlinkApiError as exc:
            _LOGGER.error("Failed to get route stop predictions for route %s direction %s: %s", 
                         route_id, direction_id, exc)
            raise