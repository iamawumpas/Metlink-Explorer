import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from custom_components.metlink_explorer.core import api
from custom_components.metlink_explorer.core.realtime import RealtimeService
from custom_components.metlink_explorer.core.service import MetlinkService
from custom_components.metlink_explorer.core.static_sync import SCHEMA, build_database
from custom_components.metlink_explorer.core.store import Store
from tests.gtfs_fixture import build_zip

NZ = timezone(timedelta(hours=13))


class QuietHttp:
    async def get_json(self, path):
        return {"entity": []}


class FakeTask:
    def cancel(self):
        pass


def with_service(tmp_path, body):
    zip_path = tmp_path / "f.zip"
    zip_path.write_bytes(build_zip())

    async def main():
        store = Store(tmp_path / "a.db")
        await store.open(SCHEMA, 1)
        await store.transaction(lambda conn: build_database(conn, zip_path))
        rt = RealtimeService(QuietHttp(), spawn=lambda coro: (coro.close(), FakeTask())[1])
        svc = MetlinkService(store, None, rt, lambda: datetime(2026, 1, 6, 7, 0, tzinfo=NZ))
        await svc.async_reload_index()
        try:
            return await body(svc, rt)
        finally:
            await store.close()

    return asyncio.run(main())


def error_code(coro):
    async def go():
        with pytest.raises(api.ApiError) as info:
            await coro
        return info.value.code

    return go()


def test_commands_return_data(tmp_path):
    async def body(svc, rt):
        assert len(await api.run_command(svc, "routes", {})) == 3
        assert len(await api.run_command(svc, "routes", {"mode": "ferry"})) == 1
        assert {m["id"] for m in await api.run_command(svc, "stops", {"route_ids": ["R1"]})} >= {"A1"}
        assert (await api.run_command(svc, "route", {"route_id": "R1"}))["short_name"] == "1"
        assert (await api.run_command(svc, "shape", {"shape_id": "SH1"}))["points"][0] == [-41.22, 174.8]
        assert {d["stop_id"] for d in await api.run_command(svc, "destinations", {"stop_id": "A1"})} == {"A4", "B0"}
        rows = await api.run_command(svc, "departures", {"stop_id": "A1", "towards": "A4", "horizon_hours": 3})
        assert [r["trip_id"] for r in rows] == ["T_in_1", "T_in_2"]
        assert await api.run_command(svc, "alerts", {}) == []
        assert "static" in await api.run_command(svc, "status", {})

    with_service(tmp_path, body)


def test_validation_and_errors(tmp_path):
    async def body(svc, rt):
        assert await error_code(api.run_command(svc, "nope", {})) == "unknown_command"
        assert await error_code(api.run_command(svc, "departures", {})) == "invalid_format"
        assert await error_code(api.run_command(svc, "departures", {"stop_id": "zzz"})) == "not_found"
        assert await error_code(api.run_command(svc, "departures", {"stop_id": "A1", "limit": "x"})) == "invalid_format"
        assert await error_code(api.run_command(svc, "stops", {"bbox": [1, 2]})) == "invalid_format"
        assert await error_code(api.run_command(svc, "routes", {"mode": "plane"})) == "invalid_format"
        assert await error_code(api.run_command(svc, "stops", {"route_ids": "R1"})) == "invalid_format"
        assert await error_code(api.run_command(svc, "route", {"route_id": "x"})) == "not_found"
        # limits are clamped, not rejected
        rows = await api.run_command(svc, "departures", {"stop_id": "A1", "limit": 99999, "horizon_hours": 99999})
        assert len(rows) <= api.MAX_LIMIT

    with_service(tmp_path, body)


def test_vehicle_subscription_pushes_and_cleans_up(tmp_path):
    async def body(svc, rt):
        sent = []
        unsub, kick = await api.subscribe_vehicles(svc, {"route_ids": ["R1"]}, sent.append)
        assert rt.running and sent == []
        rt.snapshot.vehicles = {"1": {"id": "1", "trip_id": "T_in_1", "lat": -41.25, "lon": 174.8}}
        kick()
        assert len(sent) == 1 and sent[0][0]["route"] == "1"
        for cb in list(rt._subscribers.values()):
            cb("alerts")  # unrelated feed: no push
            cb("vehicles")
        assert len(sent) == 2
        unsub()
        await asyncio.sleep(0)
        assert not rt.running

    with_service(tmp_path, body)


def test_departure_subscription_refreshes_on_trip_updates(tmp_path):
    async def body(svc, rt):
        sent, tasks = [], []
        spawn = lambda coro: tasks.append(asyncio.ensure_future(coro))  # noqa: E731
        stop, kick = await api.subscribe_departures(svc, {"stop_id": "A1", "towards": "A4", "horizon_hours": 3}, sent.append, spawn)
        kick()
        kick()  # a refresh is already in flight: skipped
        assert len(tasks) == 1
        await asyncio.gather(*tasks)
        assert [r["trip_id"] for r in sent[0]] == ["T_in_1", "T_in_2"]
        for cb in list(rt._subscribers.values()):
            cb("vehicles")  # ignored
            cb("trip_updates")
        await asyncio.gather(*tasks)
        assert len(sent) == 2
        stop()
        stop_count = len(sent)
        kick()
        await asyncio.sleep(0)
        assert len(sent) == stop_count and not rt.running
        assert await error_code(api.subscribe_departures(svc, {"stop_id": "zzz"}, sent.append, spawn)) == "not_found"

    with_service(tmp_path, body)
