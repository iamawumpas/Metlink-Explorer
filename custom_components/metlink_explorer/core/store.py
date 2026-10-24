"""SQLite store for static GTFS data. All access runs on one worker thread."""
from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence, TypeVar

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")

META_SCHEMA = "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID;"
DEFAULT_CACHE_KB = 8192
DEFAULT_MMAP_BYTES = 32 * 1024 * 1024
BATCH_SIZE = 5000


class Store:
    """Async wrapper around one SQLite connection (WAL, capped page cache)."""

    def __init__(
        self,
        path: str | Path,
        *,
        cache_kb: int = DEFAULT_CACHE_KB,
        mmap_bytes: int = DEFAULT_MMAP_BYTES,
    ) -> None:
        self._path = str(path)
        self._cache_kb = cache_kb
        self._mmap_bytes = mmap_bytes
        self._conn: sqlite3.Connection | None = None
        self._executor: ThreadPoolExecutor | None = None

    @property
    def is_open(self) -> bool:
        return self._conn is not None

    async def open(self, schema: str, version: int) -> None:
        """Open the database and apply `schema`.

        The data is a rebuildable cache, so when the stored schema version
        differs every table is dropped and the schema is created afresh.
        """
        if self._conn is not None:
            return
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="metlink_store")
        await self._run(self._open_sync, schema, version)

    async def close(self) -> None:
        if self._executor is None:
            return
        if self._conn is not None:
            await self._run(self._close_sync)
        self._executor.shutdown(wait=True)
        self._executor = None

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        await self._run(self._execute_sync, sql, params)

    async def executescript(self, script: str) -> None:
        await self._run(self._script_sync, script)

    async def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> int:
        """Insert rows in batches inside one transaction. Returns the row count."""
        return await self._run(self._executemany_sync, sql, rows)

    async def query(self, sql: str, params: Sequence[Any] = ()) -> list[tuple]:
        return await self._run(self._query_sync, sql, params)

    async def query_one(self, sql: str, params: Sequence[Any] = ()) -> tuple | None:
        rows = await self.query(sql, params)
        return rows[0] if rows else None

    async def get_meta(self, key: str) -> str | None:
        row = await self.query_one("SELECT value FROM meta WHERE key = ?", (key,))
        return row[0] if row else None

    async def set_meta(self, key: str, value: str) -> None:
        await self.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    async def transaction(self, func: Callable[[sqlite3.Connection], T]) -> T:
        """Run `func(conn)` on the worker thread in one transaction."""
        return await self._run(self._transaction_sync, func)

    async def replace_with(self, new_path: str | Path, schema: str, version: int) -> None:
        """Swap in a freshly built database file.

        Runs on the worker thread, so queued queries see either the old
        database or the new one and never a closed store.
        """
        await self._run(self._replace_sync, str(new_path), schema, version)

    async def _run(self, func: Callable[..., T], *args: Any) -> T:
        if self._executor is None:
            raise RuntimeError("Store is not open")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, func, *args)

    def _conn_or_raise(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Store is not open")
        return self._conn

    def _open_sync(self, schema: str, version: int) -> None:
        conn = sqlite3.connect(self._path, check_same_thread=False, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute(f"PRAGMA cache_size=-{int(self._cache_kb)}")
        conn.execute(f"PRAGMA mmap_size={int(self._mmap_bytes)}")
        conn.execute("PRAGMA temp_store=FILE")
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        if current != version:
            if current:
                _LOGGER.info("Static database schema %s -> %s; rebuilding", current, version)
            self._drop_all(conn)
        conn.executescript(META_SCHEMA)
        conn.executescript(schema)
        conn.execute(f"PRAGMA user_version={int(version)}")
        self._conn = conn

    @staticmethod
    def _drop_all(conn: sqlite3.Connection) -> None:
        names = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for name in names:
            conn.execute(f'DROP TABLE IF EXISTS "{name}"')

    def _close_sync(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _replace_sync(self, new_path: str, schema: str, version: int) -> None:
        self._close_sync()
        for suffix in ("-wal", "-shm"):
            Path(self._path + suffix).unlink(missing_ok=True)
        os.replace(new_path, self._path)
        for suffix in ("-wal", "-shm"):
            Path(new_path + suffix).unlink(missing_ok=True)
        self._open_sync(schema, version)

    def _execute_sync(self, sql: str, params: Sequence[Any]) -> None:
        self._conn_or_raise().execute(sql, params)

    def _script_sync(self, script: str) -> None:
        self._conn_or_raise().executescript(script)

    def _query_sync(self, sql: str, params: Sequence[Any]) -> list[tuple]:
        return self._conn_or_raise().execute(sql, params).fetchall()

    def _executemany_sync(self, sql: str, rows: Iterable[Sequence[Any]]) -> int:
        conn = self._conn_or_raise()
        total = 0
        batch: list[Sequence[Any]] = []
        conn.execute("BEGIN")
        try:
            for row in rows:
                batch.append(row)
                if len(batch) >= BATCH_SIZE:
                    conn.executemany(sql, batch)
                    total += len(batch)
                    batch.clear()
            if batch:
                conn.executemany(sql, batch)
                total += len(batch)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return total

    def _transaction_sync(self, func: Callable[[sqlite3.Connection], T]) -> T:
        conn = self._conn_or_raise()
        conn.execute("BEGIN")
        try:
            result = func(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return result
