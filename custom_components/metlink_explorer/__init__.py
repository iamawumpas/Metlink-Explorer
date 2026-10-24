"""Metlink Explorer v2: a data service for the Metlink cards.

Static timetables live in SQLite and are refreshed daily. Live data is only
fetched while a card is subscribed. Everything is served over authenticated
Home Assistant websocket commands, so there are no entities.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from .const import (
    CONF_METLINK_KEY,
    DOMAIN,
    FRONTEND_URL_BASE,
    METLINK_BASE_URL,
    STATIC_CHECK_INTERVAL_HOURS,
    STATIC_DB_FILENAME,
)
from .core.http import MetlinkHttpClient
from .core.realtime import RealtimeService
from .core.service import MetlinkService
from .core.static_sync import StaticSync
from .core.store import Store
from .websocket import async_register_commands

_LOGGER = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent / "frontend"
CARD_FILES = ("metlink-departure-board-card.js",)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("frontend"):
        return
    version = (await async_get_integration(hass, DOMAIN)).version
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_URL_BASE, str(FRONTEND_DIR), cache_headers=False)]
    )
    for name in CARD_FILES:
        add_extra_js_url(hass, f"{FRONTEND_URL_BASE}/{name}?v={version}")
    async_register_commands(hass)
    domain_data["frontend"] = True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    db_path = Path(hass.config.path(STATIC_DB_FILENAME))

    store = Store(db_path)
    sync = StaticSync(session, store, db_path)
    await sync.async_open()

    http = MetlinkHttpClient(session, entry.data[CONF_METLINK_KEY], base_url=METLINK_BASE_URL)
    realtime = RealtimeService(
        http,
        spawn=lambda coro: entry.async_create_background_task(hass, coro, "metlink_explorer_realtime"),
    )
    service = MetlinkService(store, sync, realtime, dt_util.now)
    await service.async_reload_index()

    async def refresh_static(_now: datetime | None = None) -> None:
        result = await sync.async_sync()
        if result.status == "updated":
            await service.async_reload_index()
        elif result.status == "failed":
            _LOGGER.warning("Static timetable check failed; keeping the existing data")

    # The first download takes a while, so it must not hold up Home Assistant's startup.
    entry.async_create_background_task(hass, refresh_static(), "metlink_explorer_static_sync")
    entry.async_on_unload(
        async_track_time_interval(hass, refresh_static, timedelta(hours=STATIC_CHECK_INTERVAL_HOURS))
    )

    hass.data.setdefault(DOMAIN, {})["service"] = service
    await _async_register_frontend(hass)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    service: MetlinkService | None = hass.data.get(DOMAIN, {}).pop("service", None)
    if service is not None:
        await service.realtime.async_stop()
        await service.store.close()
    return True
