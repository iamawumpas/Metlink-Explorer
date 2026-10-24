"""Live Metlink data: vehicle positions, trip updates and service alerts.

Each feed polls in its own task with its own failure handling, so one feed
failing never blocks another. Polling only runs while something is
subscribed. Realtime route ids don't match the static feed, so consumers
must map vehicles to routes through trip_id.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from .http import MetlinkAuthError, MetlinkBackoffError, MetlinkHttpClient, MetlinkHttpError

_LOGGER = logging.getLogger(__name__)

FEEDS = {
    "vehicles": "/gtfs-rt/vehiclepositions",
    "trip_updates": "/gtfs-rt/tripupdates",
    "alerts": "/gtfs-rt/servicealerts",
}
DEFAULT_INTERVALS = {"vehicles": 30.0, "trip_updates": 30.0, "alerts": 180.0}
SKIPPED = 1
CANCELED = 3


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def parse_vehicles(payload: Any) -> dict[str, dict[str, Any]]:
    """Vehicle id -> compact position record."""
    out: dict[str, dict[str, Any]] = {}
    for entity in _as_list((payload or {}).get("entity")):
        vehicle = entity.get("vehicle") or {}
        pos = vehicle.get("position") or {}
        trip = vehicle.get("trip") or {}
        if "latitude" not in pos or "longitude" not in pos:
            continue
        vid = str((vehicle.get("vehicle") or {}).get("id") or entity.get("id"))
        out[vid] = {
            "id": vid,
            "trip_id": trip.get("trip_id"),
            "direction_id": trip.get("direction_id"),
            "start_time": trip.get("start_time"),
            "lat": pos["latitude"],
            "lon": pos["longitude"],
            "bearing": pos.get("bearing"),
            "occupancy": vehicle.get("occupancy_status"),
            "timestamp": vehicle.get("timestamp"),
        }
    return out


def parse_trip_updates(payload: Any) -> dict[str, dict[str, Any]]:
    """trip_id -> {"canceled": bool, "updates": [per-stop records sorted by sequence]}."""
    out: dict[str, dict[str, Any]] = {}
    for entity in _as_list((payload or {}).get("entity")):
        update = entity.get("trip_update") or {}
        trip = update.get("trip") or {}
        trip_id = trip.get("trip_id")
        if not trip_id:
            continue
        record = out.setdefault(trip_id, {"canceled": False, "updates": []})
        if trip.get("schedule_relationship") == CANCELED:
            record["canceled"] = True
        for stu in _as_list(update.get("stop_time_update")):
            arrival, departure = stu.get("arrival") or {}, stu.get("departure") or {}
            record["updates"].append(
                {
                    "stop_id": stu.get("stop_id"),
                    "sequence": stu.get("stop_sequence"),
                    "delay": departure.get("delay", arrival.get("delay")),
                    "time": departure.get("time", arrival.get("time")),
                    "skipped": stu.get("schedule_relationship") == SKIPPED,
                }
            )
    for record in out.values():
        record["updates"].sort(key=lambda u: (u["sequence"] is None, u["sequence"] or 0))
    return out


def _translated(block: Any) -> str:
    for item in _as_list((block or {}).get("translation")):
        if item.get("text"):
            return item["text"]
    return ""


def parse_alerts(payload: Any) -> list[dict[str, Any]]:
    out = []
    for entity in _as_list((payload or {}).get("entity")):
        alert = entity.get("alert") or {}
        entities = _as_list(alert.get("informed_entity"))
        out.append(
            {
                "id": entity.get("id"),
                "cause": alert.get("cause"),
                "effect": alert.get("effect"),
                "severity": alert.get("severity_level"),
                "header": _translated(alert.get("header_text")),
                "description": _translated(alert.get("description_text")),
                "periods": [
                    {"start": p.get("start"), "end": p.get("end")}
                    for p in _as_list(alert.get("active_period"))
                ],
                "stop_ids": sorted({e["stop_id"] for e in entities if e.get("stop_id")}),
                "route_ids": sorted({str(e["route_id"]) for e in entities if e.get("route_id")}),
                "trip_ids": sorted({e["trip_id"] for e in entities if e.get("trip_id")}),
            }
        )
    return out


def apply_delays(
    deps: list[dict[str, Any]], trip_updates: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Add status, delay and expected time to scheduled departures.

    A delay at one stop carries on to the stops after it until the next
    update, as GTFS-RT defines.
    """
    for dep in deps:
        record = trip_updates.get(dep["trip_id"])
        dep["status"], dep["delay"], dep["timestamp_expected"] = "scheduled", None, dep["timestamp"]
        if record is None:
            continue
        if record["canceled"]:
            dep["status"] = "canceled"
            continue
        seq = dep.get("stop_sequence")
        match = None
        for upd in record["updates"]:
            if upd["stop_id"] == dep["stop_id"] and (upd["sequence"] in (None, seq)):
                match = upd
                break
            if upd["sequence"] is not None and seq is not None and upd["sequence"] <= seq:
                match = upd
        if match is None:
            continue
        exact = match["stop_id"] == dep["stop_id"] and match["sequence"] in (None, seq)
        if exact and match["skipped"]:
            dep["status"] = "skipped"
            continue
        if exact and match["time"]:
            dep["timestamp_expected"] = int(match["time"])
            dep["delay"] = int(match["time"]) - dep["timestamp"]
        elif match["delay"] is not None:
            dep["delay"] = int(match["delay"])
            dep["timestamp_expected"] = dep["timestamp"] + dep["delay"]
        else:
            continue
        dep["status"] = "delayed" if dep["delay"] >= 60 else "early" if dep["delay"] <= -60 else "on_time"
    return deps


