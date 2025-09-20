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

        # Check for existing API key in config entries/entities
        existing_api_key = None
        for entry in self._async_current_entries():
            # Try top-level key
            api_key = entry.data.get(CONF_API_KEY)
            if api_key:
                existing_api_key = api_key
                break
            # Try inside entities
            for entity in entry.data.get("entities", []):
                api_key = entity["data"].get(CONF_API_KEY)
                if api_key:
                    existing_api_key = api_key
                    break
            if existing_api_key:
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
            errors=errors,
        )

    async def async_step_entity_type(self, user_input=None):
        errors = {}

        # Collect all used route IDs from existing config entries
        used_route_ids = set()
        for entry in self._async_current_entries():
            for entity in entry.data.get("entities", []):
                route_id = entity["data"].get("route_id")
                if route_id:
                    used_route_ids.add(route_id)

        # Only show types with at least one unused route
        available_types = []
        for type_key, type_label in ENTITY_TYPES.items():
            client = MetlinkApiClient(self.api_key)
            routes = await client.get_routes(type_key)
            await client.close()
            if routes and any(route["route_id"] not in used_route_ids for route in routes):
                available_types.append({"value": type_key, "label": type_label})

        if not available_types:
            errors["base"] = "no_types"
            # Optionally, you could abort the flow here

        if user_input is not None:
            self.entity_type = user_input["entity_type"]
            return await self.async_step_route()
        return self.async_show_form(
            step_id="entity_type",
            data_schema=vol.Schema({
                vol.Required(
                    "entity_type",
                    default=available_types[0]["value"] if available_types else None
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=available_types,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }),
            errors=errors,
        )

    async def async_step_route(self, user_input=None):
        errors = {}

        # Collect all used route IDs from existing config entries
        used_route_ids = set()
        for entry in self._async_current_entries():
            for entity in entry.data.get("entities", []):
                route_id = entity["data"].get("route_id")
                if route_id:
                    used_route_ids.add(route_id)

        # Build route_options, skipping used routes
        if not hasattr(self, "route_options"):
            client = MetlinkApiClient(self.api_key)
            routes = await client.get_routes(self.entity_type)
            await client.close()
            if not routes:
                errors["base"] = "no_routes"
                self.route_options = []
            else:
                self.route_options = [
                    {
                        "value": route["route_id"],
                        "label": f"{route['route_short_name']} - {route['route_long_name']}"
                    }
                    for route in sorted(routes, key=lambda r: r["route_long_name"])
                    if route["route_id"] not in used_route_ids
                ]
                self._routes_cache = {route["route_id"]: route for route in routes}
        route_default = self.route_options[0]["value"] if self.route_options else None

        if user_input is not None and self.route_options:
            route_id = user_input["route_name"]
            if not route_id:
                errors["route_name"] = "select_route"
            else:
                # Get route_short_name and route_long_name for the selected route
                route_obj = self._routes_cache.get(route_id, {})
                route_short_name = route_obj.get("route_short_name", "")
                route_long_name = route_obj.get("route_long_name", "")
                route_name_full = f"{route_short_name} - {route_long_name}"

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
                        friendly_name = f"{ENTITY_TYPES[self.entity_type]} :: {route_short_name} - {route_long_name}"
                        entries.append({
                            "title": friendly_name,
                            "data": {
                                CONF_API_KEY: self.api_key,
                                "entity_type": self.entity_type,
                                "route_id": route_id,
                                "route_name": route_name_full,
                                "direction_id": dir_id,
                                "departure_stop": departure_stop,
                                "destination_stop": destination_stop,
                                "departure_name": departure_name,
                                "destination_name": destination_name,
                            }
                        })
                    if entries:
                        return self.async_create_entry(
                            title=f"{ENTITY_TYPES[self.entity_type]} :: {route_name_full}",
                            data={"entities": entries}
                        )
                    else:
                        errors["base"] = "no_direction_trips"
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
            errors=errors,
        )