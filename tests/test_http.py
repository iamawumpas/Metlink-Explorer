"""Tests for the HTTP client."""
import asyncio

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from custom_components.metlink_explorer.core.http import (
    Backoff,
    MetlinkAuthError,
    MetlinkBackoffError,
    MetlinkHttpClient,
    MetlinkRequestError,
    parse_retry_after,
)


def run(coro):
    return asyncio.run(coro)


async def with_client(handler, body, **client_kwargs):
    app = web.Application()
    app.router.add_get("/{tail:.*}", handler)
    async with TestServer(app) as server:
        async with aiohttp.ClientSession() as session:
            client = MetlinkHttpClient(
                session,
                "secret",
                base_url=str(server.make_url("/v1")),
                min_interval=0,
                **client_kwargs,
            )
            return await body(client)


def test_sends_api_key_and_decodes_json():
    seen = {}

    async def handler(request):
        seen["key"] = request.headers.get("x-api-key")
        return web.json_response({"ok": True})

    async def body(client):
        return await client.get_json("gtfs/routes")

    assert run(with_client(handler, body)) == {"ok": True}
    assert seen["key"] == "secret"


def test_429_enters_backoff_and_skips_next_request():
    calls = []

    async def handler(request):
        calls.append(1)
        return web.Response(status=429, headers={"Retry-After": "120"})

    async def body(client):
        with pytest.raises(MetlinkRequestError) as first:
            await client.get("gtfs-rt/tripupdates")
        assert first.value.status == 429
        with pytest.raises(MetlinkBackoffError) as second:
            await client.get("gtfs-rt/tripupdates")
        assert second.value.retry_in > 100
        # A different endpoint is unaffected.
        with pytest.raises(MetlinkRequestError):
            await client.get("gtfs-rt/vehiclepositions")

    run(with_client(handler, body))
    assert len(calls) == 2


def test_auth_error_is_sticky():
    calls = []

    async def handler(request):
        calls.append(1)
        return web.Response(status=401)

    async def body(client):
        with pytest.raises(MetlinkAuthError):
            await client.get("a")
        assert client.auth_failed
        with pytest.raises(MetlinkAuthError):
            await client.get("b")

    run(with_client(handler, body))
    assert len(calls) == 1


def test_conditional_request_returns_304():
    async def handler(request):
        if request.headers.get("If-None-Match") == '"v1"':
            return web.Response(status=304)
        return web.Response(body=b"data", headers={"ETag": '"v1"'})

    async def body(client):
        first = await client.get("gtfs/stops", conditional=True)
        assert first.body == b"data" and not first.not_modified
        second = await client.get("gtfs/stops", conditional=True)
        assert second.not_modified and second.body is None

    run(with_client(handler, body))


def test_success_clears_backoff():
    state = {"fail": True}

    async def handler(request):
        if state["fail"]:
            return web.Response(status=500)
        return web.json_response({})

    now = {"t": 1000.0}

    async def body(client):
        with pytest.raises(MetlinkRequestError):
            await client.get("x")
        assert client.backoff_remaining("x") > 0
        state["fail"] = False
        now["t"] += 1000
        await client.get("x")
        assert client.backoff_remaining("x") == 0

    run(with_client(handler, body, clock=lambda: now["t"]))


def test_backoff_grows_and_is_capped():
    b = Backoff(base=5, maximum=60, clock=lambda: 0.0, rand=lambda: 0.5)
    delays = [b.failure() for _ in range(6)]
    assert delays[:3] == [5, 10, 20]
    assert max(delays) <= 60 * 1.25
    b.success()
    assert b.failures == 0 and b.remaining() == 0


def test_retry_after_overrides_short_backoff():
    b = Backoff(base=1, maximum=10, clock=lambda: 0.0, rand=lambda: 0.5)
    assert b.failure(retry_after=300) == 300


def test_parse_retry_after():
    assert parse_retry_after("30") == 30
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None
