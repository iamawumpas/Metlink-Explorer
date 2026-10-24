"""Scheduled departures filtered by where the trip is going.

Direction is never guessed. A trip "goes towards" a place when that place is
one of the trip's later stops, so the filter is correct for any route shape
(cross-town, loop, regional). All times come from the static timetable;
live delays are merged in by the realtime layer.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from ..const import DEFAULT_DEPARTURE_HORIZON_HOURS, DEFAULT_DEPARTURE_LIMIT, MAX_DEPARTURE_HORIZON_HOURS
from .store import Store

__all__ = ["active_services", "departures", "destinations", "group_members", "reachable"]

_LAST_SEQ = "(SELECT MAX(stop_sequence) FROM stop_times WHERE trip_id = st.trip_id)"
_LAST_STOP = (
    "(SELECT stop_id FROM stop_times WHERE trip_id = st.trip_id "
    "ORDER BY stop_sequence DESC LIMIT 1)"
)


def _marks(values: list[str]) -> str:
    return ",".join("?" * len(values))


async def group_members(store: Store, stop_id: str) -> list[str]:
    """All stops that share a map marker with stop_id (itself included)."""
    row = await store.query_one("SELECT group_id FROM stops WHERE stop_id = ?", (stop_id,))
    if row is None:
        return []
    if not row[0]:
        return [stop_id]
    rows = await store.query("SELECT stop_id FROM stops WHERE group_id = ?", (row[0],))
    return [r[0] for r in rows]


async def active_services(store: Store, day: date) -> set[str]:
    """Service ids running on a calendar day."""
    ymd = int(day.strftime("%Y%m%d"))
    weekday = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")[day.weekday()]
    rows = await store.query(
        f"SELECT service_id FROM calendar WHERE {weekday} = 1 AND start_date <= ? AND end_date >= ?",
        (ymd, ymd),
    )
    services = {r[0] for r in rows}
    for service_id, kind in await store.query(
        "SELECT service_id, exception_type FROM calendar_dates WHERE date = ?", (ymd,)
    ):
        if kind == 1:
            services.add(service_id)
        elif kind == 2:
            services.discard(service_id)
    return services


async def destinations(store: Store, stop_id: str) -> list[dict[str, Any]]:
    """Where trips leaving this stop finish, as options for a "Towards" filter."""
    members = await group_members(store, stop_id)
    if not members:
        return []
    rows = await store.query(
        f"""SELECT COALESCE(ls.group_id, ls.stop_id) AS dest, ls.name,
                   COUNT(DISTINCT st.trip_id), GROUP_CONCAT(DISTINCT r.short_name)
            FROM stop_times st
            JOIN trips t ON t.trip_id = st.trip_id
            JOIN routes r ON r.route_id = t.route_id
            JOIN stops ls ON ls.stop_id = {_LAST_STOP}
            WHERE st.stop_id IN ({_marks(members)})
              AND st.stop_sequence < {_LAST_SEQ}
              AND COALESCE(st.pickup, 0) != 1
            GROUP BY dest, ls.name
            ORDER BY 3 DESC""",
        members,
    )
    return [
        {"stop_id": d, "name": n, "trips": c, "routes": sorted((rt or "").split(","))}
        for d, n, c, rt in rows
    ]


async def reachable(store: Store, stop_id: str) -> list[dict[str, Any]]:
    """Every place a trip from this stop calls at later (for a "Towards any stop" pick)."""
    members = await group_members(store, stop_id)
    if not members:
        return []
    rows = await store.query(
        f"""SELECT COALESCE(s.group_id, s.stop_id) AS place, MIN(s.name),
                   COUNT(DISTINCT st.trip_id)
            FROM stop_times st
            JOIN stop_times x ON x.trip_id = st.trip_id AND x.stop_sequence > st.stop_sequence
            JOIN stops s ON s.stop_id = x.stop_id
            WHERE st.stop_id IN ({_marks(members)}) AND COALESCE(x.drop_off, 0) != 1
            GROUP BY place
            ORDER BY 3 DESC, 2""",
        members,
    )
    return [{"stop_id": p, "name": n, "trips": c} for p, n, c in rows]


async def departures(
    store: Store,
    stop_id: str,
    now: datetime,
    *,
    towards: str | None = None,
    route_ids: list[str] | None = None,
    limit: int = DEFAULT_DEPARTURE_LIMIT,
    horizon_hours: int = DEFAULT_DEPARTURE_HORIZON_HOURS,
) -> list[dict[str, Any]]:
    """Next scheduled departures from a stop (both sides of a pair).

    `now` must be timezone-aware in the feed's local zone. `towards` is a
    stop or group id; only trips that call there after this stop are returned.
    """
    members = await group_members(store, stop_id)
    if not members:
        return []
    horizon = timedelta(hours=min(max(horizon_hours, 1), MAX_DEPARTURE_HORIZON_HOURS))
    target = await group_members(store, towards) if towards else []
    if towards and not target:
        return []

    found: list[dict[str, Any]] = []
    # Start a day back because GTFS times past 24:00 belong to the previous service day.
    first = now.date() - timedelta(days=1)
    for offset in range((now + horizon).date().toordinal() - first.toordinal() + 1):
        day = first + timedelta(days=offset)
        services = await active_services(store, day)
        if not services:
            continue
        midnight = datetime.combine(day, time(), tzinfo=now.tzinfo)
        low = int((now - midnight).total_seconds())
        high = int((now + horizon - midnight).total_seconds())
        if high < 0:
            continue

        sql = (
            f"""SELECT st.trip_id, st.stop_id, st.departure, t.route_id, t.headsign,
                       t.direction_id, r.short_name, r.color, r.text_color, r.mode,
                       r.is_school, ls.name, st.stop_sequence
                FROM stop_times st
                JOIN trips t ON t.trip_id = st.trip_id
                JOIN routes r ON r.route_id = t.route_id
                JOIN stops ls ON ls.stop_id = {_LAST_STOP}
                WHERE st.stop_id IN ({_marks(members)})
                  AND t.service_id IN ({_marks(sorted(services))})
                  AND st.departure BETWEEN ? AND ?
                  AND COALESCE(st.pickup, 0) != 1
                  AND st.stop_sequence < {_LAST_SEQ}"""
        )
        params: list[Any] = [*members, *sorted(services), max(low, 0), high]
        if target:
            sql += (
                f""" AND EXISTS (SELECT 1 FROM stop_times x WHERE x.trip_id = st.trip_id
                      AND x.stop_sequence > st.stop_sequence
                      AND COALESCE(x.drop_off, 0) != 1
                      AND x.stop_id IN ({_marks(target)}))"""
            )
            params += target
        if route_ids:
            sql += f" AND t.route_id IN ({_marks(route_ids)})"
            params += route_ids
        sql += " ORDER BY st.departure LIMIT ?"
        params.append(limit)

        for trip_id, sid, secs, route_id, headsign, direction_id, short, color, text, mode, school, dest, seq in (
            await store.query(sql, params)
        ):
            when = midnight + timedelta(seconds=secs)
            if when < now or when > now + horizon:
                continue
            found.append(
                {
                    "trip_id": trip_id,
                    "stop_id": sid,
                    "stop_sequence": seq,
                    "route_id": route_id,
                    "route": short,
                    "color": color,
                    "text_color": text,
                    "mode": mode,
                    "is_school": bool(school),
                    "headsign": headsign,
                    "destination": dest,
                    "direction_id": direction_id,
                    "scheduled": when.isoformat(),
                    "timestamp": int(when.timestamp()),
                }
            )
    found.sort(key=lambda d: d["timestamp"])
    return found[:limit]
