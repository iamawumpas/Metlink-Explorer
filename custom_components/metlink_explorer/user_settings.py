"""Persistent settings scoped to authenticated Home Assistant users."""
from __future__ import annotations

import asyncio
import json

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

MAX_SETTINGS_BYTES = 64 * 1024
SETTING_PREFIXES = ("metlink_explorer_board:", "metlink_explorer_map:")


class UserSettings:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store(hass, 1, f"{DOMAIN}_user_settings")
        self._data: dict | None = None
        self._lock = asyncio.Lock()

    async def _async_load(self) -> dict:
        if self._data is None:
            data = await self._store.async_load()
            if data is None:
                data = {"users": {}}
            if not isinstance(data, dict) or not isinstance(data.get("users", {}), dict):
                raise ValueError("Stored Metlink Explorer settings have an invalid format")
            self._data = {"users": data.get("users", {})}
        return self._data

    async def async_get(self, user_id: str) -> dict:
        async with self._lock:
            data = await self._async_load()
            settings = data["users"].get(user_id, {})
            if not isinstance(settings, dict):
                raise ValueError("Stored Metlink Explorer settings have an invalid format")
            return dict(settings)

    async def async_set(self, user_id: str, key: str, value: dict) -> None:
        if not isinstance(key, str) or not key.startswith(SETTING_PREFIXES) or len(key) > 160:
            raise ValueError("Invalid settings key")
        if any(ord(char) < 32 for char in key):
            raise ValueError("Invalid settings key")
        if not isinstance(value, dict):
            raise ValueError("Settings must be an object")
        try:
            serialized = json.dumps(value, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as err:
            raise ValueError("Settings must contain JSON-compatible values") from err
        if len(serialized.encode("utf-8")) > MAX_SETTINGS_BYTES:
            raise ValueError("Settings are too large")
        safe_value = json.loads(serialized)

        async with self._lock:
            data = await self._async_load()
            users = data["users"]
            user_settings = users.get(user_id, {})
            if not isinstance(user_settings, dict):
                raise ValueError("Stored Metlink Explorer settings have an invalid format")
            candidate = {
                "users": {
                    **users,
                    user_id: {**user_settings, key: safe_value},
                }
            }
            await self._store.async_save(candidate)
            self._data = candidate
