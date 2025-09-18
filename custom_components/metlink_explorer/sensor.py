import logging
from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN
from .api import MetlinkApiClient

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities):
    entities = entry.data.get("entities")
    if entities:
        sensors = []
        for ent in entities:
            data = ent["data"]
            client = MetlinkApiClient(data["api_key"])
            sensors.append(
                MetlinkExplorerSensor(
                    client,
                    data["entity_type"],
                    data["route_id"],
                    data["route_name"],
                    data["departure_stop"],
                    data["destination_stop"],
                    data.get("direction_id"),
                    data.get("departure_name"),
                    data.get("destination_name"),
                )
            )
        async_add_entities(sensors)
    else:
        # fallback for single entity config
        api_key = entry.data["api_key"]
        entity_type = entry.data["entity_type"]
        route_id = entry.data["route_id"]
        route_name = entry.data["route_name"]
        departure_stop = entry.data.get("departure_stop")
        destination_stop = entry.data.get("destination_stop")
        direction_id = entry.data.get("direction_id")
        departure_name = entry.data.get("departure_name")
        destination_name = entry.data.get("destination_name")
        client = MetlinkApiClient(api_key)
        async_add_entities([
            MetlinkExplorerSensor(
                client, entity_type, route_id, route_name,
                departure_stop, destination_stop, direction_id,
                departure_name, destination_name
            )
        ])

class MetlinkExplorerSensor(Entity):
    def __init__(self, client, entity_type, route_id, route_name, departure_stop, destination_stop, direction_id=None, departure_name=None, destination_name=None):
        self._client = client
        self._entity_type = entity_type
        self._route_id = route_id
        self._route_name = route_name
        self._departure_stop = departure_stop
        self._destination_stop = destination_stop
        self._direction_id = direction_id
        self._departure_name = departure_name
        self._destination_name = destination_name
        self._attr_name = f"{entity_type.title()} :: {departure_name} - {destination_name}" if departure_name and destination_name else f"{entity_type.title()} :: {route_name}"
        self._attr_unique_id = f"{entity_type}_{route_id}_{direction_id}".replace(" ", "_").lower() if direction_id is not None else f"{entity_type}_{route_id}".replace(" ", "_").lower()
        self._state = None
        self._extra_state_attributes = {}

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._extra_state_attributes

    async def async_update(self):
        # 1. Get all trips for the route and filter by direction_id
        trips = await self._client.get_trips(self._route_id)
        if not trips:
            self._extra_state_attributes["route_stops"] = []
            self._state = 0
            return

        # Select the trip with the correct direction_id
        trip = next((t for t in trips if t.get("direction_id") == self._direction_id), trips[0])
        trip_id = trip["trip_id"]

        # 2. Get stop times for the trip (ordered)
        stop_times = await self._client.get_stop_times(trip_id)
        stop_ids = [st["stop_id"] for st in stop_times]
        stops = await self._client.get_stops_by_ids(stop_ids)
        stop_lookup = {stop["stop_id"]: stop for stop in stops}

        # 3. Get real-time predictions for this route only
        predictions = await self._client.get_departure_predictions(self._route_id)
        if isinstance(predictions, dict):
            predictions = [predictions]
        elif predictions is None:
            predictions = []
        predictions = [p for p in predictions if p.get("route_id") == self._route_id]
        pred_lookup = {}
        for pred in predictions:
            pred_lookup.setdefault(pred["stop_id"], []).append(pred)

        # 4. Get alerts for this route only and normalize to a list of alert objects
        alerts = await self._client.get_service_alerts(self._route_id)
        if isinstance(alerts, dict) and "entity" in alerts:
            alerts = [e["alert"] for e in alerts["entity"] if "alert" in e]
        elif isinstance(alerts, list):
            alerts = [a["alert"] if "alert" in a else a for a in alerts]
        elif isinstance(alerts, dict) and "alert" in alerts:
            alerts = [alerts["alert"]]
        elif isinstance(alerts, dict):
            alerts = [alerts]
        elif alerts is None:
            alerts = []
        alerts = [
            a for a in alerts
            if any(ent.get("route_id") == self._route_id for ent in a.get("informed_entity", []))
        ] if alerts else []
        self._extra_state_attributes["alerts"] = alerts

        # 5. Get trip updates for this route only
        trip_updates = await self._client.get_trip_updates(self._route_id)
        if isinstance(trip_updates, list):
            trip_updates = [t for t in trip_updates if t.get("route_id") == self._route_id]
        elif isinstance(trip_updates, dict):
            if trip_updates.get("route_id") == self._route_id:
                trip_updates = [trip_updates]
            else:
                trip_updates = []
        elif trip_updates is None:
            trip_updates = []
        self._extra_state_attributes["trip_updates"] = trip_updates

        # 6. Get cancellations for this route only
        cancellations = await self._client.get_trip_cancellations(self._route_id)
        if isinstance(cancellations, list):
            cancellations = [c for c in cancellations if c.get("route_id") == self._route_id]
        elif isinstance(cancellations, dict):
            if cancellations.get("route_id") == self._route_id:
                cancellations = [cancellations]
            else:
                cancellations = []
        elif cancellations is None:
            cancellations = []
        self._extra_state_attributes["cancellations"] = cancellations

        # 7. Departure predictions (already filtered above)
        self._extra_state_attributes["departure_predictions"] = predictions

        # 8. Route stops (ordered)
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

        # 9. Add route_name, departure_name, and destination_name as top-level attributes
        self._extra_state_attributes["route_name"] = self._route_name
        self._extra_state_attributes["departure_name"] = self._departure_name
        self._extra_state_attributes["destination_name"] = self._destination_name

        self._state = len(route_stops)
        _LOGGER.info("Route stops: %s", route_stops)