"""Database-focused coordinators for the v1.0.0 local JSON pipeline."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MetlinkApiClient, MetlinkApiError
from .const import (
    DB_ALERTS_FILENAME,
    DB_REFRESH_ALERTS_SECONDS,
    DB_REFRESH_ROUTES_SECONDS,
    DB_REFRESH_SCHEDULES_SECONDS,
    DB_ROUTE_GEOMETRY_FILENAME_TEMPLATE,
    DB_ROUTES_FILENAME_TEMPLATE,
    DB_SCHEDULES_FILENAME_TEMPLATE,
    DB_STOPS_FILENAME_TEMPLATE,
    DOMAIN,
)
from .db_manager import async_update_meta, async_write_db_file

_LOGGER = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    """Return current UTC timestamp for JSON payloads."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _service_datetime(service_date: str | None, departure_time: str | None) -> datetime | None:
    """Convert GTFS date/time strings to local datetime.

    Supports hours >= 24 used by overnight trips.
    """
    if not service_date or not departure_time:
        return None

    date_text = str(service_date).strip()
    time_text = str(departure_time).replace("Scheduled:", "").strip()
    if len(date_text) != 8 or not date_text.isdigit():
        return None

    try:
        base = datetime.strptime(date_text, "%Y%m%d")
        parts = time_text.split(":")
        if len(parts) < 2:
            return None
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
        return base + timedelta(hours=hour, minutes=minute, seconds=second)
    except Exception:
        return None


class MetlinkStaticDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Build and write static per-mode route, geometry, and stop files."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: MetlinkApiClient,
        mode_slug: str,
        route_ids: list[str],
    ) -> None:
        self.api_client = api_client
        self.mode_slug = str(mode_slug)
        self.route_ids = [str(rid) for rid in route_ids if str(rid).strip()]

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.mode_slug}_db_static",
            update_interval=timedelta(seconds=DB_REFRESH_ROUTES_SECONDS),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            geojson = await self.api_client.get_mode_routes_geojson(self.route_ids)
            features = geojson.get("features", []) if isinstance(geojson, dict) else []
            if not isinstance(features, list):
                features = []

            generated_at = _utc_now_iso()

            route_rows: list[dict[str, Any]] = []
            stops_rows: list[dict[str, Any]] = []

            for feature in features:
                if not isinstance(feature, dict):
                    continue
                props = feature.get("properties", {})
                if not isinstance(props, dict):
                    props = {}
                route_id = str(props.get("route_id", "")).strip()
                if not route_id:
                    continue

                route_rows.append(
                    {
                        "route_id": route_id,
                        "route_short_name": str(props.get("route_short_name") or route_id),
                        "shape_count": int(props.get("shape_count") or 0),
                        "inbound_direction_id": next(
                            (
                                v.get("inbound_direction_id")
                                for v in (props.get("stop_pair_index") or {}).values()
                                if isinstance(v, dict) and v.get("inbound_direction_id") is not None
                            ),
                            None,
                        ),
                        "live_tracking": bool(props.get("live_tracking", True)),
                    }
                )

                timeline_stops = props.get("timeline_stops", {})
                if isinstance(timeline_stops, dict):
                    for direction_id, stops in timeline_stops.items():
                        if not isinstance(stops, list):
                            continue
                        for stop in stops:
                            if not isinstance(stop, dict):
                                continue
                            stops_rows.append(
                                {
                                    "route_id": route_id,
                                    "direction_id": int(direction_id),
                                    "stop_id": str(stop.get("stop_id") or ""),
                                    "stop_name": str(stop.get("stop_name") or ""),
                                    "stop_lat": stop.get("stop_lat"),
                                    "stop_lon": stop.get("stop_lon"),
                                    "stop_sequence": int(stop.get("stop_sequence") or 0),
                                    "is_hub": bool(stop.get("is_hub", False)),
                                    "stop_pair": (props.get("stop_pair_index") or {}).get(str(stop.get("stop_id") or "")),
                                }
                            )

            routes_payload = {
                "generated_at": generated_at,
                "mode": self.mode_slug,
                "route_count": len(route_rows),
                "routes": route_rows,
            }
            geometry_payload = {
                "generated_at": generated_at,
                "mode": self.mode_slug,
                "type": "FeatureCollection",
                "features": features,
            }
            stops_payload = {
                "generated_at": generated_at,
                "mode": self.mode_slug,
                "stop_count": len(stops_rows),
                "stops": stops_rows,
            }

            routes_file = DB_ROUTES_FILENAME_TEMPLATE.format(mode=self.mode_slug)
            geometry_file = DB_ROUTE_GEOMETRY_FILENAME_TEMPLATE.format(mode=self.mode_slug)
            stops_file = DB_STOPS_FILENAME_TEMPLATE.format(mode=self.mode_slug)

            await async_write_db_file(self.hass, routes_file, routes_payload)
            await async_write_db_file(self.hass, geometry_file, geometry_payload)
            await async_write_db_file(self.hass, stops_file, stops_payload)

            await async_update_meta(
                self.hass,
                {
                    f"{self.mode_slug}_routes_ts": generated_at,
                    f"{self.mode_slug}_route_geometry_ts": generated_at,
                    f"{self.mode_slug}_stops_ts": generated_at,
                    f"{self.mode_slug}_route_count": len(route_rows),
                    "configured_routes": {
                        self.mode_slug: sorted(self.route_ids),
                    },
                },
            )

            return {
                "generated_at": generated_at,
                "route_count": len(route_rows),
                "feature_count": len(features),
                "stop_count": len(stops_rows),
            }
        except MetlinkApiError as exc:
            raise UpdateFailed(f"Error communicating with API: {exc}") from exc


class MetlinkScheduleCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Build and write per-mode stop schedules for the next 24 hours."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: MetlinkApiClient,
        mode_slug: str,
        route_ids: list[str],
    ) -> None:
        self.api_client = api_client
        self.mode_slug = str(mode_slug)
        self.route_ids = [str(rid) for rid in route_ids if str(rid).strip()]

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.mode_slug}_db_schedules",
            update_interval=timedelta(seconds=DB_REFRESH_SCHEDULES_SECONDS),
        )

    def _canonical_stop_id(self, stop_id: Any) -> str:
        """Collapse train platform stop ids (e.g. WELL1/WELL2 -> WELL)."""
        raw = str(stop_id or "").strip()
        if not raw:
            return ""
        if self.mode_slug != "train":
            return raw
        return re.sub(r"[\s_-]*\d+$", "", raw.upper())

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = datetime.now()
            generated_at = _utc_now_iso()
            raw_by_stop = await self.api_client.get_mode_schedule_window_by_stop(self.route_ids, hours_ahead=24)
            by_stop: dict[str, list[dict[str, Any]]] = {}
            total_rows = 0

            for stop_id, rows in raw_by_stop.items():
                if not isinstance(rows, list):
                    continue
                canonical_stop_id = self._canonical_stop_id(stop_id)
                if not canonical_stop_id:
                    continue
                normalized_rows: list[dict[str, Any]] = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    dep_time = row.get("departure_time") or row.get("scheduled_departure_time")
                    dep_dt = _service_datetime(row.get("service_date"), dep_time)
                    if dep_dt is None:
                        continue
                    row_stop_id = self._canonical_stop_id(row.get("stop_id") or canonical_stop_id)
                    if not row_stop_id:
                        continue
                    normalized_rows.append(
                        {
                            "route_id": str(row.get("route_id") or ""),
                            "route_short_name": row.get("route_short_name"),
                            "service_label": row.get("service_label"),
                            "direction_id": row.get("direction_id"),
                            "stop_id": row_stop_id,
                            "stop_name": row.get("stop_name"),
                            "destination": row.get("destination"),
                            "service_date": row.get("service_date"),
                            "departure_time": dep_time,
                            "scheduled_departure_time": row.get("scheduled_departure_time"),
                            "departure_iso": row.get("departure_iso") or dep_dt.isoformat(),
                            "is_realtime": bool(row.get("is_realtime", False)),
                            "time_source": row.get("time_source"),
                            "trip_id": row.get("trip_id"),
                            "stop_sequence": row.get("stop_sequence"),
                        }
                    )
                if normalized_rows:
                    bucket = by_stop.setdefault(canonical_stop_id, [])
                    bucket.extend(normalized_rows)
                    total_rows += len(normalized_rows)

            for stop_id, rows in by_stop.items():
                rows.sort(key=lambda r: str(r.get("departure_iso") or ""))

            schedules_payload = {
                "generated_at": generated_at,
                "valid_until": (now + timedelta(seconds=DB_REFRESH_SCHEDULES_SECONDS)).isoformat(),
                "mode": self.mode_slug,
                "route_count": len(self.route_ids),
                "row_count": total_rows,
                "by_stop": by_stop,
            }

            schedules_file = DB_SCHEDULES_FILENAME_TEMPLATE.format(mode=self.mode_slug)
            await async_write_db_file(self.hass, schedules_file, schedules_payload)
            await async_update_meta(
                self.hass,
                {
                    f"{self.mode_slug}_schedules_ts": generated_at,
                    f"{self.mode_slug}_schedules_row_count": total_rows,
                },
            )

            return {
                "generated_at": generated_at,
                "row_count": total_rows,
                "stop_count": len(by_stop),
            }
        except MetlinkApiError as exc:
            raise UpdateFailed(f"Error communicating with API: {exc}") from exc


class MetlinkAlertCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll service alerts and trigger schedule refresh when alert content changes."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: MetlinkApiClient,
    ) -> None:
        self.api_client = api_client
        self._schedule_coordinators: list[MetlinkScheduleCoordinator] = []
        self._last_alert_hash: str = ""

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_db_alerts",
            update_interval=timedelta(seconds=DB_REFRESH_ALERTS_SECONDS),
        )

    def register_schedule_coordinator(self, coordinator: MetlinkScheduleCoordinator) -> None:
        """Register a schedule coordinator to refresh on alert change."""
        if coordinator not in self._schedule_coordinators:
            self._schedule_coordinators.append(coordinator)

    def _hash_payload(self, payload: dict[str, Any]) -> str:
        """Compute stable content hash for alert change detection."""
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            generated_at = _utc_now_iso()
            by_mode = await self.api_client.get_alert_messages_by_mode()
            if not isinstance(by_mode, dict):
                by_mode = {}

            payload = {
                "generated_at": generated_at,
                "alerts_by_mode": {
                    "train": str(by_mode.get("train") or "").strip(),
                    "bus": str(by_mode.get("bus") or "").strip(),
                    "ferry": str(by_mode.get("ferry") or "").strip(),
                },
            }

            await async_write_db_file(self.hass, DB_ALERTS_FILENAME, payload)
            await async_update_meta(
                self.hass,
                {
                    "alerts_ts": generated_at,
                },
            )

            new_hash = self._hash_payload(payload)
            if self._last_alert_hash and new_hash != self._last_alert_hash:
                for coordinator in self._schedule_coordinators:
                    self.hass.async_create_task(coordinator.async_request_refresh())
            self._last_alert_hash = new_hash

            return payload
        except MetlinkApiError as exc:
            raise UpdateFailed(f"Error communicating with API: {exc}") from exc


__all__ = [
    "MetlinkAlertCoordinator",
    "MetlinkScheduleCoordinator",
    "MetlinkStaticDataCoordinator",
]
