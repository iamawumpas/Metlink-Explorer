"""Config flow for Metlink Explorer integration."""
from __future__ import annotations

import logging
import re
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
    CONF_ACTIVE_DIRECTION,
    CONF_API_KEY,
    CONF_LEGACY_DIRECTION_ENTITIES,
    CONF_TRANSPORTATION_TYPE,
    CONF_ROUTE_ID,
    CONF_ROUTE_SHORT_NAME,
    CONF_ROUTE_LONG_NAME,
    CONF_ROUTE_DESC,
    CONF_ROUTES,
    DEFAULT_ACTIVE_DIRECTION,
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
        """Get routes for a transportation type that aren't already configured as entities."""
        # Get all routes for this transportation type from the API
        all_routes = await self._api_client.get_routes_by_type(transportation_type)
        
        # Get existing configured route IDs from ALL integration entries
        existing_entries = self._async_current_entries()
        configured_route_ids = set()
        
        for entry in existing_entries:
            entry_routes = entry.data.get(CONF_ROUTES)
            if isinstance(entry_routes, list) and entry_routes:
                for route in entry_routes:
                    rid = route.get(CONF_ROUTE_ID)
                    if rid:
                        configured_route_ids.add(rid)
                        _LOGGER.debug("Found existing route configuration: %s (%s)", rid, entry.title)
            else:
                # Legacy single-route entry support
                entry_route_id = entry.data.get(CONF_ROUTE_ID)
                if entry_route_id:
                    configured_route_ids.add(entry_route_id)
                    _LOGGER.debug(
                        "Found existing route configuration: %s (%s)",
                        entry_route_id,
                        entry.title,
                    )
        
        # Filter out routes that are already configured as entities
        available_routes = []
        for route in all_routes:
            route_id = route.get("route_id")
            if route_id not in configured_route_ids:
                available_routes.append(route)
            else:
                _LOGGER.debug(
                    "Filtering out already configured route: %s (%s :: %s)",
                    route_id,
                    route.get("route_short_name", "Unknown"),
                    route.get("route_long_name", "Unknown Route")
                )
        
        _LOGGER.info(
            "Transportation type %s: %d total routes, %d already configured, %d available",
            transportation_type,
            len(all_routes),
            len(configured_route_ids),
            len(available_routes)
        )
        
        return available_routes

    async def async_step_route_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle route selection with advanced filtering and sorting."""
        errors: dict[str, str] = {}

        if user_input is not None:
            route_id = user_input[CONF_ROUTE_ID]
            
            # Find the selected route details
            selected_route = next(
                (route for route in self._available_routes if route["route_id"] == route_id),
                None
            )
            
            if selected_route:
                transportation_name = TRANSPORTATION_TYPES.get(self._transportation_type, "Unknown")
                route_short_name = selected_route["route_short_name"]
                route_long_name = selected_route["route_long_name"] 
                route_desc = selected_route.get("route_desc", "")  # Direction 1 description

                new_route = {
                    CONF_ROUTE_ID: route_id,
                    CONF_ROUTE_SHORT_NAME: route_short_name,
                    CONF_ROUTE_LONG_NAME: route_long_name,
                    CONF_ROUTE_DESC: route_desc,
                }

                # Single-entry per mode behavior: append routes to existing mode entry when present.
                existing_mode_entry = next(
                    (
                        entry for entry in self._async_current_entries()
                        if entry.data.get(CONF_API_KEY) == self._api_key
                        and int(entry.data.get(CONF_TRANSPORTATION_TYPE, -1)) == int(self._transportation_type)
                    ),
                    None,
                )

                if existing_mode_entry:
                    existing_routes = existing_mode_entry.data.get(CONF_ROUTES)
                    if not isinstance(existing_routes, list) or not existing_routes:
                        # Convert legacy single-route entry to list format.
                        existing_routes = [
                            {
                                CONF_ROUTE_ID: existing_mode_entry.data.get(CONF_ROUTE_ID),
                                CONF_ROUTE_SHORT_NAME: existing_mode_entry.data.get(CONF_ROUTE_SHORT_NAME),
                                CONF_ROUTE_LONG_NAME: existing_mode_entry.data.get(CONF_ROUTE_LONG_NAME),
                                CONF_ROUTE_DESC: existing_mode_entry.data.get(CONF_ROUTE_DESC, ""),
                            }
                        ]

                    if any(str(r.get(CONF_ROUTE_ID)) == str(route_id) for r in existing_routes):
                        return self.async_abort(reason="already_configured")

                    existing_routes.append(new_route)
                    updated_data = dict(existing_mode_entry.data)
                    updated_data[CONF_ROUTES] = existing_routes
                    # Keep legacy fields populated from the first route for compatibility.
                    if existing_routes:
                        updated_data[CONF_ROUTE_ID] = existing_routes[0].get(CONF_ROUTE_ID)
                        updated_data[CONF_ROUTE_SHORT_NAME] = existing_routes[0].get(CONF_ROUTE_SHORT_NAME)
                        updated_data[CONF_ROUTE_LONG_NAME] = existing_routes[0].get(CONF_ROUTE_LONG_NAME)
                        updated_data[CONF_ROUTE_DESC] = existing_routes[0].get(CONF_ROUTE_DESC, "")

                    self.hass.config_entries.async_update_entry(
                        existing_mode_entry,
                        title=f"{transportation_name}",
                        data=updated_data,
                    )
                    await self.hass.config_entries.async_reload(existing_mode_entry.entry_id)
                    return self.async_abort(reason="route_added_to_existing")

                # Create a new mode entry for first selected route.
                return self.async_create_entry(
                    title=f"{transportation_name}",
                    data={
                        CONF_API_KEY: self._api_key,
                        CONF_TRANSPORTATION_TYPE: self._transportation_type,
                        CONF_ROUTE_ID: route_id,
                        CONF_ROUTE_SHORT_NAME: route_short_name,
                        CONF_ROUTE_LONG_NAME: route_long_name,
                        CONF_ROUTE_DESC: route_desc,
                        CONF_ROUTES: [new_route],
                    },
                    options={
                        CONF_ACTIVE_DIRECTION: DEFAULT_ACTIVE_DIRECTION,
                        CONF_LEGACY_DIRECTION_ENTITIES: True,
                    },
                )
            else:
                errors["base"] = "route_not_found"

        # Double-check available routes (exclude already configured ones)
        try:
            self._available_routes = await self._get_available_routes_for_type(self._transportation_type)
            if not self._available_routes:
                errors["base"] = "no_routes_available"
        except MetlinkApiError:
            errors["base"] = "cannot_connect"

        # Create route options with intelligent alphanumeric sorting
        route_options = self._create_sorted_route_options(self._available_routes)
        
        if not route_options:
            errors["base"] = "no_routes_available"

        return self.async_show_form(
            step_id="route_selection",
            data_schema=vol.Schema({
                vol.Required(CONF_ROUTE_ID): vol.In(route_options),
            }),
            errors=errors,
        )

    def _create_sorted_route_options(self, routes: list[dict[str, Any]]) -> dict[str, str]:
        """Create route options with intelligent alphanumeric sorting."""
        if not routes:
            return {}

        # Sort routes using intelligent alphanumeric logic
        def sort_key(route):
            short_name = route.get("route_short_name", "")
            
            # Handle empty or None values
            if not short_name:
                return (2, "zzz", short_name.lower() if short_name else "")
            
            # Try to extract numeric portion for proper sorting
            # Look for numbers at the start of the route name
            numeric_match = re.match(r'^(\d+)', str(short_name))
            if numeric_match:
                # Route starts with number (e.g., "1", "83", "220")
                numeric_part = int(numeric_match.group(1))
                text_part = str(short_name)[len(str(numeric_part)):].lower()
                return (0, numeric_part, text_part)
            
            # Check for mixed formats (e.g., "31x", "60e")
            mixed_match = re.match(r'^(\d+)([a-zA-Z]+)', str(short_name))
            if mixed_match:
                numeric_part = int(mixed_match.group(1))
                text_part = mixed_match.group(2).lower()
                return (0, numeric_part, text_part)
            
            # Pure text routes (e.g., "AX", "KPL", "CCL")
            return (1, 0, str(short_name).lower())

        sorted_routes = sorted(routes, key=sort_key)
        
        # Create options dictionary with enhanced display format
        route_options = {}
        for route in sorted_routes:
            route_id = route["route_id"]
            route_short_name = route.get("route_short_name", "Unknown")
            route_long_name = route.get("route_long_name", "Unknown Route")
            
            # Use the specified format: route_short_name :: route_long_name
            display_text = f"{route_short_name} :: {route_long_name}"
            route_options[route_id] = display_text
            
        return route_options

