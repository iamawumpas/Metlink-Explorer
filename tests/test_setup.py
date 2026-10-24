import asyncio
import json
from pathlib import Path

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer

from custom_components.metlink_explorer import config_flow
from custom_components.metlink_explorer.const import DOMAIN

PKG = Path(config_flow.__file__).parent


def test_manifest_and_translations_are_consistent():
    manifest = json.loads((PKG / "manifest.json").read_text())
    assert manifest["domain"] == DOMAIN and manifest["config_flow"] is True
    assert {"frontend", "http", "websocket_api"} <= set(manifest["dependencies"])
    strings = json.loads((PKG / "strings.json").read_text())
    assert strings == json.loads((PKG / "translations" / "en.json").read_text())
    fields = set(strings["config"]["step"]["user"]["data"])
    assert fields == {config_flow.CONF_METLINK_KEY, config_flow.CONF_AIS_KEY}
    assert "invalid_auth" in strings["config"]["error"]


def test_legacy_entry_is_rejected_and_cards_register_without_an_entry():
    import custom_components.metlink_explorer as integration
    from homeassistant.exceptions import ConfigEntryError

    class Entry:
        data = {"transport_type": "bus"}

    class Hass:
        data = {}

    try:
        asyncio.run(integration.async_setup_entry(Hass(), Entry()))
        raise AssertionError("legacy entry was accepted")
    except ConfigEntryError as err:
        assert "version 1" in str(err)

    calls = []

    async def fake_register(hass):
        calls.append(hass)

    original = integration._async_register_frontend
    integration._async_register_frontend = fake_register
    try:
        assert asyncio.run(integration.async_setup("hass", {})) is True
    finally:
        integration._async_register_frontend = original
    assert calls == ["hass"]


def test_integration_modules_import():
    import custom_components.metlink_explorer as integration

    assert callable(integration.async_setup_entry) and callable(integration.async_unload_entry)
    assert (PKG / "frontend" / integration.CARD_FILES[0]).exists()


def check_key(status):
    async def main():
        seen = {}

        async def handler(request):
            seen["key"] = request.headers.get("x-api-key")
            return web.Response(status=status)

        app = web.Application()
        app.router.add_get("/gtfs-rt/servicealerts", handler)
        async with TestServer(app) as server:
            original = config_flow.METLINK_BASE_URL
            config_flow.METLINK_BASE_URL = str(server.make_url("")).rstrip("/")
            try:
                async with aiohttp.ClientSession() as session:
                    return await config_flow.validate_metlink_key(session, "abc"), seen
            finally:
                config_flow.METLINK_BASE_URL = original

    return asyncio.run(main())


def test_key_validation_outcomes():
    assert check_key(200) == (None, {"key": "abc"})
    assert check_key(429)[0] is None  # busy, but the key was accepted
    assert check_key(401)[0] == "invalid_auth"
    assert check_key(403)[0] == "invalid_auth"
    assert check_key(503)[0] == "cannot_connect"


def test_unreachable_api_reports_cannot_connect():
    async def main():
        original = config_flow.METLINK_BASE_URL
        config_flow.METLINK_BASE_URL = "http://127.0.0.1:1"
        try:
            async with aiohttp.ClientSession() as session:
                return await config_flow.validate_metlink_key(session, "abc")
        finally:
            config_flow.METLINK_BASE_URL = original

    assert asyncio.run(main()) == "cannot_connect"
