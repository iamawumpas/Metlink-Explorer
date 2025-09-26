"""Config flow for Metlink Explorer integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .api import MetlinkApiClient, MetlinkApiError
from .const import (
    CONF_API_KEY,
    CONF_ROUTE_ID,
    CONF_ROUTE_LONG_NAME,
    CONF_ROUTE_SHORT_NAME,
    CONF_TRANSPORT_TYPE,
    DOMAIN,
    TRANSPORT_TYPES,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_API_KEY): str,
})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.
    
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    api_key = data[CONF_API_KEY]
    
    # Create API client and validate
    api_client = MetlinkApiClient(hass, api_key)
    
    try:
        if not await api_client.validate_api_key():
            raise InvalidAuth
    except MetlinkApiError as err:
        raise CannotConnect from err

    # Return info that you want to store in the config entry.
    return {"title": "Metlink Explorer", CONF_API_KEY: api_key}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Metlink Explorer."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api_key: str | None = None
        self._transport_type: int | None = None
        self._selected_route: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Store API key for use in subsequent steps
            self._api_key = info[CONF_API_KEY]
            
            # Check if we already have this API key configured
            await self.async_set_unique_id(self._api_key)
            self._abort_if_unique_id_configured()
            
            # Move to transport type selection
            return await self.async_step_transport_type()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_transport_type(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle transport type selection."""
        if user_input is not None:
            self._transport_type = user_input[CONF_TRANSPORT_TYPE]
            return await self.async_step_route_selection()

        # Create the transport type selection schema
        transport_type_schema = vol.Schema({
            vol.Required(CONF_TRANSPORT_TYPE): vol.In({
                route_type: name for route_type, name in TRANSPORT_TYPES.items()
            })
        })

        return self.async_show_form(
            step_id="transport_type",
            data_schema=transport_type_schema,
            description_placeholders={
                "transport_types": ", ".join(TRANSPORT_TYPES.values())
            }
        )

    async def async_step_route_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle route selection."""
        if user_input is not None:
            # Get the selected route ID and look up the route details
            selected_route_id = user_input[CONF_ROUTE_ID]
            
            # Get the route details from the API
            api_client = MetlinkApiClient(self.hass, self._api_key)
            try:
                route_data = await api_client.get_route_by_id(selected_route_id)
                if not route_data:
                    return self.async_abort(reason="route_not_found")
                
                self._selected_route = {
                    CONF_ROUTE_ID: selected_route_id,
                    CONF_ROUTE_SHORT_NAME: route_data.get("route_short_name", ""),
                    CONF_ROUTE_LONG_NAME: route_data.get("route_long_name", ""),
                }
                
            except MetlinkApiError:
                return self.async_abort(reason="cannot_connect")
            
            # Create the config entry
            return await self._create_entry()

        # Get routes for the selected transport type
        api_client = MetlinkApiClient(self.hass, self._api_key)
        
        try:
            routes = await api_client.get_routes(self._transport_type)
            
            # Sort routes alphanumerically by route_short_name then route_long_name
            routes.sort(key=lambda r: (r.get("route_short_name", ""), r.get("route_long_name", "")))
            
            # Create options for the dropdown
            route_options = {}
            for route in routes:
                route_key = route.get("route_id", "")
                route_short_name = route.get("route_short_name", "")
                route_long_name = route.get("route_long_name", "")
                display_name = f"{route_short_name} - {route_long_name}"
                route_options[route_key] = display_name
                
        except MetlinkApiError:
            return self.async_abort(reason="cannot_connect")

        if not route_options:
            return self.async_abort(reason="no_routes")

        # Create the route selection schema
        route_selection_schema = vol.Schema({
            vol.Required(CONF_ROUTE_ID): vol.In(route_options),
        })

        return self.async_show_form(
            step_id="route_selection",
            data_schema=route_selection_schema,
            description_placeholders={
                "transport_type": TRANSPORT_TYPES.get(self._transport_type, "Unknown"),
                "route_count": str(len(route_options))
            }
        )

    async def _create_entry(self) -> FlowResult:
        """Create the config entry."""
        # Create the integration entry title
        transport_type_name = TRANSPORT_TYPES.get(self._transport_type, "Unknown")
        route_short_name = self._selected_route[CONF_ROUTE_SHORT_NAME]
        route_long_name = self._selected_route[CONF_ROUTE_LONG_NAME]
        
        title = f"{transport_type_name} :: {route_short_name} / {route_long_name}"

        # Prepare data for the config entry
        config_data = {
            CONF_API_KEY: self._api_key,
            CONF_TRANSPORT_TYPE: self._transport_type,
            CONF_ROUTE_ID: self._selected_route[CONF_ROUTE_ID],
            CONF_ROUTE_SHORT_NAME: route_short_name,
            CONF_ROUTE_LONG_NAME: route_long_name,
        }

        return self.async_create_entry(
            title=title,
            data=config_data,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Metlink Explorer."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""