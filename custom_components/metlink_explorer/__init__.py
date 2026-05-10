"""The Metlink Explorer integration."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
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
from .mode_registry import entry_routes, entry_routes_from_data, merged_routes, same_mode_entries

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SELECT, Platform.DEVICE_TRACKER]

FRONTEND_URL_BASE = "/metlink_explorer_frontend"
FRONTEND_DIR = Path(__file__).parent / "frontend"
MANIFEST_PATH = Path(__file__).parent / "manifest.json"
SERVICE_SET_LIVE_TRACKING = "set_live_tracking"


def _transport_type_matches(entry_transport_type: int, requested: str | int | None) -> bool:
    """Return True if service request transport type matches entry mode."""
    if requested is None:
        return True

    # Numeric request path (e.g. 2, 3, 4, 712)
    try:
        requested_num = int(requested)
        return int(entry_transport_type) == requested_num
    except (TypeError, ValueError):
        pass

    # Slug request path from frontend editor (train, bus, ferry, cable)
    requested_slug = str(requested).strip().lower()
    entry_name = TRANSPORTATION_TYPES.get(int(entry_transport_type), "").lower().replace(" ", "_")

    if requested_slug == "cable":
        requested_slug = "cable_car"

    if requested_slug == "bus":
        return entry_name in {"bus", "school_bus"}

    return entry_name == requested_slug


def _update_route_live_tracking(
    routes: list[dict[str, str]],
    route_id: str,
    live_tracking: bool,
) -> tuple[list[dict[str, str]], bool]:
    """Return updated routes and whether any route changed."""
    changed = False
    new_routes: list[dict[str, str]] = []
    for route in routes:
        updated_route = dict(route)
        if str(updated_route.get(CONF_ROUTE_ID, "")).strip() == route_id:
            if bool(updated_route.get("live_tracking", True)) != live_tracking:
                updated_route["live_tracking"] = live_tracking
                changed = True
        new_routes.append(updated_route)
    return new_routes, changed


async def _async_frontend_asset_version(hass: HomeAssistant) -> str:
    """Return frontend cache-busting version from manifest.

    File IO runs in the executor to avoid blocking the HA event loop.
    """

    def _read_manifest_version() -> str:
        try:
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            return str(manifest.get("version", "dev"))
        except Exception:  # pragma: no cover - best effort fallback
            return "dev"

    return await hass.async_add_executor_job(_read_manifest_version)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register frontend static path and card resource."""
    hass.data.setdefault(DOMAIN, {})

    asset_version = await _async_frontend_asset_version(hass)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_URL_BASE, str(FRONTEND_DIR), cache_headers=False)]
    )
    add_extra_js_url(hass, f"{FRONTEND_URL_BASE}/metlink-explorer-map-card.js?v={asset_version}")
    add_extra_js_url(hass, f"{FRONTEND_URL_BASE}/metlink-departure-board-card.js?v={asset_version}")

    async def _async_handle_set_live_tracking(call) -> None:
        """Persist per-route live tracking in config entries and active coordinators."""
        route_id = str(call.data.get("route_id", "")).strip()
        if not route_id:
            return

        live_tracking = bool(call.data.get("live_tracking", True))
        requested_transport = call.data.get("transportation_type")

        for entry in hass.config_entries.async_entries(DOMAIN):
            entry_transport_type = int(entry.data.get(CONF_TRANSPORTATION_TYPE, -1))
            if not _transport_type_matches(entry_transport_type, requested_transport):
                continue

            normalized_routes = entry_routes(entry)
            new_routes, changed = _update_route_live_tracking(normalized_routes, route_id, live_tracking)
            if not changed:
                continue

            updated_data = dict(entry.data)
            updated_data[CONF_ROUTES] = new_routes

            # Keep legacy single-route compatibility field in sync.
            if str(updated_data.get(CONF_ROUTE_ID, "")).strip() == route_id:
                updated_data["live_tracking"] = live_tracking

            hass.config_entries.async_update_entry(entry, data=updated_data)

            runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
            if runtime:
                runtime["routes"] = entry_routes_from_data(updated_data)

                coordinators = runtime.get("coordinators", {})
                coordinator = coordinators.get(route_id)
                if coordinator is not None:
                    coordinator.live_tracking_enabled = live_tracking
                    await coordinator.async_request_refresh()

                geometry_coordinator = runtime.get("geometry_coordinator")
                if geometry_coordinator is not None:
                    geometry_coordinator.route_live_tracking_map[route_id] = live_tracking
                    await geometry_coordinator.async_request_refresh()

    if not hass.services.has_service(DOMAIN, SERVICE_SET_LIVE_TRACKING):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_LIVE_TRACKING,
            _async_handle_set_live_tracking,
            schema=vol.Schema(
                {
                    vol.Required("route_id"): str,
                    vol.Required("live_tracking"): bool,
                    vol.Optional("transportation_type"): vol.Any(str, int),
                }
            ),
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Metlink Explorer from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    routes = entry_routes(entry)

    # Consolidate legacy duplicate entries for the same API key + transportation type.
    grouped_mode_entries = same_mode_entries(
        hass,
        entry.data.get(CONF_API_KEY),
        entry.data.get(CONF_TRANSPORTATION_TYPE),
    )
    if grouped_mode_entries:
        leader = grouped_mode_entries[0]
        merged = merged_routes(grouped_mode_entries)

        if merged:
            updated_data = dict(leader.data)
            updated_data[CONF_ROUTES] = merged
            updated_data[CONF_ROUTE_ID] = merged[0].get(CONF_ROUTE_ID)
            updated_data[CONF_ROUTE_SHORT_NAME] = merged[0].get(CONF_ROUTE_SHORT_NAME)
            updated_data[CONF_ROUTE_LONG_NAME] = merged[0].get(CONF_ROUTE_LONG_NAME)
            updated_data[CONF_ROUTE_DESC] = merged[0].get(CONF_ROUTE_DESC, "")
            title = TRANSPORTATION_TYPES.get(int(leader.data.get(CONF_TRANSPORTATION_TYPE, -1)), leader.title)
            if updated_data != leader.data or title != leader.title:
                hass.config_entries.async_update_entry(leader, data=updated_data, title=title)

        if entry.entry_id != leader.entry_id:
            await hass.config_entries.async_reload(leader.entry_id)
            await hass.config_entries.async_remove(entry.entry_id)
            return False

        # Leader setup should use merged routes immediately, even before reloads.
        if merged:
            routes = merged

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
        # Default live_tracking to True for backward compatibility (existing routes)
        live_tracking_enabled = route.get("live_tracking", True)
        coordinator = MetlinkDataUpdateCoordinator(
            hass, api_client, route_id, live_tracking_enabled=live_tracking_enabled
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators[route_id] = coordinator

    hass.data[DOMAIN][entry.entry_id] = {
        "api_client": api_client,
        "coordinators": coordinators,
        # Keep legacy key for code paths that still expect one coordinator.
        "coordinator": next(iter(coordinators.values())) if coordinators else None,
        "routes": routes,
    }

    # Build route geometry coordinator for all transportation modes.
    # Geometry is based on weekly-cached GTFS shapes and is mode-agnostic.
    transport_type_int = int(entry.data.get(CONF_TRANSPORTATION_TYPE, -1))
    if transport_type_int in TRANSPORTATION_TYPES:
        geometry_route_ids: list[str] = []
        seen_route_ids: set[str] = set()

        if transport_type_int == TRAIN_ROUTE_TYPE:
            # Union installed train routes across all train entries for this API key.
            source_entries = same_mode_entries(hass, entry.data.get(CONF_API_KEY), TRAIN_ROUTE_TYPE) or [entry]
            geo_mode_key = TRAIN_GEOMETRY_SENSOR_KEY
        else:
            source_entries = [entry]
            type_name = TRANSPORTATION_TYPES.get(transport_type_int, "unknown")
            geo_mode_key = f"{type_name.lower().replace(' ', '_')}_geometry"

        for source_entry in source_entries:
            for route in entry_routes(source_entry):
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

        route_live_tracking_map = {
            str(route.get(CONF_ROUTE_ID)): bool(route.get("live_tracking", True))
            for route in routes
            if route.get(CONF_ROUTE_ID)
        }

        geometry_coordinator = MetlinkRouteGeometryCoordinator(
            hass,
            api_client,
            mode_key=geo_mode_key,
            route_ids=geometry_route_ids,
            route_live_tracking_map=route_live_tracking_map,
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