from homeassistant import config_entries
from homeassistant.helpers import selector
import voluptuous as vol
from .const import DOMAIN, CONF_API_KEY
from .api import MetlinkApiClient

ENTITY_TYPES = {
    "train": "Train",
    "bus": "Bus",
    "ferry": "Ferry"
}

class MetlinkExplorerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input=None):
        errors = {}

        # Check for existing API key in config entries
        existing_api_key = None
        for entry in self._async_current_entries():
            api_key = entry.data.get(CONF_API_KEY)
            if api_key:
                existing_api_key = api_key
                break

        if existing_api_key:
            self.api_key = existing_api_key
            return await self.async_step_entity_type()

        # If no API key found, ask for it
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            client = MetlinkApiClient(api_key)
            valid = await client.validate_api_key()
            await client.close()
            if valid:
                self.api_key = api_key
                return await self.async_step_entity_type()
            else:
                errors["base"] = "invalid_api_key"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_API_KEY): str
            }),
            errors=errors
        )

    async def async_step_entity_type(self, user_input=None):
        errors = {}
        if user_input is not None:
            self.entity_type = user_input["entity_type"]
            return await self.async_step_route()
        return self.async_show_form(
            step_id="entity_type",
            data_schema=vol.Schema({
                vol.Required("entity_type", default="train"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[{"value": k, "label": v} for k, v in ENTITY_TYPES.items()],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }),
            errors=errors
        )

    async def async_step_route(self, user_input=None):
        errors = {}
        if not hasattr(self, "route_options"):
            client = MetlinkApiClient(self.api_key)
            routes = await client.get_routes(self.entity_type)
            await client.close()
            if not routes:
                errors["base"] = "no_routes"
                self.route_options = []
            else:
                self.route_options = [
                    {"value": route["route_id"], "label": f"{route['route_short_name']} - {route['route_long_name']}"}
                    for route in sorted(routes, key=lambda r: r["route_long_name"])
                ]
        route_default = self.route_options[0]["value"] if self.route_options else None
        if user_input is not None and self.route_options:
            route_id = user_input["route_name"]
            if not route_id:
                errors["route_name"] = "Please select a route."
            else:
                route_obj = next((opt for opt in self.route_options if opt["value"] == route_id), None)
                route_label = route_obj["label"] if route_obj else route_id
                client = MetlinkApiClient(self.api_key)
                trips = await client.get_trips(route_id)
                await client.close()
                if not trips:
                    errors["base"] = "No trips found for this route."
                else:
                    dir_trips = {0: None, 1: None}
                    for trip in trips:
                        dir_id = trip.get("direction_id")
                        if dir_id in dir_trips and dir_trips[dir_id] is None:
                            dir_trips[dir_id] = trip
                    entries = []
                    for dir_id, trip in dir_trips.items():
                        if trip is None:
                            continue
                        trip_id = trip["trip_id"]
                        client = MetlinkApiClient(self.api_key)
                        stop_times = await client.get_stop_times(trip_id)
                        stops = await client.get_stops_by_ids([st["stop_id"] for st in stop_times])
                        await client.close()
                        if not stop_times or not stops:
                            continue
                        first_stop_id = stop_times[0]["stop_id"]
                        last_stop_id = stop_times[-1]["stop_id"]
                        stop_lookup = {stop["stop_id"]: stop["stop_name"] for stop in stops}
                        departure_stop = first_stop_id
                        destination_stop = last_stop_id
                        departure_name = stop_lookup.get(departure_stop, departure_stop)
                        destination_name = stop_lookup.get(destination_stop, destination_stop)
                        friendly_name = f"{ENTITY_TYPES[self.entity_type]} :: {departure_name} - {destination_name}"
                        entries.append({
                            "title": friendly_name,
                            "data": {
                                CONF_API_KEY: self.api_key,
                                "entity_type": self.entity_type,
                                "route_id": route_id,
                                "route_name": route_label,
                                "direction_id": dir_id,
                                "departure_stop": departure_stop,
                                "destination_stop": destination_stop,
                                "departure_name": departure_name,
                                "destination_name": destination_name,
                            }
                        })
                    # Set a friendly integration title
                    if self.entity_type == "train":
                        integration_title = f"Train: {route_label.split('-', 1)[-1].strip()}"
                    elif self.entity_type == "bus":
                        integration_title = f"Bus: #{route_label.split('-', 1)[0].strip()}"
                    elif self.entity_type == "ferry":
                        integration_title = f"Ferry: {route_label.split('-', 1)[-1].strip()}"
                    else:
                        integration_title = route_label
                    return self.async_create_entry(
                        title=integration_title,
                        data={"entities": entries}
                    )
        return self.async_show_form(
            step_id="route",
            data_schema=vol.Schema({
                vol.Required("route_name", default=route_default): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self.route_options if hasattr(self, "route_options") else [],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }),
            errors=errors
        )