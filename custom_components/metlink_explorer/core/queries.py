"""Catalogue queries for the cards: routes, map markers, route detail and shapes."""
from __future__ import annotations

from typing import Any

from .static_sync import decode_shape
from .store import Store


def _marks(values: list[str]) -> str:
    return ",".join("?" * len(values))


async def list_routes(store: Store, mode: str | None = None) -> list[dict[str, Any]]:
    sql = (
        "SELECT route_id, short_name, long_name, mode, route_type, is_school, color, text_color "
        "FROM routes"
    )
    params: list[Any] = []
    if mode:
        sql += " WHERE mode = ?"
        params.append(mode)
    sql += " ORDER BY mode, COALESCE(sort_order, 0), short_name"
    return [
        {
            "route_id": rid, "short_name": short, "long_name": long, "mode": m,
            "route_type": rtype, "is_school": bool(school), "color": color, "text_color": text,
        }
        for rid, short, long, m, rtype, school, color, text in await store.query(sql, params)
    ]


async def list_stops(
    store: Store,
    *,
    route_ids: list[str] | None = None,
    mode: str | None = None,
    include_school: bool = True,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[dict[str, Any]]:
    """Map markers. Opposite-side stops are merged into one marker.

    `bbox` is (south, west, north, east). A marker's id can be passed straight
    to the departure queries, which cover every stop it merges.
    """
    where, params = ["1=1"], []
    if bbox:
        where.append("s.lat BETWEEN ? AND ? AND s.lon BETWEEN ? AND ?")
        params += [bbox[0], bbox[2], bbox[1], bbox[3]]
    served = (
        "SELECT DISTINCT rs.stop_id, r.mode FROM route_stops rs JOIN routes r ON r.route_id = rs.route_id"
    )
    conds, sparams = [], []
    if route_ids:
        conds.append(f"rs.route_id IN ({_marks(route_ids)})")
        sparams += route_ids
    if mode:
        conds.append("r.mode = ?")
        sparams.append(mode)
    if not include_school:
        conds.append("r.is_school = 0")
    if conds:
        served += " WHERE " + " AND ".join(conds)
    rows = await store.query(
        f"""SELECT s.stop_id, s.name, s.lat, s.lon, COALESCE(s.group_id, s.stop_id), x.mode
            FROM stops s JOIN ({served}) x ON x.stop_id = s.stop_id
            WHERE {' AND '.join(where)} ORDER BY s.stop_id""",
        [*sparams, *params],
    )
    markers: dict[str, dict[str, Any]] = {}
    for stop_id, name, lat, lon, marker_id, stop_mode in rows:
        marker = markers.setdefault(
            marker_id, {"id": marker_id, "name": name, "stop_ids": [], "modes": set(), "_lat": [], "_lon": []}
        )
        if stop_id not in marker["stop_ids"]:
            marker["stop_ids"].append(stop_id)
            marker["_lat"].append(lat)
            marker["_lon"].append(lon)
        marker["modes"].add(stop_mode)
        if stop_id == marker_id:
            marker["name"] = name
    out = []
    for marker in markers.values():
        lats, lons = marker.pop("_lat"), marker.pop("_lon")
        marker["lat"], marker["lon"] = sum(lats) / len(lats), sum(lons) / len(lons)
        marker["modes"] = sorted(marker["modes"])
        out.append(marker)
    return out


async def route_detail(store: Store, route_id: str) -> dict[str, Any] | None:
    """One route: its directions, ordered stops and main shape ids."""
    row = await store.query_one(
        "SELECT route_id, short_name, long_name, mode, is_school, color, text_color FROM routes WHERE route_id = ?",
        (route_id,),
    )
    if row is None:
        return None
    directions: dict[int, dict[str, Any]] = {}
    for direction_id, shape_id, count in await store.query(
        "SELECT direction_id, shape_id, trip_count FROM route_shapes WHERE route_id = ? ORDER BY trip_count DESC",
        (route_id,),
    ):
        entry = directions.setdefault(direction_id, {"direction_id": direction_id, "shape_ids": [], "stops": []})
        entry["shape_ids"].append(shape_id)
    for direction_id, headsign in await store.query(
        """SELECT direction_id, headsign FROM trips WHERE route_id = ?
           GROUP BY direction_id, headsign ORDER BY COUNT(*) DESC""",
        (route_id,),
    ):
        entry = directions.setdefault(direction_id, {"direction_id": direction_id, "shape_ids": [], "stops": []})
        entry.setdefault("headsign", headsign)
    for direction_id, stop_id, name, lat, lon, main, towards in await store.query(
        """SELECT rs.direction_id, rs.stop_id, s.name, s.lat, s.lon, rs.main, rs.is_inbound
           FROM route_stops rs JOIN stops s ON s.stop_id = rs.stop_id
           WHERE rs.route_id = ? ORDER BY rs.direction_id, rs.seq""",
        (route_id,),
    ):
        entry = directions.setdefault(direction_id, {"direction_id": direction_id, "shape_ids": [], "stops": []})
        entry["stops"].append(
            {"stop_id": stop_id, "name": name, "lat": lat, "lon": lon, "main": bool(main),
             "towards_centre": None if towards is None else bool(towards)}
        )
    rid, short, long, mode, school, color, text = row
    return {
        "route_id": rid, "short_name": short, "long_name": long, "mode": mode,
        "is_school": bool(school), "color": color, "text_color": text,
        "directions": [directions[k] for k in sorted(directions)],
    }


async def get_shape(store: Store, shape_id: str) -> list[list[float]] | None:
    row = await store.query_one("SELECT data FROM shapes WHERE shape_id = ?", (shape_id,))
    if row is None:
        return None
    return [[round(lat, 6), round(lon, 6)] for lat, lon in decode_shape(row[0])]


async def stop_routes(store: Store, stop_id: str) -> list[dict[str, Any]]:
    """Routes serving a marker, so the card can offer a route filter."""
    from .departures import group_members

    members = await group_members(store, stop_id)
    if not members:
        return []
    rows = await store.query(
        f"""SELECT DISTINCT r.route_id, r.short_name, r.long_name, r.mode, r.is_school, r.color, r.text_color
            FROM route_stops rs JOIN routes r ON r.route_id = rs.route_id
            WHERE rs.stop_id IN ({_marks(members)}) ORDER BY r.mode, r.short_name""",
        members,
    )
    return [
        {"route_id": a, "short_name": b, "long_name": c, "mode": d, "is_school": bool(e), "color": f, "text_color": g}
        for a, b, c, d, e, f, g in rows
    ]
