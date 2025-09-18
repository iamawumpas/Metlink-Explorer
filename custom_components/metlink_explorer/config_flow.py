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
        if not hasattr(self, "route_options"):
            # Fetch routes from API
            client = MetlinkApiClient(self.api_key)
            routes = await client.get_routes(self.entity_type)
            await client.close()
            if not routes:
                errors["base"] = "no_routes"
                self.route_options = []
            else:
                # Build selector options: value=route_id, label=friendly name
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
                # Find the friendly name for the selected route_id
                route_name = next((opt["label"] for opt in self.route_options if opt["value"] == route_id), route_id)
                entity_title = f"{ENTITY_TYPES[self.entity_type]} :: {route_name}"
                return self.async_create_entry(
                    title=entity_title,
                    data={
                        CONF_API_KEY: self.api_key,
                        "entity_type": self.entity_type,
                        "route_id": route_id,
                        "route_name": route_name,
                    },
                )
        # Always use selector for dropdown, with placeholder as first option
        return self.async_show_form(
            step_id="route",
            data_schema=vol.Schema({
                vol.Required("route_name", default=""): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self.route_options if hasattr(self, "route_options") else [],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }),
            errors=errors,
        )