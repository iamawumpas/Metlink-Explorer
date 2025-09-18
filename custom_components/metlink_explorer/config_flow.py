from homeassistant import config_entries
import voluptuous as vol
from homeassistant.helpers import selector
from .const import DOMAIN, CONF_API_KEY
from .api import MetlinkApiClient

ENTITY_TYPES = {
    "train": "Train",
    "bus": "Bus",
    "ferry": "Ferry"
}

PLACEHOLDER = "--- Select a route ---"

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
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_entity_type(self, user_input=None):
        errors = {}
        if user_input is not None:
            self.entity_type = user_input["entity_type"]
            return await self.async_step_route()
        return self.async_show_form(
            step_id="entity_type",
            data_schema=vol.Schema({
                vol.Required("entity_type", default="bus"): vol.In(ENTITY_TYPES)
            }),
            errors=errors,
        )

    async def async_step_route(self, user_input=None):
        errors = {}
        if not hasattr(self, "routes"):
            # Fetch routes from API
            client = MetlinkApiClient(self.api_key)
            routes = await client.get_routes(self.entity_type)
            await client.close()
            if not routes:
                errors["base"] = "no_routes"
                self.routes = {}
            else:
                # Friendly name as key, route_id as value
                route_dict = {
                    f"{route['route_short_name']} - {route['route_long_name']}": route["route_id"]
                    for route in sorted(routes, key=lambda r: r["route_long_name"])
                }
                # Insert placeholder at the top
                self.routes = {PLACEHOLDER: ""}  # Non-selectable value
                self.routes.update(route_dict)
                # For selector, build a list of options (excluding placeholder)
                self.route_options = [
                    {"value": route_id, "label": name}
                    for name, route_id in self.routes.items()
                    if name != PLACEHOLDER
                ]
        if user_input is not None and self.routes:
            route_id = user_input["route_name"]
            if not route_id or route_id == "":
                errors["route_name"] = "select_route"
            else:
                # Find the friendly name for the selected route_id
                route_name = next((name for name, rid in self.routes.items() if rid == route_id), route_id)
                entity_title = (
                    f"{ENTITY_TYPES[self.entity_type]} :: {route_name}"
                    if self.entity_type == "ferry"
                    else f"{ENTITY_TYPES[self.entity_type]} {route_name}"
                )
                return self.async_create_entry(
                    title=entity_title,
                    data={
                        CONF_API_KEY: self.api_key,
                        "entity_type": self.entity_type,
                        "route_id": route_id,
                        "route_name": route_name,
                    },
                )
        # Always use selector for dropdown
        return self.async_show_form(
            step_id="route",
            data_schema=vol.Schema({
                vol.Required("route_name"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self.route_options if hasattr(self, "route_options") else [],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }),
            errors=errors,
        )