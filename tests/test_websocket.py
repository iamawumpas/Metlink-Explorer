import asyncio
from types import SimpleNamespace

from custom_components.metlink_explorer import websocket as ws
from custom_components.metlink_explorer.const import DOMAIN
from tests.test_api import with_service


class FakeHass:
    def __init__(self, service=None):
        self.data = {DOMAIN: {"service": service}} if service else {}
        self.tasks = []

    def async_create_background_task(self, coro, name, eager_start=False):
        task = asyncio.ensure_future(coro)
        self.tasks.append(task)
        return task


class FakeConnection:
    def __init__(self, user_id="test-user"):
        self.log, self.subscriptions = [], {}
        self.user = SimpleNamespace(id=user_id)

    def send_result(self, id, result=None):
        self.log.append(("result", id, result))

    def send_error(self, id, code, message):
        self.log.append(("error", id, code))

    def send_message(self, message):
        self.log.append(("message", message["id"], message.get("event")))


async def call(hass, conn, command, msg):
    ws._make_handler(command)(hass, conn, {"id": 7, **msg})
    await asyncio.gather(*hass.tasks)


def test_commands_through_the_websocket_layer(tmp_path):
    async def body(svc, rt):
        hass, conn = FakeHass(svc), FakeConnection()
        await call(hass, conn, "routes", {"mode": "ferry"})
        assert conn.log[-1][0] == "result" and len(conn.log[-1][2]) == 1
        await call(hass, conn, "departures", {})
        assert conn.log[-1] == ("error", 7, "invalid_format")
        await call(hass, conn, "route", {"route_id": "nope"})
        assert conn.log[-1] == ("error", 7, "not_found")

        # Subscription: result first, then the initial event, then cleanup on unsubscribe.
        rt.snapshot.vehicles = {"1": {"id": "1", "trip_id": "T_in_1", "lat": -41.25, "lon": 174.8}}
        conn.log.clear()
        await call(hass, conn, "subscribe_vehicles", {})
        assert [e[0] for e in conn.log] == ["result", "message"] and 7 in conn.subscriptions
        assert conn.log[1][2][0]["route"] == "1" and rt.running
        conn.subscriptions.pop(7)()
        await asyncio.sleep(0)
        assert not rt.running

        conn.log.clear()
        await call(hass, conn, "subscribe_departures", {"stop_id": "A1", "towards": "A4", "horizon_hours": 3})
        await asyncio.gather(*hass.tasks)
        assert [e[0] for e in conn.log] == ["result", "message"]
        assert [d["trip_id"] for d in conn.log[1][2]] == ["T_in_1", "T_in_2"]
        conn.subscriptions.pop(7)()

        rt.snapshot.alerts = [{"id": "a", "stop_ids": [], "route_ids": ["R1"], "trip_ids": [], "header": "Detour"}]
        conn.log.clear()
        await call(hass, conn, "subscribe_alerts", {"modes": ["bus"]})
        assert [e[0] for e in conn.log] == ["result", "message"] and conn.log[1][2][0]["id"] == "a"
        conn.subscriptions.pop(7)()

    with_service(tmp_path, body)


def test_not_ready_when_service_missing():
    async def main():
        hass, conn = FakeHass(), FakeConnection()
        await call(hass, conn, "routes", {})
        assert conn.log == [("error", 7, "not_ready")]

    asyncio.run(main())


def test_settings_are_scoped_to_the_authenticated_user():
    class Settings:
        values = {}

        async def async_get(self, user_id):
            return dict(self.values.get(user_id, {}))

        async def async_set(self, user_id, key, value):
            self.values.setdefault(user_id, {})[key] = value

    async def main():
        settings = Settings()
        hass = FakeHass()
        hass.data[DOMAIN] = {"user_settings": settings}
        first = FakeConnection("first-user")
        second = FakeConnection("second-user")

        await call(hass, first, "save_settings", {"key": "metlink_explorer_map:default", "value": {"dim": 25}})
        await call(hass, second, "get_settings", {})
        assert first.log == [("result", 7, None)]
        assert second.log == [("result", 7, {})]

        await call(hass, first, "get_settings", {})
        assert first.log[-1] == ("result", 7, {"metlink_explorer_map:default": {"dim": 25}})

    asyncio.run(main())


def test_settings_require_an_authenticated_user():
    async def main():
        hass = FakeHass()
        hass.data[DOMAIN] = {"user_settings": object()}
        conn = FakeConnection(user_id=None)
        await call(hass, conn, "get_settings", {})
        assert conn.log == [("error", 7, "unauthorized")]

    asyncio.run(main())
