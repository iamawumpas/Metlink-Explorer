"""The Metlink Explorer integration."""
from __future__ import annotations

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MetlinkApiClient
from .coordinator import MetlinkDataUpdateCoordinator, MetlinkRouteGeometryCoordinator
from .const import (
    CONF_API_KEY,
    CONF_ROUTE_DESC,
    CONF_ROUTE_ID,
    CONF_ROUTE_LONG_NAME,
    CONF_ROUTE_SHORT_NAME,
    CONF_ROUTES,
    CONF_TRANSPORTATION_TYPE,
    TRAIN_GEOMETRY_SENSOR_KEY,
    TRAIN_ROUTE_TYPE,
    TRANSPORTATION_TYPES,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SELECT, Platform.DEVICE_TRACKER]


def _entry_routes(entry: ConfigEntry) -> list[dict[str, str]]:
    """Return routes list for an entry with legacy compatibility."""
    routes = entry.data.get(CONF_ROUTES)
    if isinstance(routes, list) and routes:
        return routes
    if entry.data.get(CONF_ROUTE_ID):
        return [
            {
                CONF_ROUTE_ID: entry.data.get(CONF_ROUTE_ID),
                CONF_ROUTE_SHORT_NAME: entry.data.get(CONF_ROUTE_SHORT_NAME),
                CONF_ROUTE_LONG_NAME: entry.data.get(CONF_ROUTE_LONG_NAME),
                CONF_ROUTE_DESC: entry.data.get(CONF_ROUTE_DESC, ""),
            }
        ]
    return []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Metlink Explorer from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    routes = _entry_routes(entry)

    # Consolidate legacy duplicate entries for the same API key + transportation type.
    same_mode_entries = sorted(
        [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.data.get(CONF_API_KEY) == entry.data.get(CONF_API_KEY)
            and e.data.get(CONF_TRANSPORTATION_TYPE) == entry.data.get(CONF_TRANSPORTATION_TYPE)
        ],
        key=lambda e: e.entry_id,
    )
    if same_mode_entries:
        leader = same_mode_entries[0]
        merged_routes: list[dict[str, str]] = []
        merged_route_ids: set[str] = set()

        # Always union all configured routes across matching entries so leader
        # setup can initialize coordinators for every installed route.
        for grouped_entry in same_mode_entries:
            for route in _entry_routes(grouped_entry):
                rid = str(route.get(CONF_ROUTE_ID, "")).strip()
                if not rid or rid in merged_route_ids:
                    continue
                merged_route_ids.add(rid)
                merged_routes.append(route)

        if merged_routes:
            updated_data = dict(leader.data)
            updated_data[CONF_ROUTES] = merged_routes
            updated_data[CONF_ROUTE_ID] = merged_routes[0].get(CONF_ROUTE_ID)
            updated_data[CONF_ROUTE_SHORT_NAME] = merged_routes[0].get(CONF_ROUTE_SHORT_NAME)
            updated_data[CONF_ROUTE_LONG_NAME] = merged_routes[0].get(CONF_ROUTE_LONG_NAME)
            updated_data[CONF_ROUTE_DESC] = merged_routes[0].get(CONF_ROUTE_DESC, "")
            title = TRANSPORTATION_TYPES.get(int(leader.data.get(CONF_TRANSPORTATION_TYPE, -1)), leader.title)
            if updated_data != leader.data or title != leader.title:
                hass.config_entries.async_update_entry(leader, data=updated_data, title=title)

        if entry.entry_id != leader.entry_id:
            await hass.config_entries.async_reload(leader.entry_id)
            await hass.config_entries.async_remove(entry.entry_id)
            return False

        # Leader setup should use merged routes immediately, even before reloads.
        if merged_routes:
            routes = merged_routes

    session = async_get_clientsession(hass)
    api_client = MetlinkApiClient(
        entry.data[CONF_API_KEY],
        session,
        transportation_type=entry.data.get(CONF_TRANSPORTATION_TYPE),
    )

    coordinators: dict[str, MetlinkDataUpdateCoordinator] = {}
    for route in routes:
        route_id = str(route.get(CONF_ROUTE_ID))
        if not route_id:
            continue
        coordinator = MetlinkDataUpdateCoordinator(hass, api_client, route_id)
        await coordinator.async_config_entry_first_refresh()
        coordinators[route_id] = coordinator

    hass.data[DOMAIN][entry.entry_id] = {
        "api_client": api_client,
        "coordinators": coordinators,
        # Keep legacy key for code paths that still expect one coordinator.
        "coordinator": next(iter(coordinators.values())) if coordinators else None,
        "routes": routes,
    }

    if int(entry.data.get(CONF_TRANSPORTATION_TYPE, -1)) == TRAIN_ROUTE_TYPE:
        geometry_route_ids: list[str] = []
        seen_route_ids: set[str] = set()

        # Build geometry from installed routes only, unioned across all train
        # entries sharing this API key.
        train_entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.data.get(CONF_API_KEY) == entry.data.get(CONF_API_KEY)
            and int(e.data.get(CONF_TRANSPORTATION_TYPE, -1)) == TRAIN_ROUTE_TYPE
        ]
        if not train_entries:
            train_entries = [entry]

        for train_entry in train_entries:
            for route in _entry_routes(train_entry):
                route_id = str(route.get(CONF_ROUTE_ID, "")).strip()
                if not route_id or route_id in seen_route_ids:
                    continue
                seen_route_ids.add(route_id)
                geometry_route_ids.append(route_id)

        if not geometry_route_ids:
            geometry_route_ids = [
                str(route.get(CONF_ROUTE_ID))
                for route in routes
                if route.get(CONF_ROUTE_ID)
            ]

        geometry_coordinator = MetlinkRouteGeometryCoordinator(
            hass,
            api_client,
            mode_key=TRAIN_GEOMETRY_SENSOR_KEY,
            route_ids=geometry_route_ids,
        )
        await geometry_coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id]["geometry_coordinator"] = geometry_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok