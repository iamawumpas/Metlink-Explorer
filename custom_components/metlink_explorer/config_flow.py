"""Config flow: just the Metlink key and the optional AISStream key."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_AIS_KEY, CONF_METLINK_KEY, DOMAIN, METLINK_BASE_URL

_LOGGER = logging.getLogger(__name__)

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_METLINK_KEY): str,
        vol.Optional(CONF_AIS_KEY, default=""): str,
    }
)


async def validate_metlink_key(session: aiohttp.ClientSession, key: str) -> str | None:
    """Returns an error code, or None when the key works.

    429 means the key was accepted but the API is busy, so it is not an error.
    """
    try:
        async with session.get(
            f"{METLINK_BASE_URL}/gtfs-rt/servicealerts",
            headers={"x-api-key": key},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status in (401, 403):
                return "invalid_auth"
            if resp.status >= 500:
                return "cannot_connect"
            return None
    except (aiohttp.ClientError, TimeoutError):
        return "cannot_connect"


class MetlinkExplorerConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = {k: v.strip() for k, v in user_input.items()}
            error = await validate_metlink_key(async_get_clientsession(self.hass), user_input[CONF_METLINK_KEY])
            if error is None:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Metlink Explorer", data=user_input)
            errors["base"] = error
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = {k: v.strip() for k, v in user_input.items()}
            error = await validate_metlink_key(async_get_clientsession(self.hass), user_input[CONF_METLINK_KEY])
            if error is None:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
            errors["base"] = error
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(SCHEMA, entry.data),
            errors=errors,
        )
