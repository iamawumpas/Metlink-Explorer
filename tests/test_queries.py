import asyncio

from custom_components.metlink_explorer.core.queries import (
    get_shape,
    list_routes,
    list_stops,
    route_detail,
    stop_routes,
)
from custom_components.metlink_explorer.core.static_sync import SCHEMA, build_database
from custom_components.metlink_explorer.core.store import Store
from tests.gtfs_fixture import build_zip


def with_db(tmp_path, body):
    zip_path = tmp_path / "f.zip"
    zip_path.write_bytes(build_zip())

    async def main():
        store = Store(tmp_path / "q.db")
        await store.open(SCHEMA, 1)
        await store.transaction(lambda conn: build_database(conn, zip_path))
        try:
            return await body(store)
        finally:
            await store.close()

    return asyncio.run(main())


def test_routes_filter_by_mode(tmp_path):
    async def body(store):
        assert [r["route_id"] for r in await list_routes(store)] == ["R1", "R2", "R3"]
        assert [r["route_id"] for r in await list_routes(store, "ferry")] == ["R3"]
        school = {r["route_id"]: r["is_school"] for r in await list_routes(store, "bus")}
        assert school == {"R1": False, "R2": True}

    with_db(tmp_path, body)


def test_stop_markers_merge_opposite_stops(tmp_path):
    async def body(store):
        markers = {m["id"]: m for m in await list_stops(store)}
        assert set(markers["A1"]["stop_ids"]) == {"A1", "B1"}
        assert markers["A1"]["modes"] == ["bus"]
        assert "B1" not in markers and "A0" in markers
        assert abs(markers["A1"]["lon"] - (174.80 + 0.0001)) < 1e-9

        assert "A1" in {m["id"] for m in await list_stops(store, route_ids=["R1"])}
        assert await list_stops(store, route_ids=["R3"]) == []
        assert await list_stops(store, mode="bus", include_school=False, bbox=(-41.3, 174.7, -41.25, 174.9)) \
            and all(m["lat"] <= -41.25 for m in await list_stops(store, bbox=(-41.3, 174.7, -41.25, 174.9)))

    with_db(tmp_path, body)


def test_route_detail_and_shape(tmp_path):
    async def body(store):
        detail = await route_detail(store, "R1")
        by_dir = {d["direction_id"]: d for d in detail["directions"]}
        assert [s["stop_id"] for s in by_dir[1]["stops"]] == ["A0", "A1", "A2", "A3", "A4"]
        assert all(s["towards_centre"] is True for s in by_dir[1]["stops"])
        assert by_dir[1]["shape_ids"] == ["SH1"] and by_dir[1]["headsign"] == "City"
        assert await route_detail(store, "nope") is None
        assert await get_shape(store, "SH1") == [[-41.22, 174.8], [-41.27, 174.8]]
        assert await get_shape(store, "nope") is None

    with_db(tmp_path, body)


def test_stop_routes(tmp_path):
    async def body(store):
        assert {r["route_id"] for r in await stop_routes(store, "A1")} == {"R1", "R2"}
        assert await stop_routes(store, "nope") == []

    with_db(tmp_path, body)
