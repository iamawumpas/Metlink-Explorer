import asyncio

from custom_components.metlink_explorer.core.http import (
    MetlinkAuthError,
    MetlinkBackoffError,
    MetlinkRequestError,
)
from custom_components.metlink_explorer.core.realtime import (
    RealtimeService,
    apply_delays,
    parse_alerts,
    parse_trip_updates,
    parse_vehicles,
)

VEHICLES = {"entity": [
    {"id": "e1", "vehicle": {"position": {"latitude": -41.2, "longitude": 174.8, "bearing": 90.0},
                              "timestamp": 100, "occupancy_status": 1,
                              "trip": {"trip_id": "T1", "direction_id": 1, "route_id": 63},
                              "vehicle": {"id": "0681"}}},
    {"id": "e2", "vehicle": {"trip": {"trip_id": "T2"}}},  # no position
]}
UPDATES = {"entity": [
    {"id": "a", "trip_update": {"trip": {"trip_id": "T1"},
                                "stop_time_update": {"stop_id": "S2", "stop_sequence": 2,
                                                     "arrival": {"delay": 120, "time": 1000}}}},
    {"id": "b", "trip_update": {"trip": {"trip_id": "T1"},
                                "stop_time_update": [{"stop_id": "S5", "stop_sequence": 5,
                                                      "departure": {"delay": -90}}]}},
    {"id": "c", "trip_update": {"trip": {"trip_id": "T9", "schedule_relationship": 3}}},
    {"id": "d", "trip_update": {"trip": {"trip_id": "T7"},
                                "stop_time_update": {"stop_id": "S1", "stop_sequence": 1,
                                                     "schedule_relationship": 1}}},
]}
ALERTS = {"entity": [{"id": "x", "alert": {
    "cause": "CONSTRUCTION", "effect": "STOP_MOVED", "severity_level": "WARNING",
    "header_text": {"translation": [{"language": "en", "text": "Shelter"}]},
    "active_period": [{"start": 1, "end": 2}],
    "informed_entity": [{"stop_id": "2132"}, {"route_id": 5}, {"stop_id": "2132"}]}}]}


def dep(trip, stop, seq, ts=500):
    return {"trip_id": trip, "stop_id": stop, "stop_sequence": seq, "timestamp": ts}


def test_parsers():
    v = parse_vehicles(VEHICLES)
    assert list(v) == ["0681"] and v["0681"]["trip_id"] == "T1" and v["0681"]["lat"] == -41.2
    assert parse_vehicles(None) == {} and parse_vehicles({"entity": None}) == {}
    u = parse_trip_updates(UPDATES)
    assert [x["sequence"] for x in u["T1"]["updates"]] == [2, 5]
    assert u["T9"]["canceled"] and u["T7"]["updates"][0]["skipped"]
    a = parse_alerts(ALERTS)[0]
    assert a["header"] == "Shelter" and a["stop_ids"] == ["2132"] and a["route_ids"] == ["5"]


def test_apply_delays():
    u = parse_trip_updates(UPDATES)
    exact = apply_delays([dep("T1", "S2", 2)], u)[0]
    assert exact["delay"] == 500 and exact["timestamp_expected"] == 1000 and exact["status"] == "delayed"
    carried = apply_delays([dep("T1", "S3", 3)], u)[0]  # delay carries forward from S2
    assert carried["delay"] == 120 and carried["timestamp_expected"] == 620
    early = apply_delays([dep("T1", "S5", 5)], u)[0]
    assert early["delay"] == -90 and early["status"] == "early"
    before = apply_delays([dep("T1", "S1", 1)], u)[0]  # earlier than any update
    assert before["delay"] is None and before["status"] == "scheduled"
    assert apply_delays([dep("T9", "S1", 1)], u)[0]["status"] == "canceled"
    assert apply_delays([dep("T7", "S1", 1)], u)[0]["status"] == "skipped"
    assert apply_delays([dep("nope", "S1", 1)], u)[0]["status"] == "scheduled"


class FakeHttp:
    def __init__(self, script):
        self.script, self.calls = script, []

    async def get_json(self, path):
        self.calls.append(path)
        result = self.script.get(path)
        if isinstance(result, Exception):
            raise result
        return result


PATHS = {"v": "/gtfs-rt/vehiclepositions", "t": "/gtfs-rt/tripupdates", "a": "/gtfs-rt/servicealerts"}


def service(script, **kw):
    return RealtimeService(FakeHttp(script), **kw)


def test_one_feed_failing_does_not_affect_others():
    async def main():
        svc = service({PATHS["v"]: MetlinkRequestError("boom"), PATHS["t"]: UPDATES, PATHS["a"]: ALERTS})
        assert await svc.poll_once("vehicles") == 30.0
        await svc.poll_once("trip_updates")
        await svc.poll_once("alerts")
        st = svc.status()
        assert not st["vehicles"]["ok"] and st["vehicles"]["failures"] == 1
        assert st["trip_updates"]["ok"] and st["alerts"]["ok"]
        assert "T1" in svc.snapshot.trip_updates and svc.snapshot.alerts

    asyncio.run(main())


def test_backoff_auth_and_garbage_payloads():
    async def main():
        svc = service({PATHS["v"]: MetlinkBackoffError(42), PATHS["t"]: MetlinkAuthError("no"),
                       PATHS["a"]: "not a dict"})
        assert await svc.poll_once("vehicles") == 42
        assert await svc.poll_once("trip_updates") == -1
        assert await svc.poll_once("alerts") == 180.0  # parse failure is contained
        assert not svc.status()["alerts"]["ok"]

    asyncio.run(main())


def test_polling_follows_subscribers():
    async def main():
        async def fast_sleep(_):
            await asyncio.sleep(0.005)

        svc = service({PATHS["v"]: VEHICLES, PATHS["t"]: UPDATES, PATHS["a"]: ALERTS}, sleep=fast_sleep)
        seen = []
        unsub = svc.subscribe(seen.append)
        unsub2 = svc.subscribe(lambda name: 1 / 0)  # broken subscriber must not stop polling
        await asyncio.sleep(0.1)
        assert svc.running and {"vehicles", "trip_updates", "alerts"} <= set(seen)
        assert svc.snapshot.vehicles["0681"]["lat"] == -41.2
        unsub()
        assert svc.running  # one subscriber left
        unsub2()
        await asyncio.sleep(0.02)
        assert not svc.running
        calls = len(svc._http.calls)
        await asyncio.sleep(0.05)
        assert len(svc._http.calls) == calls  # idle: no polling without subscribers

    asyncio.run(main())


def test_auth_failure_stops_that_feed_only():
    async def main():
        async def fast_sleep(_):
            await asyncio.sleep(0.005)

        svc = service({PATHS["v"]: VEHICLES, PATHS["t"]: MetlinkAuthError("no"), PATHS["a"]: ALERTS},
                      sleep=fast_sleep)
        unsub = svc.subscribe(lambda n: None)
        await asyncio.sleep(0.1)
        calls = svc._http.calls
        assert calls.count(PATHS["t"]) == 1  # stopped after the rejection
        assert calls.count(PATHS["v"]) > 1  # the others kept going
        unsub()
        await svc.async_stop()

    asyncio.run(main())
