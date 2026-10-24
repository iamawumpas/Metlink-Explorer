import asyncio
import json

import aiohttp

from custom_components.metlink_explorer.core.ais import AisService, parse_position

MMSI = "512003252"


def report(mmsi=MMSI, lat=-41.28, lon=174.85, heading=90, kind="PositionReport"):
    return {
        "MessageType": kind,
        "MetaData": {"MMSI": int(mmsi), "ShipName": "EAST BY WEST "},
        "Message": {kind: {"Latitude": lat, "Longitude": lon, "TrueHeading": heading, "Cog": 45.0, "Sog": 12.5}},
    }


class FakeMsg:
    def __init__(self, data, type_=aiohttp.WSMsgType.TEXT):
        self.data, self.type = data, type_


class FakeWs:
    def __init__(self, messages):
        self.messages, self.sent = messages, []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send_str(self, text):
        self.sent.append(json.loads(text))

    def __aiter__(self):
        async def gen():
            for m in self.messages:
                yield FakeMsg(json.dumps(m) if isinstance(m, dict) else m)
        return gen()


class FakeSession:
    def __init__(self, *outcomes):
        self.outcomes, self.calls = list(outcomes), 0

    def ws_connect(self, url, **kw):
        self.calls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else FakeWs([])
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def handshake(status):
    return aiohttp.WSServerHandshakeError(None, (), status=status, message="x")


def test_parse_position_filters_and_picks_bearing():
    got = parse_position(report(), {MMSI})
    assert got["mmsi"] == MMSI and got["name"] == "EAST BY WEST" and got["bearing"] == 90
    assert parse_position(report(heading=511), {MMSI})["bearing"] == 45.0
    assert parse_position(report(mmsi="999"), {MMSI}) is None
    assert parse_position(report(lat=None), {MMSI}) is None
    assert parse_position(report(lat=-95), {MMSI}) is None
    assert parse_position(report(kind="ShipStaticData"), {MMSI}) is None
    assert parse_position("junk", {MMSI}) is None


def run_service(session, body, block_after=6, **kw):
    async def main():
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) > block_after:
                await asyncio.sleep(3600)

        ais = AisService(session, "key", sleep=fake_sleep, **kw)
        return await body(ais, sleeps)

    return asyncio.run(main())


async def settle():
    for _ in range(20):
        await asyncio.sleep(0)


def test_single_connection_shared_by_many_subscribers_and_stops_with_last():
    session = FakeSession(FakeWs([report()]))

    async def body(ais, sleeps):
        pushes = []
        a = ais.subscribe(lambda: pushes.append("a"))
        b = ais.subscribe(lambda: pushes.append("b"))
        await settle()
        assert session.calls == 1 and ais.running
        assert [v["mmsi"] for v in ais.vehicles()] == [MMSI]
        assert pushes == ["a", "b"]
        a()
        assert ais.running
        b()
        await settle()
        assert not ais.running

    run_service(session, body, block_after=0)


def test_backoff_grows_and_resets_and_auth_stops():
    session = FakeSession(OSError("down"), OSError("down"), handshake(429), FakeWs([report()]), handshake(401))

    async def body(ais, sleeps):
        ais.subscribe(lambda: None)
        await settle()
        assert sleeps[:4] == [30.0, 60.0, 120.0, 30.0]
        assert ais.stopped_reason and not ais.running
        assert session.calls == 5

    run_service(session, body)


def test_error_payload_key_rejected_stops_and_no_key_never_connects():
    session = FakeSession(FakeWs([{"error": "Api Key Is Not Valid"}]))

    async def body(ais, sleeps):
        ais.subscribe(lambda: None)
        await settle()
        assert ais.stopped_reason and session.calls == 1
        # A later subscriber must not retry a rejected key.
        ais.subscribe(lambda: None)
        await settle()
        assert session.calls == 1

    run_service(session, body)

    idle = FakeSession()

    async def main():
        ais = AisService(idle, "")
        ais.subscribe(lambda: None)
        await settle()
        assert idle.calls == 0 and not ais.enabled

    asyncio.run(main())


def test_pushes_are_throttled_and_stale_ships_expire():
    now = [1000.0]

    async def main():
        ais = AisService(FakeSession(), "key", clock=lambda: now[0])
        pushes = []
        ais._subscribers[1] = lambda: pushes.append(1)
        ais.handle_payload(report())
        now[0] += 1
        ais.handle_payload(report(lat=-41.29))
        assert len(pushes) == 1
        assert ais.vehicles()[0]["lat"] == -41.29
        now[0] += 6
        ais.handle_payload(report(lat=-41.30))
        assert len(pushes) == 2
        now[0] += 16 * 60
        assert ais.vehicles() == []

    asyncio.run(main())
