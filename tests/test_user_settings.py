import asyncio

import pytest

from custom_components.metlink_explorer import user_settings as module


class FakeStore:
    def __init__(self, data=None):
        self.data = data

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.data = data


def test_user_settings_persist_independently(monkeypatch):
    async def main():
        store = FakeStore()
        monkeypatch.setattr(module, "Store", lambda hass, version, key: store)
        module_instance = module.UserSettings(object())

        await module_instance.async_set("user-a", "metlink_explorer_map:default", {"dim": 30})
        await module_instance.async_set("user-b", "metlink_explorer_map:default", {"dim": 60})

        assert await module_instance.async_get("user-a") == {"metlink_explorer_map:default": {"dim": 30}}
        assert await module_instance.async_get("user-b") == {"metlink_explorer_map:default": {"dim": 60}}

        restored = module.UserSettings(object())
        assert await restored.async_get("user-a") == {"metlink_explorer_map:default": {"dim": 30}}

    asyncio.run(main())


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("not-a-metlink-setting", {}),
        ("metlink_explorer_map:default", []),
        ("metlink_explorer_map:default", {"not_json": object()}),
        ("metlink_explorer_map:default", {"too_large": "x" * module.MAX_SETTINGS_BYTES}),
    ],
)
def test_user_settings_reject_invalid_values(key, value):
    async def main():
        settings = module.UserSettings.__new__(module.UserSettings)
        settings._store = FakeStore()
        settings._data = None
        settings._lock = asyncio.Lock()
        with pytest.raises(ValueError):
            await settings.async_set("user-a", key, value)

    asyncio.run(main())
