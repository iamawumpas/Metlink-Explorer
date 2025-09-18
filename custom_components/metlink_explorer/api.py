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
            return [route for route in data if route.get("route_type") == type_map[entity_type]]

    async def close(self):
        await self.session.close()