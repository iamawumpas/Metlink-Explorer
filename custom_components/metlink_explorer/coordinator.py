"""Data update coordinator for Metlink Explorer."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import MetlinkApiClient, MetlinkApiError
from .const import CONF_API_KEY, CONF_ROUTE_ID, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class MetlinkDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Metlink API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.api_client = MetlinkApiClient(hass, entry.data[CONF_API_KEY])
        self.route_id = entry.data[CONF_ROUTE_ID]
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            _LOGGER.info("📡 " + "=" * 40)
            _LOGGER.info("📡 FETCHING route data from Metlink API...")
            _LOGGER.info("📡 " + "=" * 40)
            
            # Get route information
            _LOGGER.info("📋 Step 1/6: Getting route information...")
            route_data = await self.api_client.get_route_by_id(self.route_id)
            if not route_data:
                raise UpdateFailed(f"Route {self.route_id} not found")
            _LOGGER.info(f"✅ Route data loaded: {route_data.get('route_short_name')} - {route_data.get('route_long_name')}")
            
            # Get real-time data
            _LOGGER.info("🚌 Step 2/6: Getting real-time trip updates...")
            trip_updates = await self.api_client.get_trip_updates()
            _LOGGER.info(f"✅ Trip updates loaded: {len(trip_updates)} updates")
            
            _LOGGER.info("🚗 Step 3/6: Getting vehicle positions...")
            vehicle_positions = await self.api_client.get_vehicle_positions()
            _LOGGER.info(f"✅ Vehicle positions loaded: {len(vehicle_positions)} vehicles")
            
            _LOGGER.info("🚨 Step 4/6: Getting service alerts...")
            service_alerts = await self.api_client.get_service_alerts()
            _LOGGER.info(f"✅ Service alerts loaded: {len(service_alerts)} alerts")
            
            # Get stop sequences for both directions
            _LOGGER.info("🛑 Step 5/6: Getting stop sequences for route...")
            route_stops = await self.api_client.get_route_stops(self.route_id)
            if route_stops:
                total_stops = sum(len(stops) for stops in route_stops.values())
                directions = list(route_stops.keys())
                _LOGGER.info(f"✅ Route stops loaded: {total_stops} stops across {len(directions)} directions")
                for direction_id, stops in route_stops.items():
                    direction_name = "Outbound" if direction_id == 0 else "Inbound"
                    _LOGGER.info(f"   📍 {direction_name}: {len(stops)} stops")
            else:
                _LOGGER.warning("⚠️ No route stops found")
            
            # Get departures for both directions separately
            _LOGGER.info("⏰ Step 6/6: Getting departure times...")
            direction_0_departures = await self.api_client.get_route_departures(self.route_id, direction_id=0, limit=10)
            _LOGGER.info(f"   ✅ Outbound departures: {len(direction_0_departures)} upcoming")
            
            direction_1_departures = await self.api_client.get_route_departures(self.route_id, direction_id=1, limit=10)
            _LOGGER.info(f"   ✅ Inbound departures: {len(direction_1_departures)} upcoming")
            
            _LOGGER.info("🔍 Filtering real-time data for this route...")
            # Filter data for this route
            # Convert route_id to string for comparison since API may return integers
            route_id_str = str(self.route_id)
            
            route_trip_updates = []
            for update in trip_updates:
                trip_update = update.get("trip_update", {})
                trip = trip_update.get("trip", {})
                if str(trip.get("route_id", "")) == route_id_str:
                    route_trip_updates.append(update)
            
            route_vehicle_positions = []
            for position in vehicle_positions:
                trip = position.get("trip", {})
                if str(trip.get("route_id", "")) == route_id_str:
                    route_vehicle_positions.append(position)
            
            route_service_alerts = []
            for alert in service_alerts:
                alert_data = alert.get("alert", {})
                informed_entities = alert_data.get("informed_entity", [])
                for entity in informed_entities:
                    if str(entity.get("route_id", "")) == route_id_str:
                        route_service_alerts.append(alert)
                        break
            
            _LOGGER.info(f"   🚌 Route trips: {len(route_trip_updates)} active")
            _LOGGER.info(f"   🚗 Route vehicles: {len(route_vehicle_positions)} tracked")
            _LOGGER.info(f"   🚨 Route alerts: {len(route_service_alerts)} active")
            
            _LOGGER.info("📡 " + "=" * 40)
            _LOGGER.info("✅ DATA FETCH COMPLETED successfully!")
            _LOGGER.info("📡 " + "=" * 40)
            
            return {
                "route_data": route_data,
                "trip_updates": route_trip_updates,
                "vehicle_positions": route_vehicle_positions,
                "service_alerts": route_service_alerts,
                "route_stops": route_stops,
                "direction_0_departures": direction_0_departures,
                "direction_1_departures": direction_1_departures,
                "last_updated": dt_util.utcnow(),
            }
            
        except MetlinkApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err