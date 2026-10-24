"""Download the Metlink static GTFS zip and load it into SQLite."""
from __future__ import annotations

import array
import asyncio
import csv
import io
import logging
import sqlite3
import zipfile
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import aiohttp

from ..const import (
    ROUTE_TYPE_MODES,
    SCHOOL_ROUTE_TYPES,
    STATIC_DB_SCHEMA_VERSION,
    STATIC_GTFS_URL,
)
from .analysis import (
    RouteDirection,
    StopPoint,
    choose_attractors,
    group_pairs,
    label_pattern_directions,
    pair_route_stops,
)
from .store import Store

_LOGGER = logging.getLogger(__name__)

CHUNK_BYTES = 64 * 1024
DOWNLOAD_TIMEOUT = aiohttp.ClientTimeout(total=600, sock_connect=30)
SHAPE_SCALE = 1_000_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS routes (
    route_id TEXT PRIMARY KEY, agency_id TEXT, short_name TEXT, long_name TEXT,
    description TEXT, route_type INTEGER, mode TEXT, is_school INTEGER,
    color TEXT, text_color TEXT, sort_order INTEGER,
    direction_method TEXT, direction_confidence REAL
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_routes_mode ON routes (mode);

CREATE TABLE IF NOT EXISTS stops (
    stop_id TEXT PRIMARY KEY, code TEXT, name TEXT, lat REAL, lon REAL,
    zone TEXT, location_type INTEGER, parent_station TEXT, group_id TEXT
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_stops_group ON stops (group_id);

CREATE TABLE IF NOT EXISTS trips (
    trip_id TEXT PRIMARY KEY, route_id TEXT, service_id TEXT, headsign TEXT,
    direction_id INTEGER, shape_id TEXT
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_trips_route ON trips (route_id, direction_id);
CREATE INDEX IF NOT EXISTS idx_trips_service ON trips (service_id);

CREATE TABLE IF NOT EXISTS stop_times (
    trip_id TEXT, stop_sequence INTEGER, stop_id TEXT, arrival INTEGER,
    departure INTEGER, headsign TEXT, pickup INTEGER, drop_off INTEGER,
    timepoint INTEGER,
    PRIMARY KEY (trip_id, stop_sequence)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_stop_times_stop ON stop_times (stop_id, departure);

CREATE TABLE IF NOT EXISTS shapes (
    shape_id TEXT PRIMARY KEY, npoints INTEGER, data BLOB
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS route_shapes (
    route_id TEXT, direction_id INTEGER, shape_id TEXT, trip_count INTEGER,
    PRIMARY KEY (route_id, direction_id, shape_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS route_stops (
    route_id TEXT, direction_id INTEGER, stop_id TEXT, seq INTEGER, main INTEGER,
    is_inbound INTEGER,
    PRIMARY KEY (route_id, direction_id, stop_id)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_route_stops_stop ON route_stops (stop_id);

CREATE TABLE IF NOT EXISTS calendar (
    service_id TEXT PRIMARY KEY, monday INTEGER, tuesday INTEGER, wednesday INTEGER,
    thursday INTEGER, friday INTEGER, saturday INTEGER, sunday INTEGER,
    start_date INTEGER, end_date INTEGER
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS calendar_dates (
    service_id TEXT, date INTEGER, exception_type INTEGER,
    PRIMARY KEY (service_id, date)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS stop_pairs (
    route_id TEXT, stop_id TEXT, paired_stop_id TEXT, score REAL,
    distance_m REAL, reasons TEXT,
    PRIMARY KEY (route_id, stop_id)
) WITHOUT ROWID;
"""


@dataclass(slots=True)
class DownloadResult:
    status: int
    etag: str | None = None
    last_modified: str | None = None


@dataclass(slots=True)
class SyncResult:
    status: str  # "unchanged" | "updated" | "failed"
    feed_version: str | None = None
    error: str | None = None


def decode_shape(blob: bytes) -> list[tuple[float, float]]:
    """Decode a stored shape blob into (lat, lon) pairs."""
    values = array.array("i")
    values.frombytes(zlib.decompress(blob))
    return [(values[i] / SHAPE_SCALE, values[i + 1] / SHAPE_SCALE) for i in range(0, len(values), 2)]


def _secs(value: str | None) -> int | None:
    """GTFS time to seconds since midnight (may exceed 24h)."""
    if not value:
        return None
    try:
        h, m, s = value.strip().split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except ValueError:
        return None


def _int(value: str | None, default: int | None = None) -> int | None:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


def _float(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def _rows(zf: zipfile.ZipFile, name: str) -> Iterator[dict[str, str]]:
    with zf.open(name) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))


def _has(zf: zipfile.ZipFile, name: str) -> bool:
    return name in zf.namelist()


def read_feed_version(zip_path: str | Path) -> str | None:
    with zipfile.ZipFile(zip_path) as zf:
        if not _has(zf, "feed_info.txt"):
            return None
        for row in _rows(zf, "feed_info.txt"):
            return row.get("feed_version") or None
    return None


def build_database(conn: sqlite3.Connection, zip_path: str | Path) -> dict[str, int]:
    """Load the GTFS zip into `conn`. Runs on the store's worker thread."""
    counts: dict[str, int] = {}
    with zipfile.ZipFile(zip_path) as zf:
        # routes
        route_rows = []
        for r in _rows(zf, "routes.txt"):
            rtype = _int(r.get("route_type"), -1)
            route_rows.append(
                (
                    r["route_id"], r.get("agency_id"), r.get("route_short_name"),
                    r.get("route_long_name"), r.get("route_desc"), rtype,
                    ROUTE_TYPE_MODES.get(rtype, "other"), int(rtype in SCHOOL_ROUTE_TYPES),
                    r.get("route_color"), r.get("route_text_color"), _int(r.get("route_sort_order")),
                    None, None,
                )
            )
        conn.executemany("INSERT INTO routes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", route_rows)
        counts["routes"] = len(route_rows)

        # stops
        stop_points: dict[str, StopPoint] = {}
        stop_rows = []
        for s in _rows(zf, "stops.txt"):
            lat, lon = _float(s.get("stop_lat")), _float(s.get("stop_lon"))
            stop_rows.append(
                (
                    s["stop_id"], s.get("stop_code"), s.get("stop_name"), lat, lon,
                    s.get("zone_id"), _int(s.get("location_type"), 0),
                    s.get("parent_station") or None, None,
                )
            )
            if lat is not None and lon is not None:
                stop_points[s["stop_id"]] = StopPoint(
                    s["stop_id"], s.get("stop_name") or "", lat, lon, s.get("parent_station") or ""
                )
        conn.executemany("INSERT INTO stops VALUES (?,?,?,?,?,?,?,?,?)", stop_rows)
        counts["stops"] = len(stop_rows)

        # trips
        trip_meta: dict[str, tuple[str, int]] = {}
        trip_rows = []
        for t in _rows(zf, "trips.txt"):
            direction = _int(t.get("direction_id"), 0)
            trip_meta[t["trip_id"]] = (t["route_id"], direction)
            trip_rows.append(
                (
                    t["trip_id"], t["route_id"], t["service_id"], t.get("trip_headsign"),
                    direction, t.get("shape_id") or None,
                )
            )
        conn.executemany("INSERT INTO trips VALUES (?,?,?,?,?,?)", trip_rows)
        counts["trips"] = len(trip_rows)

        # stop_times (streamed)
        def stop_time_rows() -> Iterator[tuple]:
            for st in _rows(zf, "stop_times.txt"):
                yield (
                    st["trip_id"], _int(st.get("stop_sequence"), 0), st["stop_id"],
                    _secs(st.get("arrival_time")), _secs(st.get("departure_time")),
                    st.get("stop_headsign") or None, _int(st.get("pickup_type"), 0),
                    _int(st.get("drop_off_type"), 0), _int(st.get("timepoint"), 1),
                )

        cur = conn.executemany("INSERT INTO stop_times VALUES (?,?,?,?,?,?,?,?,?)", stop_time_rows())
        counts["stop_times"] = cur.rowcount

        # shapes: compact int32 arrays, compressed
        if _has(zf, "shapes.txt"):
            points: dict[str, array.array] = defaultdict(lambda: array.array("i"))
            for p in _rows(zf, "shapes.txt"):
                lat, lon = _float(p.get("shape_pt_lat")), _float(p.get("shape_pt_lon"))
                seq = _int(p.get("shape_pt_sequence"), 0)
                if lat is None or lon is None:
                    continue
                points[p["shape_id"]].extend(
                    (seq, round(lat * SHAPE_SCALE), round(lon * SHAPE_SCALE))
                )
            shape_rows = []
            for shape_id, triples in points.items():
                ordered = [(triples[i], triples[i + 1], triples[i + 2]) for i in range(0, len(triples), 3)]
                if any(ordered[i][0] > ordered[i + 1][0] for i in range(len(ordered) - 1)):
                    ordered.sort(key=lambda x: x[0])
                flat = array.array("i")
                for _, la, lo in ordered:
                    flat.extend((la, lo))
                shape_rows.append((shape_id, len(ordered), zlib.compress(flat.tobytes(), 6)))
            conn.executemany("INSERT INTO shapes VALUES (?,?,?)", shape_rows)
            counts["shapes"] = len(shape_rows)
            del points, shape_rows

        # calendar
        if _has(zf, "calendar.txt"):
            conn.executemany(
                "INSERT INTO calendar VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    (
                        c["service_id"], _int(c.get("monday"), 0), _int(c.get("tuesday"), 0),
                        _int(c.get("wednesday"), 0), _int(c.get("thursday"), 0),
                        _int(c.get("friday"), 0), _int(c.get("saturday"), 0),
                        _int(c.get("sunday"), 0), _int(c.get("start_date")), _int(c.get("end_date")),
                    )
                    for c in _rows(zf, "calendar.txt")
                ),
            )
        if _has(zf, "calendar_dates.txt"):
            conn.executemany(
                "INSERT OR REPLACE INTO calendar_dates VALUES (?,?,?)",
                (
                    (c["service_id"], _int(c.get("date")), _int(c.get("exception_type")))
                    for c in _rows(zf, "calendar_dates.txt")
                ),
            )

        conn.execute(
            "INSERT INTO route_shapes SELECT route_id, direction_id, shape_id, COUNT(*) "
            "FROM trips WHERE shape_id IS NOT NULL GROUP BY route_id, direction_id, shape_id"
        )

        patterns = _route_patterns(conn, zf, trip_meta)
        counts.update(_analyse(conn, patterns, stop_points))

    return counts


def _route_patterns(
    conn: sqlite3.Connection,
    zf: zipfile.ZipFile,
    trip_meta: dict[str, tuple[str, int]],
) -> dict[tuple[str, int], list[list[str]]]:
    """Stop lists per (route, direction), most-used pattern first."""
    result: dict[tuple[str, int], list[list[str]]] = defaultdict(list)

    if _has(zf, "stop_patterns.txt") and _has(zf, "stop_pattern_trips.txt"):
        pattern_stops: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for row in _rows(zf, "stop_patterns.txt"):
            pattern_stops[row["stop_pattern_id"]].append(
                (_int(row.get("stop_sequence"), 0), row["stop_id"])
            )
        usage: Counter[tuple[str, int, str]] = Counter()
        for row in _rows(zf, "stop_pattern_trips.txt"):
            meta = trip_meta.get(row["trip_id"])
            if meta and row["stop_pattern_id"] in pattern_stops:
                usage[(meta[0], meta[1], row["stop_pattern_id"])] += 1
        for (route_id, direction, pid), _ in usage.most_common():
            stops = [sid for _, sid in sorted(pattern_stops[pid])]
            result[(route_id, direction)].append(stops)
        if result:
            return result

    # Fallback: the trip with the most stops in each route direction.
    _LOGGER.info("No stop pattern files in feed; using the longest trip per route direction")
    longest: dict[tuple[str, int], tuple[int, str]] = {}
    for trip_id, count in conn.execute("SELECT trip_id, COUNT(*) FROM stop_times GROUP BY trip_id"):
        meta = trip_meta.get(trip_id)
        if meta and (meta not in longest or count > longest[meta][0]):
            longest[meta] = (count, trip_id)
    for key, (_, trip_id) in longest.items():
        rows = conn.execute(
            "SELECT stop_id FROM stop_times WHERE trip_id = ? ORDER BY stop_sequence", (trip_id,)
        ).fetchall()
        result[key].append([r[0] for r in rows])
    return result


def _analyse(
    conn: sqlite3.Connection,
    patterns: dict[tuple[str, int], list[list[str]]],
    stop_points: dict[str, StopPoint],
) -> dict[str, int]:
    """Fill route_stops (with per-stop direction), stop_pairs and stop groups."""
    by_route: dict[str, list[RouteDirection]] = defaultdict(list)
    route_sets: dict[str, set[str]] = defaultdict(set)
    for (route_id, direction), lists in patterns.items():
        by_route[route_id].append(RouteDirection(direction, lists[0]))
        for lst in lists:
            route_sets[route_id].update(lst)
    stop_route_counts: Counter[str] = Counter()
    for stop_ids in route_sets.values():
        stop_route_counts.update(stop_ids)

    attractors = {
        route_id: choose_attractors(directions, stop_points, stop_route_counts)
        for route_id, directions in by_route.items()
    }

    route_stop_rows: list[tuple] = []
    for (route_id, direction), lists in patterns.items():
        found = attractors[route_id].attractors
        seen: set[str] = set()
        extra = len(lists[0])
        for number, lst in enumerate(lists):
            labels = label_pattern_directions(lst, stop_points, found)
            for index, sid in enumerate(lst):
                if sid in seen:
                    continue
                seen.add(sid)
                if number == 0:
                    route_stop_rows.append((route_id, direction, sid, index, 1, labels[index]))
                else:
                    route_stop_rows.append((route_id, direction, sid, extra, 0, labels[index]))
                    extra += 1
    conn.executemany("INSERT INTO route_stops VALUES (?,?,?,?,?,?)", route_stop_rows)

    all_pairs = []
    for route_id, directions in by_route.items():
        result = attractors[route_id]
        conn.execute(
            "UPDATE routes SET direction_method=?, direction_confidence=? WHERE route_id=?",
            (result.method, result.confidence, route_id),
        )
        all_pairs.extend(pair_route_stops(route_id, directions, stop_points))

    conn.executemany(
        "INSERT OR REPLACE INTO stop_pairs VALUES (?,?,?,?,?,?)",
        ((p.route_id, p.stop_id, p.paired_stop_id, p.score, p.distance_m, p.reasons) for p in all_pairs),
    )
    groups = group_pairs(all_pairs)
    conn.executemany("UPDATE stops SET group_id=? WHERE stop_id=?", ((g, s) for s, g in groups.items()))
    return {"route_stops": len(route_stop_rows), "stop_pairs": len(all_pairs) // 2, "stop_groups": len(groups) // 2}


async def download_feed(
    session: aiohttp.ClientSession,
    url: str,
    dest: str | Path,
    *,
    etag: str | None = None,
    last_modified: str | None = None,
) -> DownloadResult:
    """Stream the feed to `dest`. Returns status 304 without writing when unchanged."""
    headers: dict[str, str] = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    loop = asyncio.get_running_loop()
    async with session.get(url, headers=headers, timeout=DOWNLOAD_TIMEOUT) as resp:
        if resp.status == 304:
            return DownloadResult(304, etag, last_modified)
        if resp.status != 200:
            raise aiohttp.ClientResponseError(
                resp.request_info, resp.history, status=resp.status, message="GTFS download failed"
            )
        with open(dest, "wb") as fh:
            async for chunk in resp.content.iter_chunked(CHUNK_BYTES):
                await loop.run_in_executor(None, fh.write, chunk)
        return DownloadResult(200, resp.headers.get("ETag"), resp.headers.get("Last-Modified"))


class StaticSync:
    """Keeps the static database current. Safe to call from a daily timer."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        store: Store,
        db_path: str | Path,
        *,
        url: str = STATIC_GTFS_URL,
    ) -> None:
        self._session = session
        self._store = store
        self._db_path = Path(db_path)
        self._url = url
        self._lock = asyncio.Lock()

    @property
    def store(self) -> Store:
        return self._store

    async def async_open(self) -> None:
        await self._store.open(SCHEMA, STATIC_DB_SCHEMA_VERSION)

    async def async_sync(self, *, force: bool = False) -> SyncResult:
        async with self._lock:
            try:
                return await self._sync(force)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Static GTFS sync failed: %s", err)
                return SyncResult("failed", error=str(err))

    async def _sync(self, force: bool) -> SyncResult:
        zip_path = self._db_path.with_name(self._db_path.name + ".zip.tmp")
        new_db = self._db_path.with_name(self._db_path.name + ".new")
        stored_version = await self._store.get_meta("feed_version")
        etag = None if force else await self._store.get_meta("etag")
        modified = None if force else await self._store.get_meta("last_modified")
        has_data = await self._store.get_meta("synced_at") is not None
        if not has_data:
            etag = modified = None

        try:
            result = await download_feed(self._session, self._url, zip_path, etag=etag, last_modified=modified)
            await self._store.set_meta("last_checked", _now())
            if result.status == 304:
                _LOGGER.debug("Static GTFS unchanged (304)")
                return SyncResult("unchanged", stored_version)

            loop = asyncio.get_running_loop()
            version = await loop.run_in_executor(None, read_feed_version, zip_path)
            if not force and has_data and version and version == stored_version:
                await self._save_validators(result)
                _LOGGER.debug("Static GTFS feed version %s already loaded", version)
                return SyncResult("unchanged", version)

            _LOGGER.info("Building static GTFS database (feed version %s)", version)
            for leftover in (new_db, Path(str(new_db) + "-wal"), Path(str(new_db) + "-shm")):
                leftover.unlink(missing_ok=True)
            builder = Store(new_db)
            await builder.open(SCHEMA, STATIC_DB_SCHEMA_VERSION)
            try:
                counts = await builder.transaction(lambda conn: build_database(conn, zip_path))
                await builder.set_meta("feed_version", version or "")
            finally:
                await builder.close()

            await self._store.replace_with(new_db, SCHEMA, STATIC_DB_SCHEMA_VERSION)
            await self._save_validators(result)
            await self._store.set_meta("synced_at", _now())
            await self._store.set_meta("last_checked", _now())
            _LOGGER.info("Static GTFS loaded: %s", counts)
            return SyncResult("updated", version)
        finally:
            for tmp in (zip_path, new_db, Path(str(new_db) + "-wal"), Path(str(new_db) + "-shm")):
                tmp.unlink(missing_ok=True)

    async def _save_validators(self, result: DownloadResult) -> None:
        if result.etag:
            await self._store.set_meta("etag", result.etag)
        if result.last_modified:
            await self._store.set_meta("last_modified", result.last_modified)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
