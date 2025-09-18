from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .api import MetlinkApiClient

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    api_key = entry.data["api_key"]
    entity_type = entry.data["entity_type"]
    route_id = entry.data["route_id"]
    route_name = entry.data["route_name"]
    departure_stop = entry.data.get("departure_stop")
    destination_stop = entry.data.get("destination_stop")
    client = MetlinkApiClient(api_key)
    async_add_entities([
        MetlinkExplorerSensor(client, entity_type, route_id, route_name, departure_stop, destination_stop)
    ])

class MetlinkExplorerSensor(Entity):
    def __init__(self, client, entity_type, route_id, route_name, departure_stop, destination_stop):
        self._client = client
        self._entity_type = entity_type
        self._route_id = route_id
        self._route_name = route_name
        self._departure_stop = departure_stop
        self._destination_stop = destination_stop
        self._attr_name = f"{entity_type.title()} :: {route_name}"
        self._attr_unique_id = f"{entity_type}_{route_id}".replace(" ", "_").lower()
        self._state = None
        self._extra_state_attributes = {}

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._extra_state_attributes

    async def async_update(self):
        # Example: fetch and expose some attributes
        self._extra_state_attributes["calendar"] = await self._client.get_calendar(self._route_id)
        self._extra_state_attributes["calendar_dates"] = await self._client.get_calendar_dates(self._route_id)
        self._extra_state_attributes["service_alerts"] = await self._client.get_service_alerts(self._route_id)
        self._extra_state_attributes["trip_updates"] = await self._client.get_trip_updates(self._route_id)
        self._extra_state_attributes["trip_cancellations"] = await self._client.get_trip_cancellations(self._route_id)
        self._extra_state_attributes["departure_predictions"] = await self._client.get_departure_predictions(self._route_id)
        # Optionally, fetch stops for the route
        self._extra_state_attributes["stops"] = await self._client.get_stops()
        # Set state to something meaningful, e.g. number of predictions
        self._state = len(self._extra_state_attributes["departure_predictions"]) if self._extra_state_attributes["departure_predictions"] else 0