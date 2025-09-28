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
            transportation_type = int(user_input[CONF_TRANSPORTATION_TYPE])
            self._transportation_type = transportation_type
            
            try:
                # Get available routes for this transportation type
                available_routes = await self._get_available_routes_for_type(transportation_type)
                if not available_routes:
                    errors["base"] = "no_routes_available"
                else:
                    self._available_routes = available_routes
                    return await self.async_step_route_selection()
            except MetlinkApiError:
                errors["base"] = "cannot_connect"

        # Get transportation types with available routes
        try:
            available_transport_options = await self._get_available_transportation_types()
            if not available_transport_options:
                errors["base"] = "no_transportation_types_available"
        except MetlinkApiError:
            errors["base"] = "cannot_connect"
            available_transport_options = {}

        # Fallback to all types if there's an error
        if not available_transport_options:
            available_transport_options = {
                str(type_id): f"{type_name}"
                for type_id, type_name in TRANSPORTATION_TYPES.items()
            }

        return self.async_show_form(
            step_id="transportation_type",
            data_schema=vol.Schema({
                vol.Required(CONF_TRANSPORTATION_TYPE): vol.In(available_transport_options),
            }),
            errors=errors,
        )

    async def _get_available_transportation_types(self) -> dict[str, str]:
        """Get transportation types that have available routes."""
        available_options = {}
        
        for type_id, type_name in TRANSPORTATION_TYPES.items():
            available_routes = await self._get_available_routes_for_type(type_id)
            if available_routes:
                route_count = len(available_routes)
                available_options[str(type_id)] = f"{type_name} ({route_count} routes available)"
                
        return available_options

    async def _get_available_routes_for_type(self, transportation_type: int) -> list[dict[str, Any]]:
        """Get routes for a transportation type that aren't already configured."""
        # Get all routes for this transportation type
        all_routes = await self._api_client.get_routes_by_type(transportation_type)
        
        # Get existing configured route IDs from all entries
        existing_entries = self._async_current_entries()
        configured_route_ids = set()
        
        for entry in existing_entries:
            if entry.data.get(CONF_ROUTE_ID):
                configured_route_ids.add(entry.data[CONF_ROUTE_ID])
        
        # Filter out already configured routes
        available_routes = [
            route for route in all_routes 
            if route.get("route_id") not in configured_route_ids
        ]
        
        return available_routes

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