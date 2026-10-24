"""Tests for the SQLite store."""
import asyncio

import pytest

from custom_components.metlink_explorer.core.store import Store

SCHEMA = "CREATE TABLE IF NOT EXISTS stops (id TEXT PRIMARY KEY, name TEXT);"


def run(coro):
    return asyncio.run(coro)


def test_insert_query_and_meta(tmp_path):
    async def main():
        store = Store(tmp_path / "t.db")
        await store.open(SCHEMA, 1)
        n = await store.executemany(
            "INSERT INTO stops VALUES (?, ?)", ((str(i), f"s{i}") for i in range(12000))
        )
        assert n == 12000
        assert (await store.query_one("SELECT COUNT(*) FROM stops"))[0] == 12000
        await store.set_meta("etag", "a")
        await store.set_meta("etag", "b")
        assert await store.get_meta("etag") == "b"
        assert await store.get_meta("missing") is None
        await store.close()

    run(main())


def test_failed_batch_rolls_back(tmp_path):
    async def main():
        store = Store(tmp_path / "t.db")
        await store.open(SCHEMA, 1)
        rows = [("1", "a"), ("1", "dup")]
        with pytest.raises(Exception):
            await store.executemany("INSERT INTO stops VALUES (?, ?)", rows)
        assert (await store.query_one("SELECT COUNT(*) FROM stops"))[0] == 0
        await store.close()

    run(main())


def test_data_persists_and_schema_version_change_rebuilds(tmp_path):
    path = tmp_path / "t.db"

    async def main():
        store = Store(path)
        await store.open(SCHEMA, 1)
        await store.execute("INSERT INTO stops VALUES ('1', 'a')")
        await store.close()

        store = Store(path)
        await store.open(SCHEMA, 1)
        assert (await store.query_one("SELECT COUNT(*) FROM stops"))[0] == 1
        await store.close()

        store = Store(path)
        await store.open(SCHEMA, 2)
        assert (await store.query_one("SELECT COUNT(*) FROM stops"))[0] == 0
        await store.close()

    run(main())


def test_transaction_rolls_back_on_error(tmp_path):
    async def main():
        store = Store(tmp_path / "t.db")
        await store.open(SCHEMA, 1)

        def work(conn):
            conn.execute("INSERT INTO stops VALUES ('1', 'a')")
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await store.transaction(work)
        assert (await store.query_one("SELECT COUNT(*) FROM stops"))[0] == 0
        await store.close()

    run(main())


def test_closed_store_raises(tmp_path):
    async def main():
        store = Store(tmp_path / "t.db")
        with pytest.raises(RuntimeError):
            await store.query("SELECT 1")

    run(main())
