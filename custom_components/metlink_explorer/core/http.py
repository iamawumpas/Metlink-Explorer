"""Rate-limited, backoff-aware HTTP client for the Metlink Open Data API."""
from __future__ import annotations

import asyncio
import email.utils
import json
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Callable

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.opendata.metlink.org.nz/v1"
DEFAULT_MIN_INTERVAL = 0.25
DEFAULT_TIMEOUT = 30
BACKOFF_BASE = 5.0
BACKOFF_MAX = 600.0
RETRY_AFTER_MAX = 3600.0


class MetlinkHttpError(Exception):
    """Base class for HTTP client errors."""


class MetlinkAuthError(MetlinkHttpError):
    """The API key was rejected (401/403). Retrying will not help."""


class MetlinkBackoffError(MetlinkHttpError):
    """A request was skipped because its endpoint is cooling down."""

    def __init__(self, retry_in: float) -> None:
        super().__init__(f"Endpoint cooling down for {retry_in:.0f}s")
        self.retry_in = retry_in


class MetlinkRequestError(MetlinkHttpError):
    """The request failed (network error, timeout or unexpected status)."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(slots=True)
class HttpResponse:
    """Result of a request. `body` is None when the server returned 304."""

    status: int
    body: bytes | None
    etag: str | None = None
    last_modified: str | None = None

    @property
    def not_modified(self) -> bool:
        return self.status == 304


class Backoff:
    """Exponential backoff with jitter for one endpoint."""

    def __init__(
        self,
        base: float = BACKOFF_BASE,
        maximum: float = BACKOFF_MAX,
        *,
        clock: Callable[[], float] = time.monotonic,
        rand: Callable[[], float] = random.random,
    ) -> None:
        self._base = base
        self._max = maximum
        self._clock = clock
        self._rand = rand
        self._failures = 0
        self._until = 0.0

    @property
    def failures(self) -> int:
        return self._failures

    def remaining(self) -> float:
        return max(0.0, self._until - self._clock())

    def success(self) -> None:
        self._failures = 0
        self._until = 0.0

    def failure(self, retry_after: float | None = None) -> float:
        """Record a failure and return the cooldown in seconds."""
        self._failures += 1
        delay = min(self._max, self._base * (2 ** (self._failures - 1)))
        delay *= 0.75 + 0.5 * self._rand()
        if retry_after is not None:
            delay = max(delay, min(retry_after, RETRY_AFTER_MAX))
        self._until = self._clock() + delay
        return delay


def parse_retry_after(value: str | None) -> float | None:
    """Parse a Retry-After header (seconds or HTTP date)."""
    if not value:
        return None
    value = value.strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    parsed = email.utils.parsedate_to_datetime(value) if value else None
    if parsed is None:
        return None
    return max(0.0, parsed.timestamp() - time.time())


class MetlinkHttpClient:
    """Shared client: auth header, global spacing, per-endpoint backoff, ETag."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        timeout: float = DEFAULT_TIMEOUT,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._min_interval = min_interval
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._clock = clock
        self._space_lock = asyncio.Lock()
        self._last_request = 0.0
        self._backoffs: dict[str, Backoff] = {}
        self._validators: dict[str, tuple[str | None, str | None]] = {}
        self._auth_failed = False

    @property
    def auth_failed(self) -> bool:
        return self._auth_failed

    def backoff_remaining(self, path: str) -> float:
        backoff = self._backoffs.get(path)
        return backoff.remaining() if backoff else 0.0

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        conditional: bool = False,
    ) -> HttpResponse:
        """GET `path`. With `conditional`, send ETag/Last-Modified validators."""
        if self._auth_failed:
            raise MetlinkAuthError("API key was rejected")

        backoff = self._backoffs.setdefault(path, Backoff(clock=self._clock))
        remaining = backoff.remaining()
        if remaining > 0:
            raise MetlinkBackoffError(remaining)

        headers = {"x-api-key": self._api_key, "accept": "*/*"}
        if conditional:
            etag, modified = self._validators.get(path, (None, None))
            if etag:
                headers["If-None-Match"] = etag
            if modified:
                headers["If-Modified-Since"] = modified

        await self._space_requests()
        url = f"{self._base_url}/{path.lstrip('/')}"
        try:
            async with self._session.get(
                url, params=params, headers=headers, timeout=self._timeout
            ) as resp:
                status = resp.status
                if status in (401, 403):
                    self._auth_failed = True
                    raise MetlinkAuthError(f"API key rejected ({status})")
                if status == 304:
                    backoff.success()
                    return HttpResponse(304, None, *self._validators.get(path, (None, None)))
                if status == 429 or status >= 500:
                    delay = backoff.failure(parse_retry_after(resp.headers.get("Retry-After")))
                    _LOGGER.warning("%s returned %s; cooling down %.0fs", path, status, delay)
                    raise MetlinkRequestError(f"{path} returned {status}", status)
                if status >= 400:
                    raise MetlinkRequestError(f"{path} returned {status}", status)
                body = await resp.read()
                etag = resp.headers.get("ETag")
                modified = resp.headers.get("Last-Modified")
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            delay = backoff.failure()
            _LOGGER.warning("%s failed (%s); cooling down %.0fs", path, err, delay)
            raise MetlinkRequestError(f"{path} failed: {err}") from err

        backoff.success()
        if conditional and (etag or modified):
            self._validators[path] = (etag, modified)
        return HttpResponse(status, body, etag, modified)

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET and decode a JSON body."""
        resp = await self.get(path, params)
        try:
            return json.loads(resp.body or b"null")
        except ValueError as err:
            raise MetlinkRequestError(f"{path} returned invalid JSON") from err

    async def _space_requests(self) -> None:
        """Keep a minimum gap between any two requests from this client."""
        async with self._space_lock:
            wait = self._min_interval - (self._clock() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = self._clock()
