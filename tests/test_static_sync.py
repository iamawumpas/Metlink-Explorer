"""Tests for the static GTFS sync."""
import asyncio

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer

from custom_components.metlink_explorer.core.static_sync import (
    SCHEMA,
    StaticSync,
    build_database,
    decode_shape,
)
from custom_components.metlink_explorer.core.store import Store
from tests.gtfs_fixture import build_zip


def run(coro):
    return asyncio.run(coro)


class Feed:
    def __init__(self, data: bytes, etag: str = '"e1"'):
        self.data, self.etag, self.status, self.hits = data, etag, 200, 0

    async def handler(self, request):
        self.hits += 1
        if self.status != 200:
            return web.Response(status=self.status)
        if request.headers.get("If-None-Match") == self.etag:
            return web.Response(status=304)
        return web.Response(body=self.data, headers={"ETag": self.etag})


async def with_sync(tmp_path, feed, body):
    app = web.Application()
    app.router.add_get("/gtfs.zip", feed.handler)
    async with TestServer(app) as server:
        async with aiohttp.ClientSession() as session:
            store = Store(tmp_path / "gtfs.db")
            sync = StaticSync(session, store, tmp_path / "gtfs.db", url=str(server.make_url("/gtfs.zip")))
            await sync.async_open()
            try:
                return await body(sync, store)
            finally:
                await store.close()


def test_build_database_content(tmp_path):
    zip_path = tmp_path / "f.zip"
    zip_path.write_bytes(build_zip())

    async def main():
        store = Store(tmp_path / "b.db")
        await store.open(SCHEMA, 1)
        counts = await store.transaction(lambda conn: build_database(conn, zip_path))
        assert counts["routes"] == 3 and counts["stop_times"] == 20

        modes = dict(await store.query("SELECT route_id, mode FROM routes"))
        assert modes == {"R1": "bus", "R2": "bus", "R3": "ferry"}
        school = dict(await store.query("SELECT route_id, is_school FROM routes"))
        assert school["R2"] == 1 and school["R1"] == 0

        method = (await store.query_one(
            "SELECT direction_method FROM routes WHERE route_id='R1'"))[0]
        assert method == "cbd"
        flags = {
            (d, s): i for d, s, i in await store.query(
                "SELECT direction_id, stop_id, is_inbound FROM route_stops WHERE route_id='R1'")
        }
        assert all(flags[(1, f"A{k}")] == 1 for k in range(5))  # towards the CBD
        assert all(flags[(0, f"B{k}")] == 0 for k in range(5))  # away

        # 25h departure is stored as seconds beyond 24h.
        late = (await store.query_one("SELECT MAX(departure) FROM stop_times"))[0]
        assert late > 86400

        groups = await store.query("SELECT stop_id, group_id FROM stops WHERE group_id IS NOT NULL ORDER BY stop_id")
        assert groups == [("A1", "A1"), ("A2", "A2"), ("A3", "A3"), ("B1", "A1"), ("B2", "A2"), ("B3", "A3")]
        assert (await store.query_one("SELECT COUNT(*) FROM stop_pairs"))[0] == 6

        shape = decode_shape((await store.query_one("SELECT data FROM shapes WHERE shape_id='SH1'"))[0])
        assert shape == [(-41.22, 174.8), (-41.27, 174.8)]
        assert (await store.query_one("SELECT COUNT(*) FROM route_shapes"))[0] == 3
        main_stops = await store.query(
            "SELECT stop_id FROM route_stops WHERE route_id='R1' AND direction_id=1 ORDER BY seq")
        assert [r[0] for r in main_stops] == ["A0", "A1", "A2", "A3", "A4"]
        await store.close()

    run(main())


def test_build_without_pattern_files_uses_longest_trip(tmp_path):
    zip_path = tmp_path / "f.zip"
    zip_path.write_bytes(build_zip(patterns=False))

    async def main():
        store = Store(tmp_path / "b.db")
        await store.open(SCHEMA, 1)
        await store.transaction(lambda conn: build_database(conn, zip_path))
        assert (await store.query_one("SELECT COUNT(*) FROM stop_pairs"))[0] == 6
        await store.close()

    run(main())


def test_sync_updates_then_skips_unchanged(tmp_path):
    feed = Feed(build_zip(feed_version="v1"))

    async def body(sync, store):
        first = await sync.async_sync()
        assert first.status == "updated" and first.feed_version == "v1"
        assert (await store.query_one("SELECT COUNT(*) FROM routes"))[0] == 3
        assert await store.get_meta("etag") == '"e1"'

        second = await sync.async_sync()
        assert second.status == "unchanged"

        # New etag but same feed version: no rebuild.
        feed.etag = '"e2"'
        third = await sync.async_sync()
        assert third.status == "unchanged"
        assert await store.get_meta("etag") == '"e2"'

        # New feed version: rebuilt.
        feed.data, feed.etag = build_zip(feed_version="v2", extra_stop_name="Renamed"), '"e3"'
        fourth = await sync.async_sync()
        assert fourth.status == "updated" and fourth.feed_version == "v2"
        assert (await store.query_one("SELECT name FROM stops WHERE stop_id='Z1'"))[0] == "Renamed"

        forced = await sync.async_sync(force=True)
        assert forced.status == "updated"
        leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith((".tmp", ".new"))]
        assert leftovers == []

    run(with_sync(tmp_path, feed, body))


def test_failed_download_keeps_existing_data(tmp_path):
    feed = Feed(build_zip())

    async def body(sync, store):
        assert (await sync.async_sync()).status == "updated"
        feed.status = 500
        failed = await sync.async_sync(force=True)
        assert failed.status == "failed" and failed.error
        assert (await store.query_one("SELECT COUNT(*) FROM routes"))[0] == 3

    run(with_sync(tmp_path, feed, body))


def test_corrupt_zip_keeps_existing_data(tmp_path):
    feed = Feed(build_zip())

    async def body(sync, store):
        assert (await sync.async_sync()).status == "updated"
        feed.data, feed.etag = b"not a zip", '"bad"'
        failed = await sync.async_sync()
        assert failed.status == "failed"
        assert (await store.query_one("SELECT COUNT(*) FROM routes"))[0] == 3
        assert await store.get_meta("etag") == '"e1"'

    run(with_sync(tmp_path, feed, body))
