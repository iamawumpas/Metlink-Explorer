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

class MetlinkExplorerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

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
            step_id="user",
            data_schema=self._user_schema(),
            errors=errors,
        )

    def _user_schema(self):
        return {
            vol.Required(CONF_API_KEY): str
        }

    async def async_step_entity_type(self, user_input=None):
        errors = {}
        if user_input is not None:
            self.entity_type = user_input["entity_type"]
            return await self.async_step_route()
        return self.async_show_form(
            step_id="entity_type",
            data_schema=self._entity_type_schema(),
            errors=errors,
        )

    def _entity_type_schema(self):
        return {
            "entity_type": selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in ENTITY_TYPES.items()],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
        }

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
                # Fetch trips for both directions and create two entities
                client = MetlinkApiClient(self.api_key)
                trips = await client.get_trips(route_id)
                await client.close()
                if not trips:
                    errors["base"] = "no_trips"
                else:
                    # Group trips by direction_id
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
                        # Get first and last stop
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
                        # Create a group entry with both directions
                        return self.async_create_entry(
                            title=f"{ENTITY_TYPES[self.entity_type]} :: {route_name}",
                            data={"entities": entries}
                        )
                    else:
                        errors["base"] = "no_direction_trips"
        return self.async_show_form(
            step_id="route",
            data_schema=self._route_schema(),
            errors=errors,
        )

    def _route_schema(self):
        return {
            "route_name": selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self.route_options if hasattr(self, "route_options") else [],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
        }