"""Card-facing API: validated commands and live subscriptions.

Pure Python so it can be tested without Home Assistant. websocket.py maps
these onto HA websocket commands.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from ..const import DEFAULT_DEPARTURE_HORIZON_HOURS, DEFAULT_DEPARTURE_LIMIT, MAX_DEPARTURE_HORIZON_HOURS
from . import departures as dep
from . import queries
from .service import MetlinkService

MAX_LIMIT = 100
MODES = {"bus", "train", "ferry", "cable_car"}


class ApiError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _str(msg: dict, key: str, *, required: bool = False) -> str | None:
    value = msg.get(key)
    if value is None:
        if required:
            raise ApiError("invalid_format", f"'{key}' is required")
        return None
    if not isinstance(value, (str, int)) or isinstance(value, bool) or not str(value).strip():
        raise ApiError("invalid_format", f"'{key}' must be a non-empty string")
    return str(value)


def _str_list(msg: dict, key: str) -> list[str] | None:
    value = msg.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > 500 or not all(
        isinstance(v, (str, int)) and not isinstance(v, bool) for v in value
    ):
        raise ApiError("invalid_format", f"'{key}' must be a list of ids")
    return [str(v) for v in value]


def _int(msg: dict, key: str, default: int, low: int, high: int) -> int:
    value = msg.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApiError("invalid_format", f"'{key}' must be a whole number")
    return min(max(value, low), high)


def _mode(msg: dict) -> str | None:
    mode = _str(msg, "mode")
    if mode is not None and mode not in MODES:
        raise ApiError("invalid_format", f"'mode' must be one of {sorted(MODES)}")
    return mode


def _modes(msg: dict) -> list[str] | None:
    modes = _str_list(msg, "modes")
    if modes and not set(modes) <= MODES:
        raise ApiError("invalid_format", f"'modes' must be from {sorted(MODES)}")
    return modes


def _bbox(msg: dict) -> tuple[float, float, float, float] | None:
    box = msg.get("bbox")
    if box is None:
        return None
    if (
        not isinstance(box, list) or len(box) != 4
        or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in box)
    ):
        raise ApiError("invalid_format", "'bbox' must be [south, west, north, east]")
    south, west, north, east = (float(v) for v in box)
    return south, west, north, east


def _departure_args(msg: dict) -> dict[str, Any]:
    return {
        "towards": _str(msg, "towards"),
        "route_ids": _str_list(msg, "route_ids"),
        "limit": _int(msg, "limit", DEFAULT_DEPARTURE_LIMIT, 1, MAX_LIMIT),
        "horizon_hours": _int(msg, "horizon_hours", DEFAULT_DEPARTURE_HORIZON_HOURS, 1, MAX_DEPARTURE_HORIZON_HOURS),
    }


async def _known_stop(service: MetlinkService, stop_id: str) -> str:
    if not await dep.group_members(service.store, stop_id):
        raise ApiError("not_found", f"Unknown stop {stop_id}")
    return stop_id


async def _routes(s, m): return await queries.list_routes(s.store, _mode(m))


async def _stops(s, m):
    return await queries.list_stops(
        s.store, route_ids=_str_list(m, "route_ids"), mode=_mode(m),
        include_school=m.get("include_school", True) is not False, bbox=_bbox(m),
    )


async def _route(s, m):
    detail = await queries.route_detail(s.store, _str(m, "route_id", required=True))
    if detail is None:
        raise ApiError("not_found", "Unknown route")
    return detail


async def _shape(s, m):
    points = await queries.get_shape(s.store, _str(m, "shape_id", required=True))
    if points is None:
        raise ApiError("not_found", "Unknown shape")
    return {"shape_id": m["shape_id"], "points": points}


async def _stop_routes(s, m): return await queries.stop_routes(s.store, await _known_stop(s, _str(m, "stop_id", required=True)))
async def _destinations(s, m): return await dep.destinations(s.store, await _known_stop(s, _str(m, "stop_id", required=True)))
async def _reachable(s, m): return await dep.reachable(s.store, await _known_stop(s, _str(m, "stop_id", required=True)))


async def _departures(s, m):
    stop_id = await _known_stop(s, _str(m, "stop_id", required=True))
    return await s.departures(stop_id, **_departure_args(m))


async def _alerts(s, m): return s.alerts(_str_list(m, "stop_ids"), _str_list(m, "route_ids"))
async def _status(s, m): return await s.status()


COMMANDS: dict[str, Callable[[MetlinkService, dict], Awaitable[Any]]] = {
    "routes": _routes, "stops": _stops, "route": _route, "shape": _shape,
    "stop_routes": _stop_routes, "destinations": _destinations, "reachable": _reachable,
    "departures": _departures, "alerts": _alerts, "status": _status,
}


async def run_command(service: MetlinkService, name: str, msg: dict) -> Any:
    handler = COMMANDS.get(name)
    if handler is None:
        raise ApiError("unknown_command", f"Unknown command {name}")
    return await handler(service, msg)


Send = Callable[[Any], None]
Spawn = Callable[[Awaitable], Any]


async def subscribe_vehicles(
    service: MetlinkService, msg: dict, send: Send
) -> tuple[Callable[[], None], Callable[[], None]]:
    """Returns (unsubscribe, push_now). Updates follow every position poll."""
    args = {"route_ids": _str_list(msg, "route_ids"), "modes": _modes(msg), "bbox": _bbox(msg)}

    def push(feed: str | None = None) -> None:
        if feed in (None, "vehicles"):
            send(service.vehicles(**args))

    unsubscribe = service.realtime.subscribe(push)
    unsubscribe_ais = None
    if service.ais is not None and (not args["modes"] or "ferry" in args["modes"]):
        unsubscribe_ais = service.ais.subscribe(lambda: push("vehicles"))

    def stop() -> None:
        unsubscribe()
        if unsubscribe_ais:
            unsubscribe_ais()

    return stop, push


async def subscribe_departures(
    service: MetlinkService, msg: dict, send: Send, spawn: Spawn
) -> tuple[Callable[[], None], Callable[[], None]]:
    """Push departures when kicked and again whenever trip updates arrive."""
    stop_id = await _known_stop(service, _str(msg, "stop_id", required=True))
    args = _departure_args(msg)
    state = {"busy": False, "closed": False}

    async def refresh() -> None:
        try:
            rows = await service.departures(stop_id, **args)
            if not state["closed"]:
                send(rows)
        finally:
            state["busy"] = False

    def push(feed: str | None = None) -> None:
        if feed not in (None, "trip_updates") or state["busy"] or state["closed"]:
            return
        state["busy"] = True
        spawn(refresh())

    unsubscribe = service.realtime.subscribe(push)

    def stop() -> None:
        state["closed"] = True
        unsubscribe()

    return stop, push