@dataclass
class FeedState:
    ok: bool = False
    last_success: float | None = None
    last_error: str | None = None
    failures: int = 0


@dataclass
class RealtimeSnapshot:
    vehicles: dict[str, dict[str, Any]] = field(default_factory=dict)
    trip_updates: dict[str, dict[str, Any]] = field(default_factory=dict)
    alerts: list[dict[str, Any]] = field(default_factory=list)


class RealtimeService:
    """Polls the three realtime feeds while at least one subscriber is attached."""

    def __init__(
        self,
        http: MetlinkHttpClient,
        *,
        intervals: dict[str, float] | None = None,
        spawn: Callable[[Awaitable], asyncio.Task] | None = None,
        sleep: Callable[[float], Awaitable] = asyncio.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._http = http
        self._intervals = {**DEFAULT_INTERVALS, **(intervals or {})}
        self._spawn = spawn or asyncio.ensure_future
        self._sleep = sleep
        self._clock = clock
        self.snapshot = RealtimeSnapshot()
        self.state = {name: FeedState() for name in FEEDS}
        self._subscribers: dict[int, Callable[[str], None]] = {}
        self._next_id = 0
        self._tasks: dict[str, asyncio.Task] = {}

    @property
    def running(self) -> bool:
        return bool(self._tasks)

    def subscribe(self, callback: Callable[[str], None]) -> Callable[[], None]:
        """Register for per-feed updates; polling starts with the first subscriber."""
        self._next_id += 1
        key = self._next_id
        self._subscribers[key] = callback
        self._ensure_running()

        def unsubscribe() -> None:
            if self._subscribers.pop(key, None) is not None and not self._subscribers:
                self._cancel()

        return unsubscribe

    async def async_stop(self) -> None:
        self._subscribers.clear()
        tasks = list(self._tasks.values())
        self._cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def _ensure_running(self) -> None:
        for name in FEEDS:
            if name not in self._tasks:
                self._tasks[name] = self._spawn(self._loop(name))

    def _cancel(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()

    async def poll_once(self, name: str) -> float:
        """Fetch one feed. Returns seconds to wait before the next try."""
        state = self.state[name]
        interval = self._intervals[name]
        try:
            payload = await self._http.get_json(FEEDS[name])
            if name == "vehicles":
                self.snapshot.vehicles = parse_vehicles(payload)
            elif name == "trip_updates":
                self.snapshot.trip_updates = parse_trip_updates(payload)
            else:
                self.snapshot.alerts = parse_alerts(payload)
        except MetlinkAuthError as err:
            state.ok, state.last_error = False, f"auth: {err}"
            return -1
        except MetlinkBackoffError as err:
            state.ok, state.last_error = False, str(err)
            return max(err.retry_in, 1.0)
        except (MetlinkHttpError, ValueError, AttributeError, TypeError) as err:
            state.ok, state.last_error = False, str(err)
            state.failures += 1
            return interval
        state.ok, state.last_error, state.failures = True, None, 0
        state.last_success = self._clock()
        for callback in list(self._subscribers.values()):
            try:
                callback(name)
            except Exception:  # a broken subscriber must not stop polling
                _LOGGER.exception("Realtime subscriber failed")
        return interval

    async def _loop(self, name: str) -> None:
        try:
            while self._subscribers:
                wait = await self.poll_once(name)
                if wait < 0:
                    _LOGGER.error("Metlink API key rejected; stopping %s polling", name)
                    return
                await self._sleep(wait)
        except asyncio.CancelledError:
            raise
        finally:
            self._tasks.pop(name, None)

    def status(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "ok": s.ok,
                "last_success": s.last_success,
                "error": s.last_error,
                "failures": s.failures,
            }
            for name, s in self.state.items()
        }
