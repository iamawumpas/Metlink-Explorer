"""Home Assistant websocket commands (all authenticated, HA frontend only)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .core import api
from .core.service import MetlinkService

_LOGGER = logging.getLogger(__name__)

PREFIX = f"{DOMAIN}/"
SUBSCRIPTIONS = ("subscribe_vehicles", "subscribe_departures", "subscribe_alerts")


def _service(hass: HomeAssistant) -> MetlinkService | None:
    return hass.data.get(DOMAIN, {}).get("service")


def _make_handler(command: str):
    async def handler(hass: HomeAssistant, connection: Any, msg: dict[str, Any]) -> None:
        service = _service(hass)
        if service is None:
            connection.send_error(msg["id"], "not_ready", "Metlink Explorer is not set up")
            return
        try:
            if command in SUBSCRIPTIONS:
                send = lambda data: connection.send_message(websocket_api.event_message(msg["id"], data))  # noqa: E731
                if command == "subscribe_vehicles":
                    unsub, kick = await api.subscribe_vehicles(service, msg, send)
                elif command == "subscribe_alerts":
                    unsub, kick = await api.subscribe_alerts(service, msg, send)
                else:
                    unsub, kick = await api.subscribe_departures(service, msg, send, _spawner(hass))
            else:
                connection.send_result(msg["id"], await api.run_command(service, command, msg))
                return
        except api.ApiError as err:
            connection.send_error(msg["id"], err.code, str(err))
            return
        except Exception:  # keep one bad request from affecting the connection
            _LOGGER.exception("Metlink command %s failed", command)
            connection.send_error(msg["id"], "unknown_error", "Request failed")
            return
        # HA calls this when the card unsubscribes or the socket closes.
        connection.subscriptions[msg["id"]] = unsub
        connection.send_result(msg["id"])
        kick()

    return websocket_api.async_response(handler)


def _spawner(hass: HomeAssistant):
    def spawn(coro) -> None:
        hass.async_create_background_task(_guard(coro), "metlink_explorer_departures")

    return spawn


async def _guard(coro) -> None:
    try:
        await coro
    except Exception:
        _LOGGER.exception("Metlink departures refresh failed")


def _accept(msg: dict[str, Any]) -> dict[str, Any]:
    """HA calls the schema on every message; validation happens in core.api."""
    return msg


def async_register_commands(hass: HomeAssistant) -> None:
    for name in (*api.COMMANDS, *SUBSCRIPTIONS):
        websocket_api.async_register_command(hass, PREFIX + name, _make_handler(name), schema=_accept)
