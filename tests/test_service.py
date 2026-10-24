import asyncio
from datetime import datetime, timedelta, timezone

from custom_components.metlink_explorer.core.realtime import RealtimeService, parse_trip_updates
from custom_components.metlink_explorer.core.service import MetlinkService
from custom_components.metlink_explorer.core.static_sync import SCHEMA, build_database
from custom_components.metlink_explorer.core.store import Store
from tests.gtfs_fixture import build_zip

NZ = timezone(timedelta(hours=13))


def vehicle(vid, trip, lat=-41.25):
    return {"id": vid, "trip_id": trip, "lat": lat, "lon": 174.8, "bearing": 0, "timestamp": 1}


def with_service(tmp_path, body):
    zip_path = tmp_path / "f.zip"
    zip_path.write_bytes(build_zip())

    async def main():
        store = Store(tmp_path / "s.db")
        await store.open(SCHEMA, 1)
        await store.transaction(lambda conn: build_database(conn, zip_path))
        rt = RealtimeService(None)
        svc = MetlinkService(store, None, rt, lambda: datetime(2026, 1, 6, 7, 0, tzinfo=NZ))
        await svc.async_reload_index()
        try:
            return await body(svc, rt)
        finally:
            await store.close()

    return asyncio.run(main())


def test_vehicles_resolved_by_trip_and_filtered(tmp_path):
    async def body(svc, rt):
        rt.snapshot.vehicles = {
            "1": vehicle("1", "T_in_1"), "2": vehicle("2", "T_sch", -41.30),
            "3": vehicle("3", "unknown-trip"), "4": vehicle("4", None),
        }
        everything = {v["id"]: v for v in svc.vehicles()}
        assert set(everything) == {"1", "2", "3", "4"}
        assert everything["1"]["route"] == "1" and everything["1"]["mode"] == "bus"
        assert everything["2"]["is_school"] and everything["3"]["route_id"] is None
        assert {v["id"] for v in svc.vehicles(route_ids=["R1"])} == {"1"}
        assert {v["id"] for v in svc.vehicles(modes=["ferry"])} == set()
        assert {v["id"] for v in svc.vehicles(bbox=(-41.4, 174.7, -41.28, 174.9))} == {"2"}

    with_service(tmp_path, body)


def test_ferries_from_ais_are_merged_and_filtered(tmp_path):
    from custom_components.metlink_explorer.core.ais import AisService

    async def body(svc, rt):
        svc.ais = AisService(None, "key")
        svc.ais.handle_payload({
            "MessageType": "PositionReport", "MetaData": {"MMSI": 512003252, "ShipName": "KOTUKU"},
            "Message": {"PositionReport": {"Latitude": -41.28, "Longitude": 174.85, "TrueHeading": 10}}})
        rt.snapshot.vehicles = {"1": vehicle("1", "T_in_1")}
        both = {v["id"]: v for v in svc.vehicles()}
        assert set(both) == {"1", "ais:512003252"}
        ship = both["ais:512003252"]
        assert ship["mode"] == "ferry" and ship["route_id"] == "R3" and ship["name"] == "KOTUKU"
        assert {v["id"] for v in svc.vehicles(modes=["bus"])} == {"1"}
        assert {v["id"] for v in svc.vehicles(modes=["ferry"])} == {"ais:512003252"}
        assert {v["id"] for v in svc.vehicles(route_ids=["R1"])} == {"1"}
        assert (await svc.status())["ais"]["tracked"] == 1

    with_service(tmp_path, body)


def test_departures_include_live_delay(tmp_path):
    async def body(svc, rt):
        rt.snapshot.trip_updates = parse_trip_updates({"entity": [{"id": "x", "trip_update": {
            "trip": {"trip_id": "T_in_1"},
            "stop_time_update": {"stop_id": "A1", "stop_sequence": 1, "departure": {"delay": 180}}}}]})
        rows = await svc.departures("A1", towards="A4", horizon_hours=3)
        first = rows[0]
        assert first["trip_id"] == "T_in_1" and first["status"] == "delayed" and first["delay"] == 180
        assert first["timestamp_expected"] == first["timestamp"] + 180
        assert rows[1]["status"] == "scheduled"

    with_service(tmp_path, body)


def test_alerts_filter_and_status(tmp_path):
    async def body(svc, rt):
        rt.snapshot.alerts = [
            {"id": "a", "stop_ids": ["A1"], "route_ids": []},
            {"id": "b", "stop_ids": [], "route_ids": ["R9"]},
        ]
        assert len(svc.alerts()) == 2
        assert [a["id"] for a in svc.alerts(stop_ids=["A1"])] == ["a"]
        assert [a["id"] for a in svc.alerts(route_ids=["R9"])] == ["b"]
        status = await svc.status()
        assert set(status["realtime"]) == {"vehicles", "trip_updates", "alerts"}
        assert status["subscribers_active"] is False

    with_service(tmp_path, body)
