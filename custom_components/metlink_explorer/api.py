"""API client for Metlink Open Data."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
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
            # The stop_times endpoint requires trip_id as a parameter
            endpoint = f"{API_ENDPOINTS['stop_times']}?trip_id={trip_id}"
            stop_times = await self._request(endpoint)
            
            # The API returns the stop times directly, no need to filter
            if not isinstance(stop_times, list):
                _LOGGER.warning("Expected list from stop_times API, got %s", type(stop_times))
                return []
            
            # Sort by stop_sequence to get the correct order
            sorted_stop_times = sorted(stop_times, key=lambda x: x.get("stop_sequence", 0))
            
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
            
            # Step 2: Get real-time predictions using the stop-predictions endpoint
            timeline_stops = []
            current_time = datetime.now()
            current_time_str = current_time.strftime("%H:%M:%S")
            
            for stop_info in stop_pattern:
                stop_id = str(stop_info["stop_id"])
                
                # Get real-time predictions for this stop
                predictions = []
                try:
                    stop_predictions = await self.get_stop_predictions(stop_id)
                    
                    if stop_predictions and isinstance(stop_predictions, list):
                        # Filter for our specific route and direction
                        relevant_predictions = [
                            pred for pred in stop_predictions 
                            if (str(pred.get("route_id")) == str(route_id) or 
                                str(pred.get("route_short_name", "")).lower() == self._get_route_short_name(route_id).lower()) and
                               pred.get("direction_id") == direction_id
                        ]
                        
                        # Sort predictions by departure time and take the next few
                        predictions = sorted(relevant_predictions, 
                                           key=lambda x: x.get("departure_time", "99:99:99"))[:3]
                        
                except Exception as e:
                    _LOGGER.debug("Could not get predictions for stop %s: %s", stop_id, e)
                
                # Calculate ETA for the next departure
                eta_display = "No predictions"
                eta_seconds = 0
                next_departure = None
                
                if predictions:
                    next_pred = predictions[0]
                    departure_time = next_pred.get("departure_time")
                    
                    if departure_time:
                        try:
                            # Parse departure time and calculate ETA
                            departure_dt = datetime.strptime(f"{current_time.date()} {departure_time}", "%Y-%m-%d %H:%M:%S")
                            
                            # If departure is earlier than now, assume it's tomorrow
                            if departure_dt < current_time:
                                from datetime import timedelta
                                departure_dt += timedelta(days=1)
                            
                            eta_seconds = int((departure_dt - current_time).total_seconds())
                            eta_minutes = eta_seconds // 60
                            eta_remaining_seconds = eta_seconds % 60
                            
                            # Format ETA for display
                            if eta_seconds <= 0:
                                eta_display = "Due now"
                            elif eta_seconds < 60:
                                eta_display = f"{eta_seconds}s"
                            elif eta_minutes < 60:
                                eta_display = f"{eta_minutes}m {eta_remaining_seconds}s"
                            else:
                                hours = eta_minutes // 60
                                remaining_minutes = eta_minutes % 60
                                eta_display = f"{hours}h {remaining_minutes}m"
                            
                            next_departure = departure_time
                            
                        except Exception as e:
                            _LOGGER.debug("Could not parse departure time %s: %s", departure_time, e)
                            eta_display = departure_time
                            next_departure = departure_time
                
                # Use scheduled time as fallback
                if not next_departure:
                    scheduled_time = stop_info.get("departure_time", stop_info.get("arrival_time"))
                    if scheduled_time:
                        eta_display = f"Scheduled: {scheduled_time}"
                        next_departure = scheduled_time
                
                timeline_stop = {
                    "stop_id": stop_id,
                    "stop_name": stop_info.get("stop_name", "Unknown Stop"),
                    "stop_sequence": stop_info.get("stop_sequence", 0),
                    "scheduled_time": stop_info.get("departure_time", stop_info.get("arrival_time")),
                    "next_departure": next_departure,
                    "eta_display": eta_display,
                    "eta_seconds": eta_seconds,
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
        """Get route short name for a given route ID."""
        try:
            routes = await self.get_routes()
            route_info = next((r for r in routes if str(r.get("route_id")) == str(route_id)), None)
            return route_info.get("route_short_name", "") if route_info else ""
        except:
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