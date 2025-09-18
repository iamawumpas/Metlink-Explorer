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

PLACEHOLDER = "--- Select a route or start typing ---"

# Friendly step names for UI
STEP_USER = "Add your API Key"
STEP_ENTITY_TYPE = "Select Transport Type"
STEP_ROUTE = "Route Selection"
STEP_ADD_ANOTHER = "Do you want to add another route?"

class MetlinkExplorerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self):
        self.entries = []

    async def async_step_user(self, user_input=None):
        errors = {}
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
            step_id=STEP_USER,
            data_schema=vol.Schema({
                vol.Required(CONF_API_KEY): str
            }),
            errors=errors,
            description="Enter your Metlink API Key."
        )

    async def async_step_entity_type(self, user_input=None):
        errors = {}
        if user_input is not None:
            self.entity_type = user_input["entity_type"]
            return await self.async_step_route()
        return self.async_show_form(
            step_id=STEP_ENTITY_TYPE,
            data_schema=vol.Schema({
                vol.Required("entity_type", default="train"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[{"value": k, "label": v} for k, v in ENTITY_TYPES.items()],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }),
            errors=errors,
            description="Select the type of transport."
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
                    {"value": "", "label": PLACEHOLDER}
                ] + [
                    {"value": route["route_id"], "label": f"{route['route_short_name']} - {route['route_long_name']}"}
                    for route in sorted(routes, key=lambda r: r["route_long_name"])
                ]
        if user_input is not None and self.route_options:
            route_id = user_input["route_name"]
            if not route_id:
                errors["route_name"] = "select_route"
            else:
                route_name = next((opt["label"] for opt in self.route_options if opt["value"] == route_id), route_id)
                client = MetlinkApiClient(self.api_key)
                trips = await client.get_trips(route_id)
                await client.close()
                if not trips:
                    errors["base"] = "no_trips"
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
                                "route_name": route_name,
                                "direction_id": dir_id,
                                "departure_stop": departure_stop,
                                "destination_stop": destination_stop,
                                "departure_name": departure_name,
                                "destination_name": destination_name,
                            }
                        })
                    if entries:
                        self.entries.extend(entries)
                        return await self.async_step_add_another()
                    else:
                        errors["base"] = "no_direction_trips"
        return self.async_show_form(
            step_id=STEP_ROUTE,
            data_schema=vol.Schema({
                vol.Required("route_name", default=""): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self.route_options if hasattr(self, "route_options") else [],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }),
            errors=errors,
            description="Select the route you want to add."
        )

    async def async_step_add_another(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input["add_another"]:
                return await self.async_step_entity_type()
            else:
                # Finish and create entry with all selected routes
                return self.async_create_entry(
                    title="Metlink Explorer",
                    data={"entities": self.entries}
                )
        return self.async_show_form(
            step_id=STEP_ADD_ANOTHER,
            data_schema=vol.Schema({
                vol.Required("add_another", default=False): selector.BooleanSelector()
            }),
            description="Do you want to add another route?"
        )