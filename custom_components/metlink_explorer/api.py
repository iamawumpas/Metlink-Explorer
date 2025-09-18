import aiohttp
from .const import API_BASE_URL

class MetlinkApiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = aiohttp.ClientSession()

    async def validate_api_key(self):
        """Validate the API key by making a simple request."""
        url = f"{API_BASE_URL}/gtfs/agency"
        headers = {"x-api-key": self.api_key}
        async with self.session.get(url, headers=headers) as resp:
            return resp.status == 200

    async def close(self):
        await self.session.close()