import aiohttp
from .const import API_BASE_URL

class MetlinkApiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = aiohttp.ClientSession()

    async def validate_api_key(self):
        url = f"{API_BASE_URL}/gtfs/agency"
        headers = {"x-api-key": self.api_key}
        async with self.session.get(url, headers=headers) as resp:
            return resp.status == 200

    async def get_routes(self, entity_type):
        url = f"{API_BASE_URL}/gtfs/routes"
        headers = {"x-api-key": self.api_key}
        async with self.session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            # Filter by entity type
            type_map = {"bus": 3, "train": 2, "ferry": 4}
            filtered = [
                route for route in data
                if route.get("route_type") == type_map[entity_type]
            ]
            # Only return routes with required fields
            return [
                {
                    "route_id": route.get("route_id"),
                    "route_short_name": route.get("route_short_name", ""),
                    "route_long_name": route.get("route_long_name", "")
                }
                for route in filtered
            ]

    async def get_trips(self, route_id):
        url = f"{API_BASE_URL}/gtfs/trips"
        headers = {"x-api-key": self.api_key}
        params = {"route_id": route_id}
        async with self.session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                return []
            return await resp.json()

    async def get_stop_times(self, trip_id):
        url = f"{API_BASE_URL}/gtfs/stop_times"
        headers = {"x-api-key": self.api_key}
        params = {"trip_id": trip_id}
        async with self.session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                return []
            return await resp.json()

    async def get_stops_by_ids(self, stop_ids):
        url = f"{API_BASE_URL}/gtfs/stops"
        headers = {"x-api-key": self.api_key}
        async with self.session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return []
            stops = await resp.json()
            return [stop for stop in stops if stop["stop_id"] in stop_ids]

    async def get_stops(self):
        url = f"{API_BASE_URL}/gtfs/stops"
        headers = {"x-api-key": self.api_key}
        async with self.session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return []
            return await resp.json()

    async def get_calendar(self, route_id):
        url = f"{API_BASE_URL}/gtfs/calendar"
        headers = {"x-api-key": self.api_key}
        async with self.session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            return data

    async def get_calendar_dates(self, route_id):
        url = f"{API_BASE_URL}/gtfs/calendar_dates"
        headers = {"x-api-key": self.api_key}
        async with self.session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            return data

    async def get_service_alerts(self, route_id):
        url = f"{API_BASE_URL}/gtfs-rt/servicealerts"
        headers = {"x-api-key": self.api_key}
        params = {"route_id": route_id}
        async with self.session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            return data

    async def get_departure_predictions(self, route_id):
        url = f"{API_BASE_URL}/stop-predictions"
        headers = {"x-api-key": self.api_key}
        params = {"route_id": route_id}
        async with self.session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            return data

    async def get_trip_updates(self, route_id):
        url = f"{API_BASE_URL}/gtfs-rt/tripupdates"
        headers = {"x-api-key": self.api_key}
        params = {"route_id": route_id}
        async with self.session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            return data

    async def get_trip_cancellations(self, route_id):
        url = f"{API_BASE_URL}/trip-cancellations"
        headers = {"x-api-key": self.api_key}
        params = {"route_id": route_id}
        async with self.session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            return data

    async def close(self):
        await self.session.close()