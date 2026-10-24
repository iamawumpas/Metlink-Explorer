"""Ferry positions from AISStream.

Exactly one websocket exists per service, and it only runs while at least one
map card is subscribed. Failures here never touch the Metlink feeds: the loop
backs off on rate limits, stops on a rejected key, and otherwise reconnects
with a growing delay.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

WS_URL = "wss://stream.aisstream.io/v0/stream"
# Wellington Harbour plus Eastbourne and Days Bay.
DEFAULT_BBOX = [[[-41.38, 174.73], [-41.21, 174.92]]]
MESSAGE_TYPES = ["PositionReport", "StandardClassBPositionReport", "ExtendedClassBPositionReport"]
DEFAULT_MMSIS = {
    "512003252": "Ferry",
    "512003410": "Ferry",
    "512010273": "Ferry",
}
STALE_AFTER_S = 15 * 60
MIN_PUSH_INTERVAL_S = 5.0
BACKOFF_START_S = 30.0
BACKOFF_MAX_S = 600.0
RATE_LIMIT_BACKOFF_S = 120.0
HEADING_UNKNOWN = 511


def parse_position(payload: Any, mmsis: set[str]) -> dict[str, Any] | None:
    """One AIS message -> a vehicle record, or None if it isn't a wanted position."""
    if not isinstance(payload, dict):
        return None
    msg_type = str(payload.get("MessageType") or "")
    if msg_type not in MESSAGE_TYPES:
        return None
    meta = payload.get("MetaData") or payload.get("Metadata") or {}
    mmsi = str(meta.get("MMSI") or "").strip()
    if mmsi not in mmsis:
        return None
    body = (payload.get("Message") or {}).get(msg_type) or {}
    lat = body.get("Latitude", meta.get("latitude"))
    lon = body.get("Longitude", meta.get("longitude"))
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    heading = body.get("TrueHeading")
    bearing = body.get("Cog") if heading in (None, HEADING_UNKNOWN) else heading
    speed = body.get("Sog")
    return {
        "id": f"ais:{mmsi}",
        "mmsi": mmsi,
        "name": str(meta.get("ShipName") or "").strip() or None,
        "lat": float(lat),
        "lon": float(lon),
        "bearing": bearing if isinstance(bearing, (int, float)) else None,
        "speed_knots": speed if isinstance(speed, (int, float)) else None,
    }


class AisService:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        *,
        mmsis: dict[str, str] | None = None,
        bbox: list | None = None,
        spawn: Callable[[Awaitable], asyncio.Task] | None = None,
        sleep: Callable[[float], Awaitable] = asyncio.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._session = session
        self._key = api_key
        self._mmsis = dict(mmsis or DEFAULT_MMSIS)
        self._bbox = bbox or DEFAULT_BBOX
        self._spawn = spawn or asyncio.ensure_future
        self._sleep = sleep
        self._clock = clock
        self._positions: dict[str, dict[str, Any]] = {}
        self._subscribers: dict[int, Callable[[], None]] = {}
        self._next_id = 0
        self._task: asyncio.Task | None = None
        self._last_push = 0.0
        self.connections = 0
        self.connected = False
        self.stopped_reason: str | None = None
        self.last_error: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    @property
    def running(self) -> bool:
        return self._task is not None

    def vehicles(self) -> list[dict[str, Any]]:
        cutoff = self._clock() - STALE_AFTER_S
        return [dict(v) for v in self._positions.values() if v["_seen"] >= cutoff]

    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._next_id += 1
        key = self._next_id
        self._subscribers[key] = callback
        if self.enabled and self._task is None and self.stopped_reason is None:
            self._task = self._spawn(self._run())

        def unsubscribe() -> None:
            if self._subscribers.pop(key, None) is not None and not self._subscribers:
                self._cancel()

        return unsubscribe

    async def async_stop(self) -> None:
        self._subscribers.clear()
        task = self._task
        self._cancel()
        if task:
            await asyncio.gather(task, return_exceptions=True)

    def _cancel(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
        self.connected = False

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "running": self.running,
            "connected": self.connected,
            "connections": self.connections,
            "stopped": self.stopped_reason,
            "error": self.last_error,
            "tracked": len(self.vehicles()),
        }

    def handle_payload(self, payload: Any) -> bool:
        """Store a position. Returns True if it was a wanted position."""
        report = parse_position(payload, set(self._mmsis))
        if report is None:
            return False
        report["name"] = report["name"] or self._mmsis.get(report["mmsi"])
        report["_seen"] = self._clock()
        self._positions[report["mmsi"]] = report
        self._notify()
        return True

    def _notify(self) -> None:
        now = self._clock()
        if now - self._last_push < MIN_PUSH_INTERVAL_S:
            return
        self._last_push = now
        for callback in list(self._subscribers.values()):
            try:
                callback()
            except Exception:  # a broken subscriber must not stop the stream
                _LOGGER.exception("AIS subscriber failed")

    async def _run(self) -> None:
        delay = BACKOFF_START_S
        try:
            while self._subscribers:
                outcome = await self._connect_once()
                self.connected = False
                if outcome == "auth":
                    self.stopped_reason = "AISStream rejected the API key"
                    _LOGGER.error("%s; ferry tracking stopped until the key is changed", self.stopped_reason)
                    return
                if outcome == "rate_limited":
                    wait = RATE_LIMIT_BACKOFF_S
                elif outcome == "clean":
                    delay, wait = BACKOFF_START_S, BACKOFF_START_S
                else:
                    wait = delay
                    delay = min(delay * 2, BACKOFF_MAX_S)
                await self._sleep(wait)
        except asyncio.CancelledError:
            raise
        finally:
            self.connected = False
            self._task = None

    async def _connect_once(self) -> str:
        """One websocket session. Returns clean, auth, rate_limited or error."""
        subscription = {
            "APIKey": self._key,
            "BoundingBoxes": self._bbox,
            "FilterMessageTypes": MESSAGE_TYPES,
        }
        try:
            async with self._session.ws_connect(WS_URL, heartbeat=15) as ws:
                self.connections += 1
                await ws.send_str(json.dumps(subscription))
                self.connected = True
                self.last_error = None
                received = False
                async for msg in ws:
                    if msg.type not in (aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.BINARY):
                        break
                    try:
                        payload = json.loads(msg.data)
                    except (ValueError, TypeError):
                        continue
                    if isinstance(payload, dict) and payload.get("error"):
                        text = str(payload["error"])
                        self.last_error = text
                        lowered = text.lower()
                        if "429" in lowered or "rate" in lowered or "too many" in lowered:
                            return "rate_limited"
                        if "key" in lowered or "auth" in lowered or "unauthor" in lowered:
                            return "auth"
                        return "error"
                    received = True
                    self.handle_payload(payload)
                return "clean" if received else "error"
        except aiohttp.WSServerHandshakeError as err:
            self.last_error = f"HTTP {err.status}"
            if err.status in (401, 403):
                return "auth"
            return "rate_limited" if err.status == 429 else "error"
        except asyncio.CancelledError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
            self.last_error = str(err) or type(err).__name__
            return "error"
