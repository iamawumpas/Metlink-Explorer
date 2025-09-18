import logging
from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN
from .api import MetlinkApiClient

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities):
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
        trips = await self._client.get_trips(self._route_id)
        if not trips:
            self._extra_state_attributes["route_stops"] = []
            self._state = 0
            return

        trip_id = trips[0]["trip_id"]
        stop_times = await self._client.get_stop_times(trip_id)
        stop_ids = [st["stop_id"] for st in stop_times]
        stops = await self._client.get_stops_by_ids(stop_ids)
        stop_lookup = {stop["stop_id"]: stop for stop in stops}
        predictions = await self._client.get_departure_predictions(self._route_id)
        pred_lookup = {}
        for pred in predictions:
            pred_lookup.setdefault(pred["stop_id"], []).append(pred)

        # Normalize alerts to always be a list and use 'alerts'
        alerts = await self._client.get_service_alerts(self._route_id)
        if isinstance(alerts, dict) and "alert" in alerts:
            alerts = [alerts["alert"]]
        elif isinstance(alerts, dict):
            alerts = [alerts]
        elif alerts is None:
            alerts = []
        self._extra_state_attributes["alerts"] = alerts

        # Normalize trip_updates to always be a list and use 'trip_updates'
        trip_updates = await self._client.get_trip_updates(self._route_id)
        if isinstance(trip_updates, dict):
            trip_updates = [trip_updates]
        elif trip_updates is None:
            trip_updates = []
        self._extra_state_attributes["trip_updates"] = trip_updates

        # Normalize cancellations to always be a list and use 'cancellations'
        cancellations = await self._client.get_trip_cancellations(self._route_id)
        if isinstance(cancellations, dict):
            cancellations = [cancellations]
        elif cancellations is None:
            cancellations = []
        self._extra_state_attributes["cancellations"] = cancellations

        # Normalize departure_predictions to always be a list and use 'departure_predictions'
        if isinstance(predictions, dict):
            predictions = [predictions]
        elif predictions is None:
            predictions = []
        self._extra_state_attributes["departure_predictions"] = predictions

        # Route stops (ordered)
        route_stops = []
        for st in stop_times:
            stop_id = st["stop_id"]
            stop_info = stop_lookup.get(stop_id, {})
            scheduled_time = st.get("departure_time")
            realtime = pred_lookup.get(stop_id, [])
            route_stops.append({
                "stop_id": stop_id,
                "stop_name": stop_info.get("stop_name"),
                "scheduled_departure": scheduled_time,
                "realtime_predictions": realtime,
            })
        self._extra_state_attributes["route_stops"] = route_stops

        self._state = len(route_stops)
        _LOGGER.info("Route stops: %s", route_stops)