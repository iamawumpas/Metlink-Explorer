import asyncio
from datetime import datetime, timedelta, timezone

from custom_components.metlink_explorer.core.departures import (
    departures,
    destinations,
    group_members,
    reachable,
)
from custom_components.metlink_explorer.core.static_sync import SCHEMA, build_database
from custom_components.metlink_explorer.core.store import Store
from tests.gtfs_fixture import build_zip

NZ = timezone(timedelta(hours=13))


def at(day, hour=7, minute=0):
    return datetime(2026, 1, day, hour, minute, tzinfo=NZ)


def with_db(tmp_path, body):
    zip_path = tmp_path / "f.zip"
    zip_path.write_bytes(build_zip())

    async def main():
        store = Store(tmp_path / "d.db")
        await store.open(SCHEMA, 1)
        await store.transaction(lambda conn: build_database(conn, zip_path))
        try:
            return await body(store)
        finally:
            await store.close()

    return asyncio.run(main())


def ids(rows):
    return [r["trip_id"] for r in rows]


def test_group_includes_both_sides(tmp_path):
    async def body(store):
        assert sorted(await group_members(store, "A1")) == ["A1", "B1"]
        assert sorted(await group_members(store, "B1")) == ["A1", "B1"]
        assert await group_members(store, "A4") == ["A4"]
        assert await group_members(store, "nope") == []

    with_db(tmp_path, body)


def test_towards_picks_only_trips_that_go_there(tmp_path):
    async def body(store):
        up = await departures(store, "A1", at(6), towards="A4", horizon_hours=3)
        assert ids(up) == ["T_in_1", "T_in_2"] and {r["stop_id"] for r in up} == {"A1"}
        down = await departures(store, "A1", at(6), towards="B0", horizon_hours=3)
        assert ids(down) == ["T_out_1"] and down[0]["stop_id"] == "B1"
        everything = await departures(store, "B1", at(6), horizon_hours=3)
        assert ids(everything) == ["T_in_1", "T_out_1", "T_in_2"]

    with_db(tmp_path, body)


def test_stop_after_the_target_gets_nothing(tmp_path):
    async def body(store):
        # T_in trips reach A0 first and A4 last, so nothing leaves A4 or goes back to A0.
        assert await departures(store, "A4", at(6), horizon_hours=3) == []
        assert await departures(store, "A2", at(6), towards="A0", horizon_hours=3) == []

    with_db(tmp_path, body)


def test_calendar_exception_and_weekend(tmp_path):
    async def body(store):
        assert await departures(store, "A1", at(5), horizon_hours=3) == []  # removed holiday
        assert await departures(store, "A1", at(10), horizon_hours=3) == []  # Saturday

    with_db(tmp_path, body)


def test_after_midnight_trip_belongs_to_previous_service_day(tmp_path):
    async def body(store):
        rows = await departures(store, "A1", at(7, 0, 10), horizon_hours=1)
        assert ids(rows) == ["T_sch"]
        assert rows[0]["is_school"] and rows[0]["scheduled"].startswith("2026-01-07T00:31")

    with_db(tmp_path, body)


def test_limit_and_horizon(tmp_path):
    async def body(store):
        assert len(await departures(store, "A1", at(6), limit=2, horizon_hours=72)) == 2
        week = await departures(store, "A1", at(6), horizon_hours=999, limit=500)
        assert week and max(r["timestamp"] for r in week) <= at(6).timestamp() + 168 * 3600
        times = [r["timestamp"] for r in week]
        assert times == sorted(times)

    with_db(tmp_path, body)


def test_route_filter(tmp_path):
    async def body(store):
        assert await departures(store, "A1", at(6), route_ids=["R2"], horizon_hours=3) == []

    with_db(tmp_path, body)


def test_destinations_and_reachable(tmp_path):
    async def body(store):
        dest = {d["stop_id"]: d for d in await destinations(store, "A1")}
        assert set(dest) == {"A4", "B0"}
        assert dest["A4"]["trips"] == 3 and dest["A4"]["routes"] == ["1", "S2"]
        assert {r["stop_id"] for r in await reachable(store, "A1")} == {"A2", "A3", "A4", "B0"}
        assert await destinations(store, "nope") == []

    with_db(tmp_path, body)
