"""Config flow for Metlink Explorer integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api import MetlinkApiClient, MetlinkApiError
from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_TRANSPORTATION_TYPE,
    CONF_ROUTE_ID,
    CONF_ROUTE_SHORT_NAME,
    CONF_ROUTE_LONG_NAME,
    TRANSPORTATION_TYPES,
)

_LOGGER = logging.getLogger(__name__)


class MetlinkExplorerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Metlink Explorer."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api_key: str | None = None
        self._api_client: MetlinkApiClient | None = None
        self._transportation_type: int | None = None
        self._available_routes: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - API key validation."""
        errors: dict[str, str] = {}

        # Check if there are existing entries with API keys
        existing_entries = self._async_current_entries()
        if existing_entries:
            # Use API key from existing entry
            existing_entry = existing_entries[0]
            self._api_key = existing_entry.data.get(CONF_API_KEY)
            if self._api_key:
                session = async_get_clientsession(self.hass)
                self._api_client = MetlinkApiClient(self._api_key, session)
                return await self.async_step_transportation_type()

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            
            # Validate API key
            session = async_get_clientsession(self.hass)
            api_client = MetlinkApiClient(api_key, session)
            
            try:
                if await api_client.validate_api_key():
                    self._api_key = api_key
                    self._api_client = api_client
                    return await self.async_step_transportation_type()
                else:
                    errors["base"] = "invalid_auth"
            except MetlinkApiError:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_API_KEY): cv.string,
            }),
            errors=errors,
        )

    async def async_step_transportation_type(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle transportation type selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            transportation_type = user_input[CONF_TRANSPORTATION_TYPE]
            self._transportation_type = transportation_type
            
            try:
                # Fetch routes for this transportation type
                self._available_routes = await self._api_client.get_routes_by_type(transportation_type)
                if not self._available_routes:
                    errors["base"] = "no_routes_found"
                else:
                    return await self.async_step_route_selection()
            except MetlinkApiError:
                errors["base"] = "cannot_connect"

        # Create options for transportation types
        transportation_options = {
            str(type_id): f"{type_name} ({type_id})"
            for type_id, type_name in TRANSPORTATION_TYPES.items()
        }

        return self.async_show_form(
            step_id="transportation_type",
            data_schema=vol.Schema({
                vol.Required(CONF_TRANSPORTATION_TYPE): vol.In(transportation_options),
            }),
            errors=errors,
        )

    async def async_step_route_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle route selection."""
        if user_input is not None:
            route_id = user_input[CONF_ROUTE_ID]
            
            # Find the selected route details
            selected_route = next(
                (route for route in self._available_routes if route["route_id"] == route_id),
                None
            )
            
            if selected_route:
                # Create the integration entry
                transportation_name = TRANSPORTATION_TYPES.get(self._transportation_type, "Unknown")
                route_short_name = selected_route["route_short_name"]
                route_long_name = selected_route["route_long_name"]
                
                title = f"{transportation_name} :: {route_short_name} / {route_long_name}"
                
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_API_KEY: self._api_key,
                        CONF_TRANSPORTATION_TYPE: self._transportation_type,
                        CONF_ROUTE_ID: route_id,
                        CONF_ROUTE_SHORT_NAME: route_short_name,
                        CONF_ROUTE_LONG_NAME: route_long_name,
                    }
                )

        # Create route options sorted alphanumerically
        def sort_key(route):
            short_name = route.get("route_short_name", "")
            # Try to convert to int for proper numeric sorting, fallback to string
            try:
                return (0, int(short_name))
            except ValueError:
                return (1, short_name.lower())

        sorted_routes = sorted(self._available_routes, key=sort_key)
        
        route_options = {
            route["route_id"]: f"{route['route_short_name']} :: {route['route_long_name']}"
            for route in sorted_routes
        }

        return self.async_show_form(
            step_id="route_selection",
            data_schema=vol.Schema({
                vol.Required(CONF_ROUTE_ID): vol.In(route_options),
            }),
        )