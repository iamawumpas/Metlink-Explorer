"""Glue between the static database, the realtime feeds and the card-facing API."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from ..const import DEFAULT_DEPARTURE_HORIZON_HOURS, DEFAULT_DEPARTURE_LIMIT
from . import departures as dep
from .realtime import RealtimeService, apply_delays
from .static_sync import StaticSync
from .store import Store


class MetlinkService:
    def __init__(
        self,
        store: Store,
        sync: StaticSync | None,
        realtime: RealtimeService,
        now: Callable[[], datetime],
    ) -> None:
        self.store = store
        self.sync = sync
        self.realtime = realtime
        self._now = now
        self._trips: dict[str, tuple[str, int]] = {}
        self._routes: dict[str, dict[str, Any]] = {}

    async def async_reload_index(self) -> None:
        """Rebuild the trip and route lookups. Call after every static sync."""
        self._trips = {t: (r, d) for t, r, d in await self.store.query(
            "SELECT trip_id, route_id, direction_id FROM trips")}
        self._routes = {
            rid: {"route": short, "mode": mode, "is_school": bool(school), "color": color}
            for rid, short, mode, school, color in await self.store.query(
                "SELECT route_id, short_name, mode, is_school, color FROM routes")
        }

    def vehicles(
        self,
        route_ids: list[str] | None = None,
        modes: list[str] | None = None,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[dict[str, Any]]:
        """Live vehicles. Realtime route ids don't match the static feed, so the
        route is looked up from the trip id."""
        wanted = set(route_ids or [])
        out = []
        for vehicle in self.realtime.snapshot.vehicles.values():
            trip = self._trips.get(vehicle.get("trip_id") or "")
            route = self._routes.get(trip[0]) if trip else None
            if (wanted and (trip is None or trip[0] not in wanted)) or (
                modes and (route is None or route["mode"] not in modes)
            ):
                continue
            if bbox and not (bbox[0] <= vehicle["lat"] <= bbox[2] and bbox[1] <= vehicle["lon"] <= bbox[3]):
                continue
            out.append(
                {
                    **vehicle,
                    "route_id": trip[0] if trip else None,
                    "route": route["route"] if route else None,
                    "mode": route["mode"] if route else None,
                    "is_school": route["is_school"] if route else False,
                    "color": route["color"] if route else None,
                    "kind": "vehicle",
                }
            )
        return out

    async def departures(
        self,
        stop_id: str,
        *,
        towards: str | None = None,
        route_ids: list[str] | None = None,
        limit: int = DEFAULT_DEPARTURE_LIMIT,
        horizon_hours: int = DEFAULT_DEPARTURE_HORIZON_HOURS,
    ) -> list[dict[str, Any]]:
        rows = await dep.departures(
            self.store, stop_id, self._now(), towards=towards, route_ids=route_ids,
            limit=limit, horizon_hours=horizon_hours,
        )
        return apply_delays(rows, self.realtime.snapshot.trip_updates)

    def alerts(self, stop_ids: list[str] | None = None, route_ids: list[str] | None = None) -> list[dict[str, Any]]:
        stops, routes = set(stop_ids or []), set(route_ids or [])
        if not stops and not routes:
            return list(self.realtime.snapshot.alerts)
        return [
            a for a in self.realtime.snapshot.alerts
            if stops.intersection(a["stop_ids"]) or routes.intersection(a["route_ids"])
        ]

    async def status(self) -> dict[str, Any]:
        feed_version = await self.store.get_meta("feed_version")
        checked = await self.store.get_meta("last_checked")
        return {
            "static": {"feed_version": feed_version, "last_checked": checked},
            "realtime": self.realtime.status(),
            "subscribers_active": self.realtime.running,
        }
